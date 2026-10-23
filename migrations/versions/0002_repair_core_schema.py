"""Repair core tables when an earlier deployment stamped an incomplete schema."""
from alembic import op

revision = "0002_repair_core_schema"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id UUID PRIMARY KEY,
            filename VARCHAR(255) NOT NULL,
            content_type VARCHAR(120) NOT NULL,
            sha256 VARCHAR(64) NOT NULL,
            storage_key VARCHAR(700) NOT NULL,
            collection_key VARCHAR(100) NOT NULL DEFAULT 'default',
            sensitivity VARCHAR(30) NOT NULL DEFAULT 'private',
            status VARCHAR(30) NOT NULL DEFAULT 'queued',
            error_message TEXT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_document_collection_sha256 UNIQUE (collection_key, sha256)
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS ingestion_jobs (
            id UUID PRIMARY KEY,
            document_id UUID NOT NULL UNIQUE REFERENCES documents(id) ON DELETE CASCADE,
            status VARCHAR(30) NOT NULL DEFAULT 'queued',
            attempts INTEGER NOT NULL DEFAULT 0,
            available_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            locked_at TIMESTAMPTZ NULL,
            last_error TEXT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS chunks (
            id UUID PRIMARY KEY,
            document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            collection_key VARCHAR(100) NOT NULL,
            chunk_index INTEGER NOT NULL,
            page_number INTEGER NULL,
            section VARCHAR(500) NULL,
            text TEXT NOT NULL,
            embedding vector(1024) NULL,
            source_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_chunk_document_index UNIQUE (document_id, chunk_index)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_documents_collection_status ON documents (collection_key, status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_ingestion_jobs_status_available ON ingestion_jobs (status, available_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_chunks_collection ON chunks (collection_key)")


def downgrade():
    # Intentionally non-destructive: these tables may contain user documents.
    pass
