"""Generate fal SAM 3D Object GLBs for the v2 Tiny Toybox part references.

Run from the project root with the fal-authenticated Python install:

    /Library/Frameworks/Python.framework/Versions/3.14/bin/python3 scripts/generate_sam_part_models.py

Outputs:
    assets/generated/part-models/raw/<character>/<part-id>-sam.glb
    assets/generated/part-models/raw/<character>/<part-id>-sam-result.json
    assets/generated/part-models/sam-part-inputs.json
"""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import subprocess
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import fal.apps
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "assets" / "generated" / "part-concepts" / "parts-manifest.json"
OUTPUT_ROOT = ROOT / "assets" / "generated" / "part-models"
RAW_ROOT = OUTPUT_ROOT / "raw"
INPUT_INDEX = OUTPUT_ROOT / "sam-part-inputs.json"
MODEL_ID = "fal-ai/sam-3/3d-objects"


DESCRIPTIONS = {
    "squeaky-base-body": (
        "standing unclothed chibi plush elephant base body with soft gray fabric, "
        "round ears, short trunk, stubby arms and feet, embroidered friendly face, "
        "no hat, no backpack, no clock"
    ),
    "squeaky-bowler-hat": (
        "small black bowler hat for a chibi plush elephant toy, rounded crown, "
        "short brim, simple clean toy accessory"
    ),
    "squeaky-book-backpack": (
        "cute book backpack made from stacked storybooks with straps, compact toy "
        "prop for a plush character"
    ),
    "squeaky-pocket-clock": (
        "round golden pocket clock toy prop with a small loop and chain detail, "
        "readable clock face, chibi accessory scale"
    ),
    "electraica-base-body": (
        "standing unclothed chibi electric plush girl base body with teal and cream "
        "fabric, simple closed crescent embroidered eyes, stubby arms and feet, no "
        "bulb, no battery backpack, no nut, no bolt, no chest plate"
    ),
    "electraica-bulb-head": (
        "always-on light bulb head accessory for a chibi electric plush character, "
        "warm glowing bulb with small base cap, toy-like rounded form"
    ),
    "electraica-battery-backpack": (
        "small electric battery backpack toy prop with rounded corners, visible plus "
        "and minus markings, straps, teal and yellow accents"
    ),
    "electraica-hex-nut": (
        "single oversized hex nut hand prop for a chibi plush electrician, metallic "
        "but soft toy styling, central hole clearly visible"
    ),
    "electraica-bolt": (
        "single oversized bolt hand prop for a chibi plush electrician, short screw "
        "thread and hex head, toy-like rounded edges"
    ),
    "electraica-chest-plate": (
        "small lightning chest plate clothing accessory for a chibi electric plush "
        "character, simple shield shape with yellow lightning emblem"
    ),
    "fire-boy-base-body": (
        "standing unclothed chibi plush fire boy base body with red fabric body, "
        "flame-shaped head, cream face, embroidered smile, stubby arms and feet, no "
        "tuxedo, no extinguisher, no flute, no strap"
    ),
    "fire-boy-tuxedo": (
        "tiny black tuxedo jacket clothing layer for a chibi plush fire character, "
        "white shirt front, small black tie, rounded soft fabric"
    ),
    "fire-boy-extinguisher-backpack": (
        "small red fire extinguisher backpack toy prop with hose detail and straps, "
        "rounded plush-safe shapes"
    ),
    "fire-boy-flute": (
        "small golden flute hand prop for a chibi plush musician, simple cylinder "
        "with finger holes, toy accessory scale"
    ),
    "fire-boy-shoulder-strap": (
        "single diagonal shoulder strap accessory for a chibi plush character, soft "
        "black band with simple buckles"
    ),
    "shark-girl-base-body": (
        "standing unclothed chibi plush shark girl base body with blue-gray shark "
        "hood, fins and tail, cream face and belly, embroidered sweet face, no tie, "
        "no starfish clip, no guitar, no strap"
    ),
    "shark-girl-cream-bowtie": (
        "cream-colored butler bow tie clothing accessory for a chibi plush shark "
        "character, small formal bow with soft fabric folds"
    ),
    "shark-girl-starfish-clip": (
        "small peach starfish hair clip accessory for a chibi plush shark character, "
        "rounded five-arm star shape"
    ),
    "shark-girl-guitar": (
        "small cute guitar toy prop for a chibi plush shark character, rounded body, "
        "short neck, visible strings, warm wood color"
    ),
    "shark-girl-guitar-strap": (
        "single guitar strap accessory for a chibi plush shark character, soft narrow "
        "band with small attachment loops"
    ),
}


