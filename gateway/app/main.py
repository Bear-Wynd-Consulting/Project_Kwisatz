from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from .config import settings
from .rate_limit import limiter
from .routes import chat, generate, health

logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger("kwisatz.gateway")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Verify Ollama is reachable before accepting traffic."""
    logger.info("Gateway starting — verifying Ollama at %s", settings.OLLAMA_BASE_URL)
    async with httpx.AsyncClient(timeout=5.0) as client:
        for attempt in range(1, 11):
            try:
                r = await client.get(f"{settings.OLLAMA_BASE_URL}/")
                if r.status_code < 500:
                    logger.info("Ollama is reachable (attempt %d).", attempt)
                    break
            except httpx.TransportError:
                pass
            if attempt == 10:
                logger.warning(
                    "Ollama not reachable after 10 attempts — starting anyway. "
                    "Requests will fail until Ollama is healthy."
                )
            import asyncio
            await asyncio.sleep(3)
    yield
    logger.info("Gateway shutting down.")


app = FastAPI(
    title="Project Kwisatz — LLM Gateway",
    version="1.0.0",
    description=(
        "Secure API gateway proxying Ollama/Gemma 4 for WRP applications. "
        "Authenticate with: Authorization: Bearer <api-key>"
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Rate limiting
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"error": "Rate limit exceeded. Slow down and retry."},
        headers={"Retry-After": str(exc.retry_after) if hasattr(exc, "retry_after") else "60"},
    )


# ---------------------------------------------------------------------------
# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# ---------------------------------------------------------------------------
# Routes
app.include_router(health.router)
app.include_router(chat.router, prefix="/v1")
app.include_router(generate.router, prefix="/v1")

logger.info(
    "Gateway ready — model=%s, origins=%s",
    settings.DEFAULT_MODEL,
    settings.allowed_origins_list,
)
