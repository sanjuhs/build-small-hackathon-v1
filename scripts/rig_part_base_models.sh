#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
blender --background --python scripts/rig_part_base_models_blender.py
