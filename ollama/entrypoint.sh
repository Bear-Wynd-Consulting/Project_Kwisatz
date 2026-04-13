#!/bin/bash
set -e

MODEL="${DEFAULT_MODEL:-gemma4:latest}"

echo "[ollama] Starting Ollama server..."
ollama serve &
OLLAMA_PID=$!

echo "[ollama] Waiting for Ollama to be ready..."
for i in $(seq 1 30); do
    if curl -sf http://localhost:11434/ > /dev/null 2>&1; then
        echo "[ollama] Ollama is ready."
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "[ollama] ERROR: Ollama did not become ready in time." >&2
        exit 1
    fi
    sleep 2
done

echo "[ollama] Checking if model '${MODEL}' is already pulled..."
if ollama list | grep -q "^${MODEL}"; then
    echo "[ollama] Model '${MODEL}' already present — skipping pull."
else
    echo "[ollama] Pulling model '${MODEL}' (this may take several minutes on first run)..."
    ollama pull "${MODEL}"
    echo "[ollama] Model pull complete."
fi

echo "[ollama] Ready to serve '${MODEL}'."

# Keep the container alive by waiting on the Ollama process
wait "$OLLAMA_PID"
