import pytest

from app import rag


@pytest.mark.asyncio
async def test_sensitive_collection_skips_web_search(monkeypatch):
    def fail_settings():
        raise AssertionError("Settings should not be read for blocked external processing")

    monkeypatch.setattr(rag, "get_settings", fail_settings)

    result = await rag.web_search({"query": "contract law", "external_processing_allowed": False})

    assert result == {"web_results": []}


@pytest.mark.asyncio
async def test_sensitive_collection_returns_restriction_without_model_call(monkeypatch):
    async def fail_chat(*args, **kwargs):
        raise AssertionError("Model must not be called for sensitive collections")

    monkeypatch.setattr(rag, "chat", fail_chat)

    result = await rag.compose({"query": "summarize this", "external_processing_allowed": False})

    assert result["sources"] == []
    assert "External AI processing is disabled" in result["answer"]
