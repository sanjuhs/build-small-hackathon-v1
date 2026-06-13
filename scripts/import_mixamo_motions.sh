#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
blender --background --python scripts/import_mixamo_motions_blender.py
