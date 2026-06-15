#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 \"go find berry and eat it\" [extra pet_runtime.py args...]" >&2
  exit 2
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON_BIN="${PYTHON:-$ROOT/fireboy-vla-physics/.venv/bin/python}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="${PYTHON:-python3}"
fi

export PYTHONPATH="$ROOT/fireboy-vla-physics/src${PYTHONPATH:+:$PYTHONPATH}"
export MUJOCO_GL="${MUJOCO_GL:-glfw}"

cd "$ROOT"
"$PYTHON_BIN" fireboy-vla-physics/src/pet_runtime.py "$@"
