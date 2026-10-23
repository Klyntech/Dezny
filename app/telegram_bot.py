"""Private Telegram interface for Dezny.

Run as a separate process: python -m app.telegram_bot
Only explicitly allowlisted Telegram numeric user IDs are accepted.
"""
import asyncio
import logging
from pathlib import Path

import httpx
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from app.config import get_settings

logger = logging.getLogger("dezny.telegram")
settings = get_settings()
dp = Dispatcher()

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}
MAX_TELEGRAM_UPLOAD_BYTES = settings.max_upload_mb * 1024 * 1024


def allowed_user(message: Message) -> bool:
    user_id = message.from_user.id if message.from_user else None
    return bool(user_id and user_id in settings.telegram_allowed_user_ids)


def api_headers() -> dict[str, str]:
    if not settings.dezny_api_token:
        raise RuntimeError("DEZNY_API_TOKEN is not configured")
    return {"Authorization": f"Bearer {settings.dezny_api_token}"}


async def reject_unless_allowed(message: Message) -> bool:
    if allowed_user(message):
        return True
    await message.answer("Access denied. This bot is private.")
    return False


@dp.message(CommandStart())
async def start(message: Message) -> None:
    if not await reject_unless_allowed(message):
        return
    await message.answer(
        "Dezny — Nigerian law study assistant.\n"
        "Send a question to search your indexed study documents.\n"
        "Send a PDF, DOCX, or TXT file to ingest it.\n"
        "Caption a file with /sensitive to mark its collection as sensitive."
    )


@dp.message(Command("help"))
async def help_command(message: Message) -> None:
    if not await reject_unless_allowed(message):
        return
    await message.answer(
        "Ask a legal-study question in plain text, or upload PDF/DOCX/TXT. "
        "Use /sensitive as the upload caption for sensitive material. "
        "This prototype is for study and does not replace checking primary legal sources."
    )


@dp.message(F.document)
async def receive_document(message: Message, bot: Bot) -> None:
    if not await reject_unless_allowed(message):
        return
    document = message.document
    if document is None:
        return
    filename = Path(document.file_name or "upload").name
    if Path(filename).suffix.lower() not in ALLOWED_EXTENSIONS:
        await message.answer("Unsupported file type. Please upload PDF, DOCX, or TXT.")
        return
    if document.file_size and document.file_size > MAX_TELEGRAM_UPLOAD_BYTES:
        await message.answer(f"File exceeds the configured {settings.max_upload_mb} MB limit.")
        return
    if not settings.dezny_api_url or not settings.dezny_api_token:
        await message.answer("Dezny API is not configured yet.")
        return

    sensitive = (message.caption or "").strip().lower() == "/sensitive"
    status_message = await message.answer("Receiving document…")
    try:
        file_info = await bot.get_file(document.file_id)
        if not file_info.file_path:
            await status_message.edit_text("Telegram did not provide a downloadable file path.")
            return
        downloaded = await bot.download_file(file_info.file_path)
        content = downloaded.read()
        if len(content) > MAX_TELEGRAM_UPLOAD_BYTES:
            await status_message.edit_text("File exceeds the configured upload limit.")
            return
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{settings.dezny_api_url.rstrip('/')}/v1/documents",
                headers=api_headers(),
                data={
                    "collection_key": "sensitive" if sensitive else "default",
                    "sensitivity": "sensitive" if sensitive else "private",
                },
                files={"file": (filename, content, document.mime_type or "application/octet-stream")},
            )
            response.raise_for_status()
            result = response.json()
        await status_message.edit_text(
            f"Document queued.\nID: {result['document_id']}\n"
            f"Status: {result['status']}\nCollection: {result['collection_key']}"
        )
    except httpx.HTTPStatusError as exc:
        logger.warning("Document upload rejected with HTTP %s", exc.response.status_code)
        await status_message.edit_text(
            f"Upload was rejected (HTTP {exc.response.status_code}). Check the file and API configuration."
        )
    except Exception:
        logger.exception("Telegram document upload failed")
        await status_message.edit_text("Upload failed. Please try again later.")


@dp.message(F.text)
async def answer_question(message: Message) -> None:
    if not await reject_unless_allowed(message):
        return
    question = (message.text or "").strip()
    if not question or question.startswith("/"):
        await message.answer("Send a question as plain text, or use /help.")
        return
    if not settings.dezny_api_url or not settings.dezny_api_token:
        await message.answer("Dezny API is not configured yet.")
        return
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{settings.dezny_api_url.rstrip('/')}/v1/ask",
                headers=api_headers(),
                json={"question": question, "collection_key": "default"},
            )
            response.raise_for_status()
            result = response.json()
        answer = str(result.get("answer") or result.get("response") or "No answer was returned.")
        # Telegram message limit is 4096 characters; leave room for safe splitting.
        for start in range(0, len(answer), 3900):
            await message.answer(answer[start : start + 3900])
    except httpx.HTTPStatusError as exc:
        logger.warning("Question failed with HTTP %s", exc.response.status_code)
        await message.answer(
            "Dezny could not complete that question. Check API logs and verify that the database and model are configured."
        )
    except Exception:
        logger.exception("Telegram question failed")
        await message.answer("Dezny is temporarily unavailable. Please try again later.")


async def main() -> None:
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required")
    if not settings.telegram_allowed_user_ids:
        raise RuntimeError("TELEGRAM_ALLOWED_USER_IDS must contain at least one numeric Telegram user ID")
    bot = Bot(token=settings.telegram_bot_token)
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()


if __name__ == "__main__":
    logging.basicConfig(level=settings.log_level)
    asyncio.run(main())
