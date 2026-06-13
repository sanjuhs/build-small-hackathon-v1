#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if ! command -v blender >/dev/null 2>&1; then
  echo "blender was not found on PATH."
  echo "Expected symlink: $HOME/.local/bin/blender -> /Applications/Blender.app/Contents/MacOS/Blender"
  exit 1
fi

blender --background --python scripts/generate_character_models_blender.py

python3 - <<'PY'
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

root = Path("assets/generated/previews")
items = [
    ("Squeaky beauty", root / "squeaky-beauty.png"),
    ("Squeaky rig", root / "squeaky-rig.png"),
    ("Squeaky objects", root / "squeaky-objects.png"),
    ("Electraica beauty", root / "electraica-beauty.png"),
    ("Electraica rig", root / "electraica-rig.png"),
    ("Electraica objects", root / "electraica-objects.png"),
    ("Fire Boy beauty", root / "fire-boy-beauty.png"),
    ("Fire Boy rig", root / "fire-boy-rig.png"),
    ("Fire Boy objects", root / "fire-boy-objects.png"),
    ("Shark Girl beauty", root / "shark-girl-beauty.png"),
    ("Shark Girl rig", root / "shark-girl-rig.png"),
    ("Shark Girl objects", root / "shark-girl-objects.png"),
]

thumb_w, thumb_h = 360, 360
label_h = 38
sheet = Image.new("RGB", (thumb_w * 3, (thumb_h + label_h) * 4), (250, 246, 236))
draw = ImageDraw.Draw(sheet)
try:
    font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 19)
except Exception:
    font = None

for idx, (label, path) in enumerate(items):
    img = Image.open(path).convert("RGB")
    img.thumbnail((thumb_w, thumb_h), Image.Resampling.LANCZOS)
    row, col = divmod(idx, 3)
    x = col * thumb_w + (thumb_w - img.width) // 2
    y = row * (thumb_h + label_h)
    sheet.paste(img, (x, y))
    draw.text((col * thumb_w + 14, y + thumb_h + 8), label, fill=(24, 34, 34), font=font)

sheet.save(root / "contact-sheet.png", quality=94)
print((root / "contact-sheet.png").resolve())
PY

echo "Generated Blender previews in assets/generated/previews"
echo "Generated rigged GLBs in assets/generated/rigged"
