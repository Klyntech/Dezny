import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings

_bearer = HTTPBearer(auto_error=False)


async def require_api_token(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> str:
    expected = get_settings().dezny_api_token
    if not expected:
        raise HTTPException(status_code=503, detail="Private API is not configured. Set DEZNY_API_TOKEN.")
    if credentials is None or not secrets.compare_digest(credentials.credentials, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing credentials.",
                            headers={"WWW-Authenticate": "Bearer"})
    return "owner"
