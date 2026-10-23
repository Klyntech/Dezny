# Dezny

Private, evidence-grounded legal study assistant focused initially on Nigerian law. This is an early prototype, not production-ready and not a substitute for checking primary legal sources.

## Prototype foundation
- FastAPI endpoints protected by a bearer token.
- PDF, DOCX, and TXT ingestion; OCR attempted for image-only PDFs when Tesseract is installed.
- PostgreSQL metadata, chunks, pgvector embeddings, and a durable ingestion-job table.
- LangGraph retrieval → optional web search → cited answer workflow.
- NVIDIA NIM adapter for embeddings and reasoning.
- S3-compatible object storage support (including Cloudflare R2); local storage is development-only.
- Alembic migrations and starter tests.

## Local setup
Requirements: Python 3.12+, PostgreSQL with pgvector, and optionally Tesseract OCR.

1. Create a virtual environment and install: python -m venv .venv; activate it; run pip install -e ".[dev]".
2. Copy .env.example to .env. Set DATABASE_URL, a strong DEZNY_API_TOKEN, NVIDIA_API_KEY, and optionally TAVILY_API_KEY and S3 settings.
3. Run alembic upgrade head.
4. Start the API with uvicorn app.main:app --reload.
5. In another terminal run python -m app.worker.
6. Run ruff check . and pytest.

## API
All /v1 endpoints require Authorization: Bearer <DEZNY_API_TOKEN>.
- GET /healthz: liveness check.
- GET /readyz: database readiness.
- POST /v1/documents: multipart upload; fields file, collection_key (default), sensitivity (private or sensitive).
- GET /v1/documents/{document_id}: ingestion status.
- POST /v1/ask: JSON with question and optional collection_key.

## Important limitations
Telegram integration, study memory, document deletion/versioning endpoints, and an admin UI are not implemented yet. Web search is optional and currently uses Tavily; search results are not automatically authoritative. The embedding column is fixed at 1024 dimensions; verify the chosen NIM embedding model's output and update configuration plus migration together if needed. Local file storage is not durable on ephemeral hosting. Worker lease expiry, dead-letter review, malware scanning, source-authority verification, privacy review, and backup/restore drills remain future work. The five-minute RTO/RPO targets are not guaranteed by this prototype.

Sensitive collections are not sent to external embedding, web-search, or model services by default. If a collection contains any document marked sensitive, questions against that collection return a restriction notice until local model support or an explicitly reviewed privacy policy is added. Do not upload confidential client material until deletion and recovery have been tested. No cloud database, object-storage bucket, Telegram bot, model endpoint, or hosting service is provisioned by this repository.
