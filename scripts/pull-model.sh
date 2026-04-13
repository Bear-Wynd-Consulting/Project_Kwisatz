#!/bin/bash
# Pull a model into the running Ollama container.
# Usage: bash scripts/pull-model.sh [model-tag]
#
# Examples:
#   bash scripts/pull-model.sh gemma4:latest
#   bash scripts/pull-model.sh gemma3:12b

MODEL="${1:-${DEFAULT_MODEL:-gemma4:latest}}"

echo "Pulling model '${MODEL}' into kwisatz-ollama container..."
docker exec kwisatz-ollama ollama pull "${MODEL}"
echo "Done."
