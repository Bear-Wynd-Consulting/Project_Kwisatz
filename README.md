# Project_Kwisatz

Secure Docker-based Ollama + Gemma 4 API gateway — shared LLM backend for WRP applications (Open Notebook, Property Tour, Property Management).

## Architecture

```
Vercel App (server-side)
    │  Authorization: Bearer <api-key>
    ▼
nginx:80  ──►  gateway:8000 (FastAPI)  ──►  ollama:11434 (internal only)
               Auth · Rate limit              Gemma 4 model
```

- **nginx** is the only container exposed to the host — handles all inbound traffic on port 80.
- **Gateway** sits behind nginx, handling authentication and rate limiting.
- **Ollama** lives on an internal Docker network — never reachable from outside the compose stack.
- The model is persisted in a named Docker volume so it is never re-downloaded on rebuild.

> **CORS note:** WRP apps call the gateway from Vercel serverless functions (server-to-server).
> Browsers never call the gateway directly, so `ALLOWED_ORIGINS` does not affect whether
> Vercel apps can reach the gateway. It only matters if you ever add direct browser→gateway calls.

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

Edit `.env` and paste the generated keys into `API_KEYS`.

### 2. Start (CPU)

```bash
docker compose up --build
```

The first run pulls the Gemma 4 model — this may take several minutes. All traffic enters on port 80.

### 3. Start (NVIDIA GPU)

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build
```

### 4. Verify

```bash
# Gateway liveness via nginx (no auth)
curl http://localhost/health

# Model health (auth required)
curl -H "Authorization: Bearer YOUR_KEY" http://localhost/health/model

# Chat
curl -X POST http://localhost/v1/chat/completions \
  -H "Authorization: Bearer YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Hello!"}]}'
```

## WRP App Integration (Vercel)

Call the gateway from a Vercel API route (serverless function) — **never from browser-side code**. This keeps the API key secret and bypasses CORS entirely.

```javascript
// app/api/chat/route.js  (Next.js App Router example)
export async function POST(req) {
  const { messages } = await req.json()

  const res = await fetch(`${process.env.GATEWAY_URL}/v1/chat/completions`, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${process.env.GATEWAY_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ messages }),
  })

  return new Response(res.body, { headers: { "Content-Type": "application/json" } })
}
```

Set these in your Vercel project's **Environment Variables** (not in client-side code):

```
GATEWAY_URL=http://your-pc-ip-or-server    # port 80, no port suffix needed
GATEWAY_API_KEY=key_propertymgmt_xxx
```

You can also use the OpenAI SDK with a `base_url` override if preferred:

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://your-server/v1",
    api_key="YOUR_APP_API_KEY"
)

response = client.chat.completions.create(
    model="gemma4:e2b",
    messages=[{"role": "user", "content": "Summarize this listing..."}]
)
```

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/health` | None | Gateway liveness (nginx + gateway) |
| `GET` | `/health/model` | Bearer | Verify Ollama + model are ready |
| `POST` | `/v1/chat/completions` | Bearer | OpenAI-compatible chat (streaming supported) |
| `POST` | `/v1/generate` | Bearer | Raw Ollama text generation |
| `GET` | `/docs` | None | Interactive API docs (Swagger UI) |

## Configuration

All configuration lives in `.env` (never committed). See `.env.example` for all options.

| Variable | Default | Description |
|---|---|---|
| `API_KEYS` | — | Comma-separated API keys, one per app |
| `ALLOWED_ORIGINS` | — | CORS origin whitelist (only needed for direct browser calls) |
| `DEFAULT_MODEL` | `gemma4:e2b` | Ollama model tag |
| `RATE_LIMIT_PER_KEY` | `60/minute` | Per-app rate limit |
| `RATE_LIMIT_GLOBAL` | `200/minute` | Global rate limit |
| `NGINX_PORT` | `80` | Host port nginx listens on (public-facing) |
| `GATEWAY_PORT` | `8000` | Internal FastAPI port (not exposed to host) |
| `UVICORN_WORKERS` | `2` | Gateway worker processes (use 1 with GPU) |

## Security

- Ollama is not exposed to the host — internal Docker network only
- Gateway is not exposed to the host — only reachable via nginx
- API keys validated with constant-time comparison (prevents timing attacks)
- Per-app API keys for independent revocation
- Non-root users in all containers (`cap_drop: ALL`, `no-new-privileges`)
- Secrets via `.env` — never baked into image layers
- nginx is the only public entry point — single hardened surface
