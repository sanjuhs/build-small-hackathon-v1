#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

MODEL="${TOYBOX_LLM_MODEL:-hf.co/openbmb/MiniCPM5-1B-GGUF:Q4_K_M}"
ENDPOINT="${TOYBOX_LLM_ENDPOINT:-http://127.0.0.1:11434/v1/chat/completions}"

if ! command -v ollama >/dev/null 2>&1; then
  echo "Ollama is required for MiniCPM5 local mode."
  exit 1
fi

if ! curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
  echo "Ollama is not responding on 127.0.0.1:11434."
  echo "Start Ollama first, then rerun this script."
  exit 1
fi

ollama pull "$MODEL"

export TOYBOX_LLM_ENDPOINT="$ENDPOINT"
export TOYBOX_LLM_MODEL="$MODEL"
export TOYBOX_TRACE="${TOYBOX_TRACE:-1}"

./start.sh