@dataclass(frozen=True)
class PartSpec:
    id: str
    character_slug: str
    character_name: str
    name: str
    kind: str
    attach: str
    image: Path
    prompt: str

    @property
    def output_glb(self) -> Path:
        return RAW_ROOT / self.character_slug / f"{self.id}-sam.glb"

    @property
    def metadata_path(self) -> Path:
        return RAW_ROOT / self.character_slug / f"{self.id}-sam-result.json"


def data_url(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def repo_path_from_asset_url(url: str) -> Path:
    prefix = "/toy-assets/"
    if not url.startswith(prefix):
        raise ValueError(f"Expected a /toy-assets/ URL, got {url}")
    return ROOT / "assets" / url.removeprefix(prefix)


def prompt_for(item_id: str, name: str, kind: str, character_name: str) -> str:
    description = DESCRIPTIONS.get(
        item_id,
        f"{name} {kind} for the chibi plush character {character_name}",
    )
    return (
        f"{description}. Isolated centered subject on a plain light background, "
        "single complete object, cute chibi toy proportions, clean readable silhouette, "
        "soft rounded forms, textured GLB suitable for later Blender cleanup, no extra "
        "objects, no text, no scene."
    )


def estimate_box_prompt(path: Path, padding_ratio: float = 0.04) -> dict[str, int]:
    """Estimate a foreground box for opaque generated images on a plain background."""
    image = Image.open(path).convert("RGB")
    width, height = image.size
    pixels = image.load()

    samples: list[tuple[int, int, int]] = []
    step = max(1, min(width, height) // 80)
    for x in range(0, width, step):
        samples.append(pixels[x, 0])
        samples.append(pixels[x, height - 1])
    for y in range(0, height, step):
        samples.append(pixels[0, y])
        samples.append(pixels[width - 1, y])
    background = tuple(sorted(color[channel] for color in samples)[len(samples) // 2] for channel in range(3))

    xs: list[int] = []
    ys: list[int] = []
    threshold = 36
    for y in range(0, height, 2):
        for x in range(0, width, 2):
            red, green, blue = pixels[x, y]
            diff = abs(red - background[0]) + abs(green - background[1]) + abs(blue - background[2])
            if diff > threshold:
                xs.append(x)
                ys.append(y)

    if not xs:
        inset_x = round(width * 0.10)
        inset_y = round(height * 0.10)
        return {
            "x_min": inset_x,
            "y_min": inset_y,
            "x_max": width - inset_x,
            "y_max": height - inset_y,
        }

    padding = round(max(width, height) * padding_ratio)
    return {
        "x_min": max(0, min(xs) - padding),
        "y_min": max(0, min(ys) - padding),
        "x_max": min(width - 1, max(xs) + padding),
        "y_max": min(height - 1, max(ys) + padding),
    }


def load_specs() -> list[PartSpec]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    specs: list[PartSpec] = []
    for character in manifest["characters"]:
        character_slug = character["slug"]
        character_name = character["name"]
        pieces = [character["base"], *character["parts"]]
        for piece in pieces:
            image = repo_path_from_asset_url(piece["image"])
            item_id = piece["id"]
            specs.append(
                PartSpec(
                    id=item_id,
                    character_slug=character_slug,
                    character_name=character_name,
                    name=piece["name"],
                    kind=piece.get("kind", "base-body"),
                    attach=piece.get("attach", "Root"),
                    image=image,
                    prompt=prompt_for(
                        item_id,
                        piece["name"],
                        piece.get("kind", "base-body"),
                        character_name,
                    ),
                )
            )
    return specs


def write_input_index(specs: list[PartSpec]) -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    INPUT_INDEX.write_text(
        json.dumps(
            [
                {
                    "id": spec.id,
                    "character": spec.character_slug,
                    "name": spec.name,
                    "kind": spec.kind,
                    "attach": spec.attach,
                    "image": spec.image.relative_to(ROOT).as_posix(),
                    "prompt": spec.prompt,
                    "box_prompt": estimate_box_prompt(spec.image),
                    "output": spec.output_glb.relative_to(ROOT).as_posix(),
                    "metadata": spec.metadata_path.relative_to(ROOT).as_posix(),
                }
                for spec in specs
            ],
            indent=2,
        ),
        encoding="utf-8",
    )


def download(url: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(url) as response:
            path.write_bytes(response.read())
    except Exception:
        subprocess.run(["curl", "-fL", "--retry", "3", url, "-o", str(path)], check=True)


def download_from_metadata(spec: PartSpec) -> bool:
    if not spec.metadata_path.exists() or spec.output_glb.exists():
        return spec.output_glb.exists()
    result = json.loads(spec.metadata_path.read_text(encoding="utf-8"))
    url = (result.get("model_glb") or {}).get("url")
    if not url:
        return False
    print(f"{spec.id}: recovering download from saved metadata")
    download(url, spec.output_glb)
    return True


def generate(spec: PartSpec, force: bool) -> Path:
    if not spec.image.exists():
        raise FileNotFoundError(spec.image)

    if download_from_metadata(spec) and not force:
        print(f"{spec.id}: already exists at {spec.output_glb}")
        return spec.output_glb
    if spec.output_glb.exists() and not force:
        print(f"{spec.id}: already exists at {spec.output_glb}")
        return spec.output_glb

    spec.output_glb.parent.mkdir(parents=True, exist_ok=True)
    spec.metadata_path.parent.mkdir(parents=True, exist_ok=True)

    box_prompt = estimate_box_prompt(spec.image)
    params: dict[str, Any] = {
        "image_url": data_url(spec.image),
        "prompt": spec.prompt,
        "point_prompts": [],
        "box_prompts": [box_prompt],
        "detection_threshold": 0.1,
        "export_textured_glb": True,
    }

    def submit_and_fetch(request_params: dict[str, Any]) -> dict[str, Any]:
        print(f"{spec.id}: submitting to {MODEL_ID}")
        handle = fal.apps.submit(MODEL_ID, request_params)
        print(f"{spec.id}: request_id={handle.request_id}")
        for event in handle.iter_events(logs=True):
            print(f"{spec.id}: {type(event).__name__}")
        return handle.fetch_result()

    try:
        result = submit_and_fetch(params)
    except Exception as exc:
        if "Auto-segmentation produced no masks" not in str(exc):
            raise
        print(f"{spec.id}: retrying with expanded box prompt after no-mask response")
        retry_params = params | {
            "prompt": "single isolated object",
            "box_prompts": [estimate_box_prompt(spec.image, padding_ratio=0.10)],
        }
        result = submit_and_fetch(retry_params)

    spec.metadata_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    url = (result.get("model_glb") or {}).get("url")
    if not url:
        raise RuntimeError(f"{spec.id}: fal result did not include model_glb.url")
    download(url, spec.output_glb)
    print(f"{spec.id}: saved {spec.output_glb}")
    return spec.output_glb


def select_specs(specs: list[PartSpec], requested: list[str], bases_only: bool, parts_only: bool) -> list[PartSpec]:
    selected = specs
    if bases_only:
        selected = [spec for spec in selected if spec.kind == "base-body"]
    if parts_only:
        selected = [spec for spec in selected if spec.kind != "base-body"]
    if requested:
        wanted = set(requested)
        selected = [
            spec
            for spec in selected
            if spec.id in wanted or spec.character_slug in wanted or f"{spec.character_slug}/{spec.id}" in wanted
        ]
    return selected


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Regenerate even if an output GLB already exists.")
    parser.add_argument("--bases-only", action="store_true", help="Generate only the four standing base bodies.")
    parser.add_argument("--parts-only", action="store_true", help="Generate only clothing, backpacks, and props.")
    parser.add_argument("ids", nargs="*", help="Optional part ids or character slugs to generate.")
    args = parser.parse_args()

    if args.bases_only and args.parts_only:
        raise SystemExit("Use either --bases-only or --parts-only, not both.")

    specs = load_specs()
    selected = select_specs(specs, args.ids, args.bases_only, args.parts_only)
    if not selected:
        raise SystemExit("No matching part specs selected.")

    write_input_index(specs)
    print(f"Prepared {len(selected)} SAM jobs from {MANIFEST_PATH.relative_to(ROOT)}")
    for index, spec in enumerate(selected, start=1):
        print(f"[{index}/{len(selected)}] {spec.character_slug}/{spec.id}: {spec.name}")
        generate(spec, args.force)


if __name__ == "__main__":
    main()
