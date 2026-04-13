from __future__ import annotations

import json
import logging
from typing import Any, AsyncGenerator

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..auth import require_api_key
from ..config import settings
from ..rate_limit import limiter

logger = logging.getLogger("kwisatz.gateway.generate")

router = APIRouter(tags=["generate"])


class GenerateRequest(BaseModel):
    prompt: str
    model: str | None = Field(default=None, description="Ollama model tag. Defaults to DEFAULT_MODEL.")
    system: str | None = None
    stream: bool = False
    temperature: float | None = None
    top_p: float | None = None
    top_k: int | None = None
    max_tokens: int | None = None
    options: dict[str, Any] | None = None


def _build_ollama_payload(req: GenerateRequest) -> dict:
    options: dict[str, Any] = req.options or {}
    if req.temperature is not None:
        options["temperature"] = req.temperature
    if req.top_p is not None:
        options["top_p"] = req.top_p
    if req.top_k is not None:
        options["top_k"] = req.top_k
    if req.max_tokens is not None:
        options["num_predict"] = req.max_tokens

    payload: dict[str, Any] = {
        "model": req.model or settings.DEFAULT_MODEL,
        "prompt": req.prompt,
        "stream": req.stream,
    }
    if req.system:
        payload["system"] = req.system
    if options:
        payload["options"] = options
    return payload


async def _stream_generate(ollama_url: str, payload: dict) -> AsyncGenerator[str, None]:
    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream("POST", ollama_url, json=payload) as response:
            if response.status_code != 200:
                body = await response.aread()
                yield f"data: {json.dumps({'error': body.decode()})}\n\n"
                return
            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError:
                    continue
                yield f"data: {json.dumps(chunk)}\n\n"
                if chunk.get("done"):
                    yield "data: [DONE]\n\n"
                    return


@router.post(
    "/generate",
    summary="Raw text generation (Ollama-native format)",
)
@limiter.limit(settings.RATE_LIMIT_PER_KEY)
async def generate(
    request: Request,
    body: GenerateRequest,
    _api_key: str = Depends(require_api_key),
):
    """Single-turn text completion using Ollama's native /api/generate endpoint.
    Use /v1/chat/completions for multi-turn conversations."""
    ollama_url = f"{settings.OLLAMA_BASE_URL}/api/generate"
    payload = _build_ollama_payload(body)

    if body.stream:
        return StreamingResponse(
            _stream_generate(ollama_url, payload),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            r = await client.post(ollama_url, json=payload)
            r.raise_for_status()
            return r.json()
    except httpx.TransportError as exc:
        logger.error("Ollama unreachable: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "LLM backend is unreachable"},
        )
    except httpx.HTTPStatusError as exc:
        logger.error("Ollama error %s: %s", exc.response.status_code, exc.response.text)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": "LLM backend returned an error"},
        )
