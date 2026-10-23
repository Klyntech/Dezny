import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.security import require_api_token


@pytest.mark.asyncio
async def test_missing_token_configuration_fails_closed(monkeypatch):
    from app import security
    monkeypatch.setattr(security, "get_settings", lambda: type("S", (), {"dezny_api_token": None})())
    with pytest.raises(HTTPException) as exc:
        await require_api_token(None)
    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_wrong_token_is_rejected(monkeypatch):
    from app import security
    monkeypatch.setattr(security, "get_settings", lambda: type("S", (), {"dezny_api_token": "correct"})())
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="wrong")
    with pytest.raises(HTTPException) as exc:
        await require_api_token(credentials)
    assert exc.value.status_code == 401
