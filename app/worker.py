import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError

from app.config import get_settings
from app.db import dispose_engine, session_factory
from app.ingestion import chunk_pages, extract_pages
from app.models import Chunk, Document, IngestionJob
from app.nim import embed_texts
from app.storage import get_bytes

logging.basicConfig(level=get_settings().log_level)
logger = logging.getLogger("dezny.worker")
MAX_ATTEMPTS = 5


async def claim_job():
    async with session_factory()() as session:
        async with session.begin():
            statement = (select(IngestionJob)
                .where(IngestionJob.status.in_(["queued", "retry"]),
                       IngestionJob.available_at <= datetime.now(UTC),
                       IngestionJob.attempts < MAX_ATTEMPTS)
                .order_by(IngestionJob.created_at).with_for_update(skip_locked=True).limit(1))
            job = (await session.execute(statement)).scalar_one_or_none()
            if job is None:
                return None
            job.status = "processing"
            job.attempts += 1
            job.locked_at = datetime.now(timezone.utc)
            return {"job_id": job.id, "document_id": job.document_id, "attempts": job.attempts}


async def process_job(job: dict) -> None:
    async with session_factory()() as session:
        doc = await session.get(Document, job["document_id"])
        if doc is None:
            async with session.begin():
                record = await session.get(IngestionJob, job["job_id"])
                if record:
                    record.status = "failed"
                    record.last_error = "Document record no longer exists."
            return
        doc.status = "processing"
        await session.commit()
        try:
            pages = extract_pages(doc.filename, await get_bytes(doc.storage_key), get_settings().ocr_enabled)
            chunks = chunk_pages(pages)
            if not chunks:
                raise ValueError("No readable text extracted; check scan quality and OCR setup.")
            vectors = []
            if get_settings().nvidia_api_key and doc.sensitivity != "sensitive":
                for offset in range(0, len(chunks), 32):
                    vectors.extend(await embed_texts([c["text"] for c in chunks[offset:offset+32]], "passage"))
            async with session.begin():
                await session.execute(delete(Chunk).where(Chunk.document_id == doc.id))
                for index, item in enumerate(chunks):
                    session.add(Chunk(document_id=doc.id, collection_key=doc.collection_key, chunk_index=index,
                        page_number=item["page_number"], section=item["section"], text=item["text"],
                        embedding=vectors[index] if vectors else None, source_metadata=item["metadata"]))
                doc.status = "indexed"
                doc.error_message = None
                record = await session.get(IngestionJob, job["job_id"])
                if record:
                    record.status = "completed"
                    record.locked_at = None
                    record.last_error = None
            logger.info("Indexed %s into %d chunks", doc.id, len(chunks))
        except Exception as exc:
            logger.exception("Ingestion job failed")
            async with session.begin():
                record = await session.get(IngestionJob, job["job_id"])
                current = await session.get(Document, job["document_id"])
                if record:
                    record.last_error = f"{type(exc).__name__}: {str(exc)[:1000]}"
                    record.locked_at = None
                    record.status = "retry" if record.attempts < MAX_ATTEMPTS else "failed"
                    record.available_at = datetime.now(timezone.utc) + timedelta(seconds=min(300, 5 * 2 ** record.attempts))
                if current:
                    current.status = "failed"
                    current.error_message = f"{type(exc).__name__}: {str(exc)[:1000]}"


async def run_worker():
    if not get_settings().database_url:
        raise RuntimeError("DATABASE_URL must be configured")
    logger.info("Dezny ingestion worker started")
    try:
        while True:
            try:
                job = await claim_job()
                if job:
                    await process_job(job)
                else:
                    await asyncio.sleep(2)
            except SQLAlchemyError:
                logger.exception("Database error in worker")
                await asyncio.sleep(5)
            except Exception:
                logger.exception("Unexpected worker error")
                await asyncio.sleep(5)
    finally:
        await dispose_engine()


if __name__ == "__main__":
    asyncio.run(run_worker())
