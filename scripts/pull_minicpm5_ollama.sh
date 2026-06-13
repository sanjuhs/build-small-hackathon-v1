#!/usr/bin/env bash
set -euo pipefail

MODEL="${TOYBOX_LLM_MODEL:-hf.co/openbmb/MiniCPM5-1B-GGUF:Q4_K_M}"

if ! command -v ollama >/dev/null 2>&1; then
  echo "Ollama is required for this script."
  exit 1
fi

ollama pull "$MODEL"

