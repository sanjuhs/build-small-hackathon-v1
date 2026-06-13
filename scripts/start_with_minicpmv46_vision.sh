#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

TEXT_MODEL="${TOYBOX_LLM_MODEL:-hf.co/openbmb/MiniCPM5-1B-GGUF:Q4_K_M}"
VISION_MODEL="${TOYBOX_VISION_MODEL:-hf.co/ggml-org/MiniCPM-V-4.6-GGUF:Q4_K_M}"
OLLAMA_ENDPOINT="${OLLAMA_ENDPOINT:-http://127.0.0.1:11434}"
MIN_OLLAMA_VERSION="${MIN_OLLAMA_VERSION:-0.30.0}"

if ! command -v ollama >/dev/null 2>&1; then
  echo "Ollama is required for local MiniCPM text+vision mode."
  exit 1
fi

ollama_version="$(ollama --version | grep -Eo '[0-9]+[.][0-9]+[.][0-9]+' | head -n 1)"
ollama_version="${ollama_version:-0.0.0}"
version_at_least() {
  local current="$1"
  local minimum="$2"
  local c1 c2 c3 m1 m2 m3
  IFS=. read -r c1 c2 c3 <<<"$current"
  IFS=. read -r m1 m2 m3 <<<"$minimum"
  c1="${c1:-0}"; c2="${c2:-0}"; c3="${c3:-0}"
  m1="${m1:-0}"; m2="${m2:-0}"; m3="${m3:-0}"
  ((10#$c1 > 10#$m1)) && return 0
  ((10#$c1 < 10#$m1)) && return 1
  ((10#$c2 > 10#$m2)) && return 0
  ((10#$c2 < 10#$m2)) && return 1
  ((10#$c3 >= 10#$m3))
}

if ! version_at_least "$ollama_version" "$MIN_OLLAMA_VERSION"; then
  echo "MiniCPM-V 4.6 requires Ollama $MIN_OLLAMA_VERSION or newer for local vision."
  echo "Installed: $ollama_version"
  echo "Update Ollama, then rerun this script."
  exit 1
fi

if ! curl -fsS "$OLLAMA_ENDPOINT/api/tags" >/dev/null 2>&1; then
  echo "Ollama is not responding at $OLLAMA_ENDPOINT."
  echo "Start Ollama first, then rerun this script."
  exit 1
fi

ollama pull "$TEXT_MODEL"
ollama pull "$VISION_MODEL"

export TOYBOX_LLM_ENDPOINT="$OLLAMA_ENDPOINT/v1/chat/completions"
export TOYBOX_LLM_MODEL="$TEXT_MODEL"
export TOYBOX_VISION_ENDPOINT="$OLLAMA_ENDPOINT/api/chat"
export TOYBOX_VISION_MODEL="$VISION_MODEL"
export TOYBOX_TRACE="${TOYBOX_TRACE:-1}"

./start.sh
