#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON_BIN="${PYTHON:-$ROOT/fireboy-vla-physics/.venv/bin/python}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="${PYTHON:-python3}"
fi

export PYTHONPATH="$ROOT/fireboy-vla-physics/src${PYTHONPATH:+:$PYTHONPATH}"
export MUJOCO_GL="${MUJOCO_GL:-glfw}"

cd "$ROOT"
"$PYTHON_BIN" fireboy-vla-physics/src/submission_check.py "$@"
