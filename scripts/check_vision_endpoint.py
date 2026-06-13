from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.vision_policy import try_vision_perception


SINGLE_PIXEL_PNG = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)

payload = {
    "pet": "squeaky",
    "message": "inspect the room camera",
    "cameraFrame": SINGLE_PIXEL_PNG,
}

os.environ.setdefault("TOYBOX_VISION_DEBUG", "1")
vision = try_vision_perception(payload)
print(json.dumps({"vision": vision}, indent=2))
if vision is None:
    print("Vision endpoint did not return perception. Check model name, runtime support, and Ollama version.", file=sys.stderr)
    sys.exit(1)
