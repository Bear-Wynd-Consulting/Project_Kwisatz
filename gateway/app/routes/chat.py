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

logger = logging.getLogger("kwisatz.gateway.chat")

router = APIRouter(tags=["chat"])


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[Message]
    model: str | None = Field(default=None, description="Ollama model tag. Defaults to DEFAULT_MODEL.")
    stream: bool = False
    temperature: float | None = None
    top_p: float | None = None
    top_k: int | None = None
    max_tokens: int | None = None
    options: dict[str, Any] | None = None


def _build_ollama_payload(req: ChatRequest) -> dict:
    """Translate the OpenAI-compatible request to Ollama's /api/chat format."""
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
        "messages": [m.model_dump() for m in req.messages],
        "stream": req.stream,
    }
    if options:
        payload["options"] = options
    return payload


async def _stream_ollama(ollama_url: str, payload: dict) -> AsyncGenerator[str, None]:
    """Yield SSE-formatted chunks from Ollama's streaming NDJSON response."""
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

                # Translate Ollama chunk → OpenAI SSE chunk format
                delta_content = chunk.get("message", {}).get("content", "")
                done = chunk.get("done", False)

                sse_chunk = {
                    "object": "chat.completion.chunk",
                    "model": chunk.get("model", payload["model"]),
                    "choices": [
                        {
                            "index": 0,
                            "delta": {"content": delta_content} if delta_content else {},
                            "finish_reason": "stop" if done else None,
                        }
                    ],
                }
                yield f"data: {json.dumps(sse_chunk)}\n\n"

                if done:
                    yield "data: [DONE]\n\n"
                    return


@router.post(
    "/chat/completions",
    summary="OpenAI-compatible chat completions",
)
@limiter.limit(settings.RATE_LIMIT_PER_KEY)
async def chat_completions(
    request: Request,
    body: ChatRequest,
    _api_key: str = Depends(require_api_key),
):
    """Proxy chat completions to Ollama.

    Compatible with the OpenAI Python/JS SDK when `base_url` is set to
    this gateway's URL. Set `stream=true` for streaming SSE responses.
    """
    ollama_url = f"{settings.OLLAMA_BASE_URL}/api/chat"
    payload = _build_ollama_payload(body)

    if body.stream:
        return StreamingResponse(
            _stream_ollama(ollama_url, payload),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    # Non-streaming — await the full response
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            r = await client.post(ollama_url, json=payload)
            r.raise_for_status()
            data = r.json()
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

    # Translate Ollama response → OpenAI-compatible format
    message = data.get("message", {})
    return {
        "object": "chat.completion",
        "model": data.get("model", payload["model"]),
        "choices": [
            {
                "index": 0,
                "message": message,
                "finish_reason": "stop" if data.get("done") else "length",
            }
        ],
        "usage": {
            "prompt_tokens": data.get("prompt_eval_count", 0),
            "completion_tokens": data.get("eval_count", 0),
            "total_tokens": data.get("prompt_eval_count", 0) + data.get("eval_count", 0),
        },
    }
