from sqlalchemy.dialects import postgresql

from app import worker


class FakeResult:
    def scalar_one_or_none(self):
        return None


class FakeContext:
    def __init__(self, value):
        self.value = value

    async def __aenter__(self):
        return self.value

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class FakeSession:
    def __init__(self):
        self.statements = []

    def begin(self):
        return FakeContext(self)

    async def execute(self, statement):
        self.statements.append(statement)
        return FakeResult()


async def test_claim_job_recovers_stale_jobs_and_fails_exhausted_jobs(monkeypatch):
    session = FakeSession()
    monkeypatch.setattr(worker, "session_factory", lambda: lambda: FakeContext(session))

    claimed = await worker.claim_job()

    assert claimed is None
    assert len(session.statements) == 3

    retry_sql = str(session.statements[0].compile(dialect=postgresql.dialect()))
    fail_sql = str(session.statements[1].compile(dialect=postgresql.dialect()))
    claim_sql = str(session.statements[2].compile(dialect=postgresql.dialect()))

    assert "UPDATE ingestion_jobs" in retry_sql
    assert "locked_at" in retry_sql
    assert "attempts" in retry_sql
    assert "UPDATE ingestion_jobs" in fail_sql
    assert "status" in fail_sql
    assert "FOR UPDATE SKIP LOCKED" in claim_sql


def test_worker_lease_timeout_is_five_minutes():
    assert worker.JOB_LEASE_TIMEOUT.total_seconds() == 300
