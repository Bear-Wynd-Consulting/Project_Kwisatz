# Project_Kwisatz

Secure Docker-based Ollama + Gemma 4 API gateway — shared LLM backend for WRP applications (Open Notebook, Property Tour, Property Management).

## Architecture

```
WRP Apps  ──►  gateway:8000 (FastAPI)  ──►  ollama:11434 (internal only)
               Auth · Rate limit · CORS       Gemma 4 model
```

- **Gateway** is the only container exposed to the host. It handles authentication, rate limiting, and CORS.
- **Ollama** lives on an internal Docker network — never reachable from outside the compose stack.
- The model is persisted in a named Docker volume so it is never re-downloaded on rebuild.

## Quick Start

### 1. Configure

```bash
cp .env.example .env
```

Generate one API key per WRP app:

```bash
bash scripts/generate-api-key.sh open-notebook
bash scripts/generate-api-key.sh property-tour
bash scripts/generate-api-key.sh property-mgmt
```

Edit `.env` and fill in `API_KEYS` and `ALLOWED_ORIGINS`.

### 2. Start (CPU)

```bash
docker compose up --build
```

The first run pulls the Gemma 4 model — this may take several minutes.

### 3. Start (NVIDIA GPU)

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build
```

### 4. Verify

```bash
# Gateway liveness (no auth)
curl http://localhost:8000/health

# Model health (auth required)
curl -H "Authorization: Bearer YOUR_KEY" http://localhost:8000/health/model

# Chat
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Hello!"}]}'
```

## WRP App Integration

Use the OpenAI Python/JS SDK with a `base_url` override — no custom client needed:

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://your-server:8000/v1",
    api_key="YOUR_APP_API_KEY"
)

# Non-streaming
response = client.chat.completions.create(
    messages=[{"role": "user", "content": "Summarize this listing..."}]
)

# Streaming
stream = client.chat.completions.create(
    messages=[{"role": "user", "content": "Describe this property..."}],
    stream=True,
)
for chunk in stream:
    print(chunk.choices[0].delta.content or "", end="", flush=True)
```

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/health` | None | Gateway liveness (for Docker/load balancers) |
| `GET` | `/health/model` | Bearer | Verify Ollama + model are ready |
| `POST` | `/v1/chat/completions` | Bearer | OpenAI-compatible chat (streaming supported) |
| `POST` | `/v1/generate` | Bearer | Raw Ollama text generation |
| `GET` | `/docs` | None | Interactive API docs (Swagger UI) |

## Configuration

All configuration lives in `.env` (never committed). See `.env.example` for all options.

| Variable | Default | Description |
|---|---|---|
| `API_KEYS` | — | Comma-separated API keys, one per app |
| `ALLOWED_ORIGINS` | — | CORS origin whitelist |
| `DEFAULT_MODEL` | `gemma4:latest` | Ollama model tag |
| `RATE_LIMIT_PER_KEY` | `60/minute` | Per-app rate limit |
| `RATE_LIMIT_GLOBAL` | `200/minute` | Global rate limit |
| `GATEWAY_PORT` | `8000` | Host port for the gateway |
| `UVICORN_WORKERS` | `2` | Gateway worker processes (use 1 with GPU) |

## Security

- Ollama is not exposed to the host — internal Docker network only
- API keys validated with constant-time comparison (prevents timing attacks)
- Per-app API keys for independent revocation
- CORS enforced with explicit origin whitelist
- Non-root users in all containers (`cap_drop: ALL`, `no-new-privileges`)
- Secrets via `.env` — never baked into image layers
