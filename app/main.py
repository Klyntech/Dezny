import hashlib
import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.config import get_settings
from app.db import dispose_engine, session_factory
from app.models import Document, IngestionJob
from app.rag import answer_question
from app.security import require_api_token
from app.storage import make_storage_key, put_bytes

logging.basicConfig(level=get_settings().log_level)
logger = logging.getLogger("dezny")
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await dispose_engine()


app = FastAPI(title="Dezny API", description="Private legal study assistant for Nigerian law", version="0.1.0", lifespan=lifespan)


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=4000)
    collection_key: str = Field(default="default", min_length=1, max_length=100)


@app.get("/healthz", tags=["operations"])
async def healthz():
    return {"status": "ok", "service": "dezny"}


@app.get("/readyz", tags=["operations"])
async def readyz():
    try:
        async with session_factory()() as session:
            await session.execute(text("SELECT 1"))
        return {"status": "ready", "database": "reachable"}
    except Exception as exc:
        logger.warning("Readiness failed: %s", type(exc).__name__)
        raise HTTPException(status_code=503, detail="Database is not ready") from exc


@app.post("/v1/documents", status_code=status.HTTP_202_ACCEPTED, tags=["documents"])
async def upload_document(
    file: UploadFile = File(...),
    collection_key: str = Form(default="default", min_length=1, max_length=100),
    sensitivity: str = Form(default="private", pattern="^(private|sensitive)$"),
    _: str = Depends(require_api_token),
):
    filename = Path(file.filename or "upload").name
    if Path(filename).suffix.lower() not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=415, detail="Allowed file types: PDF, DOCX, TXT.")
    settings = get_settings()
    content = await file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(content) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"Maximum upload size is {settings.max_upload_mb} MB.")
    key = make_storage_key(filename)
    try:
        await put_bytes(key, content, file.content_type or "application/octet-stream")
    except Exception as exc:
        logger.exception("Document storage failed")
        raise HTTPException(status_code=503, detail="Document storage is unavailable.") from exc
    doc = Document(filename=filename, content_type=file.content_type or "application/octet-stream",
                   sha256=hashlib.sha256(content).hexdigest(), storage_key=key,
                   collection_key=collection_key, sensitivity=sensitivity, status="queued")
    try:
        async with session_factory()() as session:
            async with session.begin():
                session.add(doc)
                await session.flush()
                session.add(IngestionJob(document_id=doc.id, status="queued"))
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail="This file already exists in this collection.") from exc
    except Exception as exc:
        logger.exception("Could not queue ingestion")
        raise HTTPException(status_code=503, detail="Could not queue document ingestion.") from exc
    return {"document_id": str(doc.id), "filename": filename, "collection_key": collection_key, "status": "queued"}


@app.post("/v1/ask", tags=["legal-rag"])
async def ask(request: AskRequest, _: str = Depends(require_api_token)):
    try:
        return await answer_question(request.question, request.collection_key)
    except Exception as exc:
        logger.exception("Answer workflow failed")
        raise HTTPException(status_code=503, detail="Dezny could not complete the research request.") from exc


@app.get("/v1/documents/{document_id}", tags=["documents"])
async def document_status(document_id: uuid.UUID, _: str = Depends(require_api_token)):
    async with session_factory()() as session:
        doc = await session.get(Document, document_id)
        if doc is None:
            raise HTTPException(status_code=404, detail="Document not found.")
        return {"document_id": str(doc.id), "filename": doc.filename, "collection_key": doc.collection_key,
                "sensitivity": doc.sensitivity, "status": doc.status, "error": doc.error_message, "created_at": doc.created_at}
