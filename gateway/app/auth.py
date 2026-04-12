from __future__ import annotations

import hmac
from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import settings

_bearer = HTTPBearer(auto_error=False)

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail={"error": "Unauthorized"},
    headers={"WWW-Authenticate": "Bearer"},
)


def _constant_time_key_check(candidate: str) -> bool:
    """Return True if candidate matches any configured API key.

    Uses hmac.compare_digest against every key so that the total
    comparison time is constant regardless of which key matched (or
    whether any matched), preventing timing oracle attacks.
    """
    matched = False
    for key in settings.api_key_set:
        # compare_digest is always constant-time per call
        if hmac.compare_digest(candidate.encode(), key.encode()):
            matched = True
        # Do NOT break early — iterate all keys every time
    return matched


async def require_api_key(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer),
) -> str:
    """FastAPI dependency. Returns the validated API key on success,
    raises 401 on missing or invalid credentials."""
    if credentials is None or not credentials.credentials:
        raise _UNAUTHORIZED
    if not _constant_time_key_check(credentials.credentials):
        raise _UNAUTHORIZED
    return credentials.credentials
