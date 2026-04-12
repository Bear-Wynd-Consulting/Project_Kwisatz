from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from ..auth import require_api_key
from ..config import settings

router = APIRouter(tags=["health"])


@router.get("/health", summary="Gateway liveness check (no auth required)")
async def health():
    """Returns 200 when the gateway process is running.
    Safe to use as a Docker health check or load balancer probe."""
    return {"status": "ok", "version": "1.0.0"}


@router.get(
    "/health/model",
    summary="Verify Ollama model is loaded (auth required)",
    dependencies=[Depends(require_api_key)],
)
async def health_model():
    """Pings Ollama and confirms the configured model is available."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
            r.raise_for_status()
            data = r.json()
    except httpx.TransportError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "Ollama is unreachable", "detail": str(exc)},
        )
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "Ollama returned an error", "detail": str(exc)},
        )

    models = [m.get("name", "") for m in data.get("models", [])]
    model_ready = any(settings.DEFAULT_MODEL in m for m in models)

    return JSONResponse(
        status_code=200 if model_ready else 503,
        content={
            "status": "ready" if model_ready else "model_not_loaded",
            "default_model": settings.DEFAULT_MODEL,
            "available_models": models,
        },
    )
