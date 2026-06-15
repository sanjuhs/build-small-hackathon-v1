#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT_DIR="$ROOT/fireboy-vla-physics/build/runpod"
OUT="$OUT_DIR/fireboy-vla-pack.tgz"

mkdir -p "$OUT_DIR"
rm -f "$OUT"

cd "$ROOT"
COPYFILE_DISABLE=1 tar \
  --no-xattrs \
  --exclude='fireboy-vla-physics/.venv' \
  --exclude='fireboy-vla-physics/build' \
  --exclude='**/__pycache__' \
  --exclude='**/._*' \
  --exclude='.git' \
  --exclude='.venv' \
  -czf "$OUT" \
  fireboy-vla-physics \
  fire-boy-rig/fire-boy-rigged-full.glb \
  pyproject.toml \
  uv.lock \
  README.md

echo "$OUT"
