#!/bin/bash
# Generate a cryptographically secure API key for a WRP app.
# Usage: bash scripts/generate-api-key.sh [app-name]
#
# Example:
#   bash scripts/generate-api-key.sh open-notebook
#   bash scripts/generate-api-key.sh property-tour
#   bash scripts/generate-api-key.sh property-mgmt

APP="${1:-app}"
KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
echo ""
echo "API key for '${APP}':"
echo "  ${KEY}"
echo ""
echo "Add to .env:"
echo "  API_KEYS=...existing...,${KEY}"
echo ""
echo "Set in the WRP app:"
echo "  LLM_API_KEY=${KEY}"
echo ""
