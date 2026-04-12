from __future__ import annotations

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from .config import settings


def _key_from_api_key(request: Request) -> str:
    """Use the API key as the rate-limit identity so that limits are
    per-application, not per-IP. Falls back to IP for unauthenticated
    requests (e.g. /health)."""
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
        if token:
            return f"key:{token}"
    return get_remote_address(request)


# Module-level limiter — imported by routes
limiter = Limiter(
    key_func=_key_from_api_key,
    default_limits=[settings.RATE_LIMIT_GLOBAL],
)
