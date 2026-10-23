import pytest

from app import storage


class ProductionWithoutObjectStorage:
    dezny_env = "production"
    object_storage_enabled = False


@pytest.mark.asyncio
async def test_production_upload_fails_closed_without_object_storage(monkeypatch):
    monkeypatch.setattr(storage, "get_settings", lambda: ProductionWithoutObjectStorage())

    with pytest.raises(RuntimeError, match="Object storage must be configured"):
        await storage.put_bytes("documents/test.txt", b"private study notes", "text/plain")


@pytest.mark.asyncio
async def test_production_read_fails_closed_without_object_storage(monkeypatch):
    monkeypatch.setattr(storage, "get_settings", lambda: ProductionWithoutObjectStorage())

    with pytest.raises(RuntimeError, match="Object storage must be configured"):
        await storage.get_bytes("documents/test.txt")
