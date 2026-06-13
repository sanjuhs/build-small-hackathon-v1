"""Generate fal SAM 3D Object GLBs for Tiny Toybox source images.

This uses fal's installed Python package and sends source images as data URLs,
which avoids needing `fal files upload` permissions.

Run from the project root:

    /Library/Frameworks/Python.framework/Versions/3.14/bin/python3 scripts/generate_sam_3d_models.py
"""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import shutil
import subprocess
import urllib.request
from pathlib import Path

import fal.apps


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "potential-char-images"
RAW_DIR = SOURCE_DIR / "extracted-from-sam"


CHARACTERS = {
    "squeaky": {
        "image": SOURCE_DIR / "squeaky.png",
        "prompt": "plushie squeaky elephant with bowler hat, books backpack, pocket clock, cute chibi toy character",
    },
    "electraica": {
        "image": SOURCE_DIR / "electraica-(her).png",
        "prompt": "plushie Electraica electric helper character, bulb on head, battery pack, nut and bolt hands, cute chibi toy character",
    },
    "fire-boy": {
        "image": SOURCE_DIR / "fire-boy.png",
        "prompt": "plushie Fire Boy character, flame hood, tuxedo, fire extinguisher backpack, flute, cute chibi toy character",
    },
    "shark-girl": {
        "image": SOURCE_DIR / "shark-girl.png",
        "prompt": "plushie Shark Girl character, shark hood, cream butler tie, guitar, cute chibi toy character",
    },
}


def data_url(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def download(url: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(url) as response:
            path.write_bytes(response.read())
    except Exception:
        subprocess.run(["curl", "-fL", url, "-o", str(path)], check=True)


def download_from_metadata(metadata: Path, output: Path) -> bool:
    if not metadata.exists() or output.exists():
        return output.exists()
    result = json.loads(metadata.read_text(encoding="utf-8"))
    url = (result.get("model_glb") or {}).get("url")
    if not url:
        return False
    print(f"Recovering download from {metadata}")
    download(url, output)
    return True


def generate(slug: str, force: bool) -> Path:
    info = CHARACTERS[slug]
    image = info["image"]
    output = RAW_DIR / f"{slug}-sam.glb"
    metadata = RAW_DIR / f"{slug}-sam-result.json"
    if download_from_metadata(metadata, output) and not force:
        print(f"Skipping {slug}; recovered/exists at {output}")
        return output
    if output.exists() and not force:
        print(f"Skipping {slug}; already exists at {output}")
        return output
    if not image.exists():
        raise FileNotFoundError(image)

    params = {
        "image_url": data_url(image),
        "prompt": info["prompt"],
        "export_textured_glb": True,
    }
    print(f"Submitting {slug} to fal-ai/sam-3/3d-objects")
    handle = fal.apps.submit("fal-ai/sam-3/3d-objects", params)
    print(f"{slug}: request_id={handle.request_id}")
    for event in handle.iter_events(logs=True):
        print(f"{slug}: {type(event).__name__}")
    result = handle.fetch_result()
    metadata.write_text(json.dumps(result, indent=2), encoding="utf-8")

    glb = result.get("model_glb") or {}
    url = glb.get("url")
    if not url:
        raise RuntimeError(f"{slug}: fal result did not include model_glb.url")
    download(url, output)
    print(f"Saved {slug}: {output}")
    return output


def seed_existing_fire_boy() -> None:
    existing = RAW_DIR / "combined_scene (2).glb"
    normalized = RAW_DIR / "fire-boy-sam.glb"
    if existing.exists() and not normalized.exists():
        shutil.copy2(existing, normalized)
        print(f"Seeded fire-boy from existing SAM export: {normalized}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Regenerate even if the named GLB already exists.")
    parser.add_argument("slugs", nargs="*", choices=sorted(CHARACTERS), help="Specific characters to generate.")
    args = parser.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    seed_existing_fire_boy()

    slugs = args.slugs or list(CHARACTERS)
    for slug in slugs:
        generate(slug, args.force)


if __name__ == "__main__":
    main()
