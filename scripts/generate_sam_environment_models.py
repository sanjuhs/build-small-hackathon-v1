"""Generate fal SAM 3D Object GLBs for Tiny Toybox room props.

Run from the project root:

    python3 scripts/generate_sam_environment_models.py berry-rose

Outputs:
    assets/generated/environment-models/raw/<object-id>-sam.glb
    assets/generated/environment-models/raw/<object-id>-sam-result.json
    assets/generated/environment-models/sam-environment-inputs.json
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
MANIFEST_PATH = ROOT / "assets" / "generated" / "environment-concepts" / "environment-manifest.json"
OUTPUT_ROOT = ROOT / "assets" / "generated" / "environment-models"
RAW_ROOT = OUTPUT_ROOT / "raw"
INPUT_INDEX = OUTPUT_ROOT / "sam-environment-inputs.json"
MODEL_ID = "fal-ai/sam-3/3d-objects"


@dataclass(frozen=True)
class EnvironmentSpec:
    id: str
    name: str
    kind: str
    image: Path
    prompt: str
    affordances: list[str]
    tags: list[str]

    @property
    def output_glb(self) -> Path:
        return RAW_ROOT / f"{self.id}-sam.glb"

    @property
    def metadata_path(self) -> Path:
        return RAW_ROOT / f"{self.id}-sam-result.json"


def data_url(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def repo_path_from_asset_url(url: str) -> Path:
    prefix = "/toy-assets/"
    if not url.startswith(prefix):
        raise ValueError(f"Expected a /toy-assets/ URL, got {url}")
    return ROOT / "assets" / url.removeprefix(prefix)


def full_prompt(item: dict[str, Any]) -> str:
    base = str(item.get("prompt") or item.get("name") or item.get("id"))
    return (
        f"{base}. Isolated centered subject on a plain light background, single complete object, "
        "cute chibi toy proportions, soft rounded forms, clean readable silhouette, textured GLB "
        "suitable for a Three.js virtual pet room, no extra objects, no text, no scene."
    )


def estimate_box_prompt(path: Path, padding_ratio: float = 0.04) -> dict[str, int]:
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


def load_specs() -> list[EnvironmentSpec]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    specs: list[EnvironmentSpec] = []
    for item in manifest["objects"]:
        specs.append(
            EnvironmentSpec(
                id=item["id"],
                name=item["name"],
                kind=item["kind"],
                image=repo_path_from_asset_url(item["image"]),
                prompt=full_prompt(item),
                affordances=[str(value) for value in item.get("affordances", [])],
                tags=[str(value) for value in item.get("tags", [])],
            )
        )
    return specs


def write_input_index(specs: list[EnvironmentSpec]) -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    INPUT_INDEX.write_text(
        json.dumps(
            [
                {
                    "id": spec.id,
                    "name": spec.name,
                    "kind": spec.kind,
                    "image": spec.image.relative_to(ROOT).as_posix(),
                    "prompt": spec.prompt,
                    "box_prompt": estimate_box_prompt(spec.image),
                    "affordances": spec.affordances,
                    "tags": spec.tags,
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


def download_from_metadata(spec: EnvironmentSpec) -> bool:
    if not spec.metadata_path.exists() or spec.output_glb.exists():
        return spec.output_glb.exists()
    result = json.loads(spec.metadata_path.read_text(encoding="utf-8"))
    url = (result.get("model_glb") or {}).get("url")
    if not url:
        return False
    print(f"{spec.id}: recovering download from saved metadata")
    download(url, spec.output_glb)
    return True


def generate(spec: EnvironmentSpec, force: bool, prepare_only: bool) -> Path:
    if not spec.image.exists():
        raise FileNotFoundError(spec.image)

    if prepare_only:
        return spec.output_glb
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


def select_specs(specs: list[EnvironmentSpec], requested: list[str]) -> list[EnvironmentSpec]:
    if not requested:
        return specs
    wanted = set(requested)
    return [spec for spec in specs if spec.id in wanted or spec.kind in wanted]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Regenerate even if an output GLB already exists.")
    parser.add_argument("--prepare-only", action="store_true", help="Write the SAM input index without submitting jobs.")
    parser.add_argument("ids", nargs="*", help="Optional object ids or kinds to generate.")
    args = parser.parse_args()

    specs = load_specs()
    selected = select_specs(specs, args.ids)
    if not selected:
        raise SystemExit("No matching environment object specs selected.")

    write_input_index(specs)
    print(f"Prepared {len(selected)} SAM jobs from {MANIFEST_PATH.relative_to(ROOT)}")
    for index, spec in enumerate(selected, start=1):
        print(f"[{index}/{len(selected)}] {spec.id}")
        generate(spec, force=args.force, prepare_only=args.prepare_only)


if __name__ == "__main__":
    main()
