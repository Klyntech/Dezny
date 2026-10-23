"""FastAPI webhook adapter for running the Telegram bot as a Render Web Service."""
import hmac
import logging
import os
from contextlib import asynccontextmanager

from aiogram import Bot
from aiogram.types import Update
from fastapi import FastAPI, Header, HTTPException, Request, status

from app.telegram_bot import dp, settings

logger = logging.getLogger("dezny.telegram.webhook")
bot: Bot | None = None
webhook_secret = os.getenv("TELEGRAM_WEBHOOK_SECRET", "")
WEBHOOK_PATH = "/telegram/webhook"


@asynccontextmanager
async def lifespan(_: FastAPI):
    global bot
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required")
    if not settings.allowed_telegram_user_ids:
        raise RuntimeError("TELEGRAM_ALLOWED_USER_IDS must contain at least one numeric Telegram user ID")
    if not webhook_secret:
        raise RuntimeError("TELEGRAM_WEBHOOK_SECRET is required")
    external_url = os.getenv("RENDER_EXTERNAL_URL", "").rstrip("/")
    if not external_url:
        raise RuntimeError("RENDER_EXTERNAL_URL is required for Telegram webhook mode")

    bot = Bot(token=settings.telegram_bot_token)
    await bot.set_webhook(
        url=f"{external_url}{WEBHOOK_PATH}",
        secret_token=webhook_secret,
        allowed_updates=dp.resolve_used_update_types(),
    )
    logger.info("Telegram webhook configured")
    try:
        yield
    finally:
        await bot.session.close()
        bot = None


app = FastAPI(title="Dezny Telegram Interface", version="0.1.0", lifespan=lifespan)


@app.get("/healthz")
async def healthz():
    return {"status": "ok", "service": "dezny-telegram-bot", "mode": "webhook"}


@app.post(WEBHOOK_PATH)
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
):
    if not webhook_secret or not x_telegram_bot_api_secret_token or not hmac.compare_digest(
        x_telegram_bot_api_secret_token, webhook_secret
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid webhook secret")
    if bot is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Bot is starting")
    try:
        payload = await request.json()
        update = Update.model_validate(payload, context={"bot": bot})
        await dp.feed_update(bot, update)
    except Exception as exc:
        logger.exception("Could not process Telegram update")
        raise HTTPException(status_code=400, detail="Invalid Telegram update") from exc
    return {"ok": True}
