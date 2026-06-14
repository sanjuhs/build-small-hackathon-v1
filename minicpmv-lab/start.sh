#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

export MINICPMV_MODEL="${MINICPMV_MODEL:-minicpm-v4.6}"
export MINICPMV_OLLAMA_URL="${MINICPMV_OLLAMA_URL:-http://127.0.0.1:11434}"
export MINICPMV_PORT="${MINICPMV_PORT:-65446}"

if ! command -v ollama >/dev/null 2>&1; then
  echo "Ollama is required. Install/update Ollama, then rerun this script."
  exit 1
fi

if ! curl -fsS "$MINICPMV_OLLAMA_URL/api/version" >/dev/null 2>&1; then
  echo "Ollama is not responding at $MINICPMV_OLLAMA_URL."
  echo "Start Ollama, then rerun this script."
  exit 1
fi

echo "MiniCPM-V Lab"
echo "  model: $MINICPMV_MODEL"
echo "  ollama: $MINICPMV_OLLAMA_URL"
echo "  url: http://127.0.0.1:$MINICPMV_PORT"

uv run \
  --with fastapi \
  --with 'uvicorn[standard]' \
  --with httpx \
  --with python-multipart \
  --with pymupdf \
  --with pillow \
  python server.py
