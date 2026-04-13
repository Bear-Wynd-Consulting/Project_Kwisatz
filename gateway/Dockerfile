# =============================================================================
# Multi-stage build — keeps the final image small and secrets-free
# =============================================================================

# Stage 1: build dependencies into an isolated venv
FROM python:3.11-slim AS builder

WORKDIR /build

COPY requirements.txt .
RUN python -m venv /venv \
    && /venv/bin/pip install --no-cache-dir --upgrade pip \
    && /venv/bin/pip install --no-cache-dir -r requirements.txt

# =============================================================================
# Stage 2: lean runtime image
FROM python:3.11-slim AS runtime

# Create non-root user
RUN groupadd --gid 1001 appgroup \
    && useradd --uid 1001 --gid appgroup --no-create-home --shell /sbin/nologin appuser

# Copy the venv from the builder stage
COPY --from=builder /venv /venv

# Copy application code
WORKDIR /app
COPY app/ ./app/

# Ensure the venv is on PATH
ENV PATH="/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

USER appuser

EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${UVICORN_WORKERS:-2}"]
