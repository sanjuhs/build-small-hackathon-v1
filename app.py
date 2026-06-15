from __future__ import annotations

import os
import json
import struct
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

import gradio as gr
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from src.ai_evidence import ai_evidence_status
from src.action_store import action_stats, fetch_action_events, record_pet_action
from src.articulated_fireboy_bridge import run_articulated_fireboy
from src.modal_omni_policy import warm_modal_omni_health
from src.mujoco_audit_bridge import run_mujoco_policy_audit
from src.mujoco_policy_bridge import run_mujoco_pet_action
from src.mujoco_showcase_bridge import run_mujoco_showcase
from src.pet_memory import load_memories
from src.pet_policy import choose_pet_action, model_status
from src.trace_dataset import training_dataset_jsonl, training_dataset_summary
from src.vla_router_policy import route_vla, run_vla_router_pet_action, vla_router_status


ROOT = Path(__file__).parent
FIREBOY_VLA_ROOT = ROOT / "fireboy-vla-physics"
FIREBOY_RUNPOD_ARTIFACT_ROOT = ROOT / "Fireboy-training-policy-vla" / "runpod-artifacts"

server = FastAPI(title="Tiny Toybox")
server.mount("/frontend", StaticFiles(directory=ROOT / "frontend"), name="frontend")
server.mount("/toy-assets", StaticFiles(directory=ROOT / "assets"), name="toy-assets")
if (ROOT / "fire-boy-rig").exists():
    server.mount("/fire-boy-rig", StaticFiles(directory=ROOT / "fire-boy-rig"), name="fire-boy-rig")
if (ROOT / "potential-char-images").exists():
    server.mount(
        "/potential-char-images",
        StaticFiles(directory=ROOT / "potential-char-images"),
        name="potential-char-images",
    )
if FIREBOY_VLA_ROOT.exists():
    server.mount(
        "/fireboy-vla",
        StaticFiles(directory=FIREBOY_VLA_ROOT),
        name="fireboy-vla",
    )
if FIREBOY_RUNPOD_ARTIFACT_ROOT.exists():
    server.mount(
        "/fireboy-runpod-artifacts",
        StaticFiles(directory=FIREBOY_RUNPOD_ARTIFACT_ROOT),
        name="fireboy-runpod-artifacts",
    )


@server.on_event("startup")
def warm_modal_gateway_on_startup() -> None:
    if os.getenv("TOYBOX_MODAL_OMNI_WARMUP", "1").lower() in {"0", "false", "no"}:
        return

    def warm() -> None:
        result = warm_modal_omni_health()
        if os.getenv("TOYBOX_MODAL_OMNI_DEBUG", "").lower() in {"1", "true", "yes"} and result:
            print(f"Modal MiniCPM-o warmup: {result}", flush=True)

    threading.Thread(target=warm, daemon=True).start()


CHARACTER_LABELS = {
    "squeaky": "Squeaky",
    "electraica": "Electraica",
    "fire-boy": "Fire Boy",
    "shark-girl": "Shark Girl",
}

KNOWN_CHARACTER_SLUGS = ("squeaky", "electraica", "fire-boy", "shark-girl")


def asset_url(path: Path) -> str:
    resolved = path.resolve()
    assets_root = (ROOT / "assets").resolve()
    source_root = (ROOT / "potential-char-images").resolve()
    if resolved.is_relative_to(assets_root):
        return "/toy-assets/" + quote(resolved.relative_to(assets_root).as_posix(), safe="/")
    if resolved.is_relative_to(source_root):
        return "/potential-char-images/" + quote(resolved.relative_to(source_root).as_posix(), safe="/")
    return quote(resolved.relative_to(ROOT.resolve()).as_posix(), safe="/")


def read_glb_stats(path: Path) -> dict[str, Any]:
    stats: dict[str, Any] = {
        "file_size": path.stat().st_size,
        "triangles": 0,
        "vertices": 0,
        "meshes": 0,
        "primitives": 0,
        "materials": 0,
        "textures": 0,
        "nodes": 0,
        "skins": 0,
        "animations": 0,
    }
    data = path.read_bytes()
    if len(data) < 20:
        return stats | {"error": "GLB header is too small"}

    magic, _version, _length = struct.unpack_from("<III", data, 0)
    if magic != 0x46546C67:
        return stats | {"error": "Not a binary glTF file"}

    offset = 12
    gltf: dict[str, Any] | None = None
    while offset + 8 <= len(data):
        chunk_length, chunk_type = struct.unpack_from("<II", data, offset)
        offset += 8
        chunk = data[offset: offset + chunk_length]
        offset += chunk_length
        if chunk_type == 0x4E4F534A:
            gltf = json.loads(chunk.decode("utf-8").rstrip("\x00 \n\r\t"))
            break
    if gltf is None:
        return stats | {"error": "No JSON chunk found"}

    accessors = gltf.get("accessors", [])
    meshes = gltf.get("meshes", [])
    stats.update({
        "meshes": len(meshes),
        "materials": len(gltf.get("materials", [])),
        "textures": len(gltf.get("textures", [])),
        "nodes": len(gltf.get("nodes", [])),
        "skins": len(gltf.get("skins", [])),
        "animations": len(gltf.get("animations", [])),
    })

    for mesh in meshes:
        for primitive in mesh.get("primitives", []):
            stats["primitives"] += 1
            attributes = primitive.get("attributes", {})
            position_accessor = attributes.get("POSITION")
            position_count = 0
            if isinstance(position_accessor, int) and position_accessor < len(accessors):
                position_count = int(accessors[position_accessor].get("count", 0))
                stats["vertices"] += position_count

            index_accessor = primitive.get("indices")
            index_count = position_count
            if isinstance(index_accessor, int) and index_accessor < len(accessors):
                index_count = int(accessors[index_accessor].get("count", 0))

            mode = primitive.get("mode", 4)
            if mode == 4:
                stats["triangles"] += index_count // 3
            elif mode in (5, 6):
                stats["triangles"] += max(0, index_count - 2)

    return stats


def infer_character_slug(path: Path, fallback_index: int = 1) -> str:
    name = path.stem.lower()
    if "squeaky" in name:
        return "squeaky"
    if "electraica" in name:
        return "electraica"
    if "fire" in name or ("combined_scene" in name and fallback_index == 1):
        return "fire-boy"
    if "shark" in name:
        return "shark-girl"
    return name.replace("_", "-").replace(" ", "-")


def collect_sam_raw_glbs(root: Path) -> list[tuple[str, Path]]:
    selected: dict[str, Path] = {}
    for slug in KNOWN_CHARACTER_SLUGS:
        named = root / f"{slug}-sam.glb"
        if named.exists():
            selected[slug] = named
    for index, path in enumerate(sorted(root.glob("*.glb")), start=1):
        slug = infer_character_slug(path, index)
        if slug in selected:
            continue
        if path.name.startswith("combined_scene") and "fire-boy" in selected:
            continue
        selected[slug] = path
    order = {slug: index for index, slug in enumerate(KNOWN_CHARACTER_SLUGS)}
    return sorted(selected.items(), key=lambda item: (order.get(item[0], 99), item[0]))


def collect_part_specs() -> dict[str, dict[str, Any]]:
    manifest_path = ROOT / "assets" / "generated" / "part-concepts" / "parts-manifest.json"
    if not manifest_path.exists():
        return {}

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    specs: dict[str, dict[str, Any]] = {}
    for character in manifest.get("characters", []):
        character_slug = character.get("slug", "")
        character_name = character.get("name", CHARACTER_LABELS.get(character_slug, character_slug.title()))
        for piece in (character.get("base"), *character.get("parts", [])):
            if not piece:
                continue
            specs[piece["id"]] = {
                "character_slug": character_slug,
                "character_name": character_name,
                "name": piece.get("name", piece["id"]),
                "kind": piece.get("kind", "base-body"),
                "attach": piece.get("attach", "Root"),
                "image": piece.get("image"),
            }
    return specs


def title_from_slug(slug: str) -> str:
    return slug.replace("-", " ").replace("_", " ").title()


def glb_asset_manifest() -> list[dict[str, Any]]:
    assets: list[dict[str, Any]] = []
    preview_root = ROOT / "assets" / "generated" / "previews"
    rigged_root = ROOT / "assets" / "generated" / "rigged"
    source_images = {
        "squeaky": ROOT / "potential-char-images" / "squeaky.png",
        "electraica": ROOT / "potential-char-images" / "electraica-(her).png",
        "fire-boy": ROOT / "potential-char-images" / "fire-boy.png",
        "shark-girl": ROOT / "potential-char-images" / "shark-girl.png",
    }

    for slug, label in CHARACTER_LABELS.items():
        path = rigged_root / f"{slug}-rigged.glb"
        if not path.exists():
            continue
        previews = []
        for kind in ("beauty", "rig", "objects"):
            image = preview_root / f"{slug}-{kind}.png"
            if image.exists():
                previews.append({"label": kind.title(), "url": asset_url(image)})
        assets.append({
            "id": f"blender-{slug}",
            "title": label,
            "character": slug,
            "version": "Blender chibi rig",
            "source": "procedural-blender",
            "url": asset_url(path),
            "path": path.relative_to(ROOT).as_posix(),
            "previews": previews,
            "stats": read_glb_stats(path),
        })

    sam_root = ROOT / "potential-char-images" / "extracted-from-sam"
    if sam_root.exists():
        for index, (slug, path) in enumerate(collect_sam_raw_glbs(sam_root), start=1):
            label = CHARACTER_LABELS.get(slug, slug.replace("-", " ").title())
            source_image = source_images.get(slug)
            previews = []
            if source_image and source_image.exists():
                previews.append({"label": "Source", "url": asset_url(source_image)})
            assets.append({
                "id": f"sam-{slug}-{index}",
                "title": label,
                "character": slug,
                "version": "SAM 3D extraction",
                "source": "fal-sam-3",
                "url": asset_url(path),
                "path": path.relative_to(ROOT).as_posix(),
                "previews": previews,
                "stats": read_glb_stats(path),
            })

    cleaned_root = ROOT / "assets" / "generated" / "sam-cleaned"
    if cleaned_root.exists():
        for path in sorted(cleaned_root.glob("*.glb")):
            slug = path.stem.replace("-sam-cleaned", "")
            label = CHARACTER_LABELS.get(slug, slug.replace("-", " ").title())
            previews = []
            cleanup_preview = preview_root / f"{slug}-sam-cleaned.png"
            if cleanup_preview.exists():
                previews.append({"label": "Clean Render", "url": asset_url(cleanup_preview)})
            source_image = source_images.get(slug)
            if source_image and source_image.exists():
                previews.append({"label": "Source", "url": asset_url(source_image)})
            assets.append({
                "id": f"sam-cleaned-{slug}",
                "title": label,
                "character": slug,
                "version": "SAM cleanup pass",
                "source": "fal-sam-3-cleaned",
                "url": asset_url(path),
                "path": path.relative_to(ROOT).as_posix(),
                "previews": previews,
                "stats": read_glb_stats(path),
            })

    rigged_root = ROOT / "assets" / "generated" / "sam-standing-rigged"
    if rigged_root.exists():
        for path in sorted(rigged_root.glob("*.glb")):
            slug = path.stem.replace("-sam-standing-rigged", "")
            label = CHARACTER_LABELS.get(slug, slug.replace("-", " ").title())
            previews = []
            standing_preview = preview_root / f"{slug}-sam-standing-rigged.png"
            rig_preview = preview_root / f"{slug}-sam-standing-rig.png"
            cleanup_preview = preview_root / f"{slug}-sam-cleaned.png"
            for preview_path, preview_label in (
                (standing_preview, "Standing"),
                (rig_preview, "Rig"),
                (cleanup_preview, "Clean Render"),
            ):
                if preview_path.exists():
                    previews.append({"label": preview_label, "url": asset_url(preview_path)})
            source_image = source_images.get(slug)
            if source_image and source_image.exists():
                previews.append({"label": "Source", "url": asset_url(source_image)})
            assets.append({
                "id": f"sam-standing-rigged-{slug}",
                "title": label,
                "character": slug,
                "version": "SAM standing rig",
                "source": "fal-sam-3-standing-rigged",
                "url": asset_url(path),
                "path": path.relative_to(ROOT).as_posix(),
                "previews": previews,
                "stats": read_glb_stats(path),
            })

    part_specs = collect_part_specs()
    base_specs = {
        spec["character_slug"]: spec
        for spec in part_specs.values()
        if spec.get("kind") == "base-body"
    }

    rigged_base_root = ROOT / "assets" / "generated" / "part-models" / "rigged-bases"
    if rigged_base_root.exists():
        for path in sorted(rigged_base_root.glob("*-base-rigged.glb")):
            slug = path.stem.replace("-base-rigged", "")
            label = CHARACTER_LABELS.get(slug, slug.replace("-", " ").title())
            spec = base_specs.get(slug, {})
            previews = []
            rig_preview = preview_root / f"{slug}-part-base-rigged.png"
            if rig_preview.exists():
                previews.append({"label": "Base Rig", "url": asset_url(rig_preview)})
            image = spec.get("image")
            if image:
                previews.append({"label": "2D Ref", "url": image})
            assets.append({
                "id": f"sam-base-rigged-{slug}",
                "title": f"{label}: Rigged base body",
                "character": slug,
                "version": "SAM v4 aligned chibi rig",
                "source": "fal-sam-3-base-rigged",
                "url": asset_url(path),
                "path": path.relative_to(ROOT).as_posix(),
                "previews": previews,
                "stats": read_glb_stats(path),
            })

    assembly_root = ROOT / "assets" / "generated" / "part-models" / "assemblies"
    if assembly_root.exists():
        for path in sorted(assembly_root.glob("*-assembled.glb")):
            slug = path.stem.replace("-assembled", "")
            label = CHARACTER_LABELS.get(slug, slug.replace("-", " ").title())
            previews = []
            assembly_preview = preview_root / f"{slug}-part-assembly.png"
            rig_preview = preview_root / f"{slug}-part-base-rigged.png"
            for preview_path, preview_label in (
                (assembly_preview, "Assembly"),
                (rig_preview, "Base Rig"),
            ):
                if preview_path.exists():
                    previews.append({"label": preview_label, "url": asset_url(preview_path)})
            assets.append({
                "id": f"sam-assembled-{slug}",
                "title": f"{label}: Socketed kit assembly",
                "character": slug,
                "version": "SAM socketed assembly",
                "source": "fal-sam-3-assembly",
                "url": asset_url(path),
                "path": path.relative_to(ROOT).as_posix(),
                "previews": previews,
                "stats": read_glb_stats(path),
            })

    mixamo_root = ROOT / "assets" / "generated" / "part-models" / "mixamo-motion-tests"
    if mixamo_root.exists():
        for path in sorted(mixamo_root.glob("*/*.glb")):
            slug = path.parent.name
            label = CHARACTER_LABELS.get(slug, title_from_slug(slug))
            prefix = f"{slug}-mixamo-"
            motion_slug = path.stem.removeprefix(prefix)
            motion_name = title_from_slug(motion_slug)
            preview_path = preview_root / f"{slug}-mixamo-{motion_slug}.png"
            previews = []
            if preview_path.exists():
                previews.append({"label": "Mixamo Render", "url": asset_url(preview_path)})
            rig_preview = preview_root / f"{slug}-part-base-rigged.png"
            if rig_preview.exists():
                previews.append({"label": "Local Rig", "url": asset_url(rig_preview)})
            assets.append({
                "id": f"mixamo-{slug}-{motion_slug}",
                "title": f"{label}: {motion_name}",
                "character": slug,
                "version": "Mixamo motion test",
                "source": "mixamo-motion-test",
                "url": asset_url(path),
                "path": path.relative_to(ROOT).as_posix(),
                "previews": previews,
                "stats": read_glb_stats(path),
            })

    part_root = ROOT / "assets" / "generated" / "part-models" / "raw"
    if part_root.exists():
        for path in sorted(part_root.glob("*/*-sam.glb")):
            part_id = path.stem.removesuffix("-sam")
            spec = part_specs.get(part_id, {})
            slug = spec.get("character_slug") or path.parent.name
            character_name = spec.get("character_name") or CHARACTER_LABELS.get(slug, slug.replace("-", " ").title())
            name = spec.get("name") or part_id.replace("-", " ").title()
            kind = spec.get("kind", "part")
            previews = []
            image = spec.get("image")
            if image:
                previews.append({"label": "2D Ref", "url": image})
            version = "SAM base body extraction" if kind == "base-body" else "SAM part extraction"
            assets.append({
                "id": f"sam-part-{part_id}",
                "title": f"{character_name}: {name}",
                "character": slug,
                "version": version,
                "source": "fal-sam-3-part",
                "url": asset_url(path),
                "path": path.relative_to(ROOT).as_posix(),
                "previews": previews,
                "kind": kind,
                "attach": spec.get("attach", "Root"),
                "stats": read_glb_stats(path),
            })

    return assets


def judge_readiness_status() -> dict[str, Any]:
    model = model_status()
    training = training_dataset_summary(limit=0)
    evidence = ai_evidence_status(limit=0)
    assets = glb_asset_manifest()
    rigged_assets = [
        asset
        for asset in assets
        if asset.get("source") == "procedural-blender" and asset.get("version") == "Blender chibi rig"
    ]
    rigged_characters = sorted({str(asset.get("character")) for asset in rigged_assets if asset.get("character")})
    total_triangles = sum(int(asset.get("stats", {}).get("triangles", 0) or 0) for asset in rigged_assets)
    total_vertices = sum(int(asset.get("stats", {}).get("vertices", 0) or 0) for asset in rigged_assets)

    checks: list[dict[str, Any]] = []

    def add_check(
        check_id: str,
        label: str,
        state: str,
        detail: str,
        category: str,
        *,
        required: bool = True,
    ) -> None:
        checks.append({
            "id": check_id,
            "label": label,
            "state": state,
            "detail": detail,
            "category": category,
            "required": required,
        })

    add_check(
        "gradio_space",
        "Gradio Space",
        "ok",
        "Docker Space serves a Gradio-mounted FastAPI app.",
        "hosting",
    )
    add_check(
        "toy_v3_route",
        "Toy Room v3 URL",
        "ok",
        "/toy and /toy-v3 serve the single Fire Boy virtual pet room.",
        "hosting",
    )
    add_check(
        "physics_room",
        "Physics toy room",
        "ok",
        "Client runtime includes a larger Cannon physics room with draggable toys and agents.",
        "gameplay",
    )
    add_check(
        "single_pet_cast",
        "Fire Boy virtual pet",
        "ok",
        "Toy Room v3 focuses on one controllable Fire Boy using the unclothed generated rig as the live body.",
        "gameplay",
    )
    add_check(
        "generated_rigs",
        "Generated GLB rigs",
        "ok" if len(rigged_characters) >= len(KNOWN_CHARACTER_SLUGS) else "warn",
        f"{len(rigged_characters)}/{len(KNOWN_CHARACTER_SLUGS)} primary rigged character meshes available.",
        "assets",
    )
    add_check(
        "trace_policy",
        "Trace policy brain",
        "ok" if model.get("tracePolicyEnabled") else "warn",
        str(model.get("fallbackPolicy") or "fallback-policy"),
        "ai",
    )
    add_check(
        "live_model_endpoint",
        "Live MiniCPM endpoint",
        "ok" if model.get("enabled") else "warn",
        (
            f"{model.get('provider') or model.get('mode')} {model.get('model')}"
            if model.get("enabled")
            else "No secret-backed endpoint configured; trace-retrieval policy is active."
        ),
        "ai",
        required=False,
    )
    add_check(
        "vision_pipeline",
        "Vision inputs",
        "ok" if model.get("visionEnabled") or model.get("tracePolicyEnabled") else "warn",
        (
            f"{model.get('visionProvider') or model.get('visionMode')} {model.get('visionModel')}"
            if model.get("visionEnabled")
            else "Browser sends camera-frame metadata and detected objects; external vision model is optional."
        ),
        "ai",
    )
    add_check(
        "training_export",
        "SFT trace export",
        "ok" if training.get("ready") else "warn",
        f"{training.get('usableRows', 0)} usable rows; target {training.get('minRows', 0)}.",
        "ai",
    )
    add_check(
        "ai_load_bearing",
        "AI load-bearing evidence",
        "ok" if evidence.get("score", {}).get("ready") else "warn",
        f"{evidence.get('score', {}).get('requiredOk', 0)}/{evidence.get('score', {}).get('requiredTotal', 0)} required evidence checks.",
        "ai",
    )
    add_check(
        "sound_layer",
        "Sound and speech",
        "ok",
        "Browser speech synthesis, procedural WebAudio, generated sound recipes, and opt-in mic summaries.",
        "media",
    )
    add_check(
        "judge_demo",
        "One-button judge demo",
        "ok",
        "Client demo exercises learning, vision council, force rescue, generated object, dialogue, charade, and recycling.",
        "polish",
    )
    add_check(
        "sharing_pack",
        "Shareable training pack",
        "ok" if training.get("downloadUrl") else "warn",
        str(training.get("downloadUrl") or "training export unavailable"),
        "sharing",
    )

    ok_count = sum(1 for check in checks if check["state"] == "ok")
    warn_count = sum(1 for check in checks if check["state"] == "warn")
    required = [check for check in checks if check.get("required")]
    required_ok = sum(1 for check in required if check["state"] == "ok")

    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "title": "Toy Room v3 judge readiness",
        "summary": "Evidence that the shipped Toy Room v3 build covers the Build Small Hackathon AI toy-box criteria.",
        "score": {
            "ok": ok_count,
            "warn": warn_count,
            "total": len(checks),
            "requiredOk": required_ok,
            "requiredTotal": len(required),
            "ready": required_ok == len(required),
        },
        "checks": checks,
        "model": model,
        "training": {
            "target": training.get("target"),
            "format": training.get("format"),
            "usableRows": training.get("usableRows", 0),
            "totalRows": training.get("totalRows", 0),
            "seedRows": training.get("seedRows", 0),
            "minRows": training.get("minRows", 0),
            "ready": training.get("ready", False),
            "downloadUrl": training.get("downloadUrl"),
            "policies": training.get("policies", {}),
            "pets": training.get("pets", {}),
            "intents": training.get("intents", {}),
        },
        "aiEvidence": {
            "score": evidence.get("score", {}),
            "metrics": evidence.get("metrics", {}),
            "policies": evidence.get("policies", {}),
        },
        "assets": {
            "total": len(assets),
            "primaryRiggedCharacters": rigged_characters,
            "primaryRigCount": len(rigged_characters),
            "primaryRigTarget": len(KNOWN_CHARACTER_SLUGS),
            "primaryRigTriangles": total_triangles,
            "primaryRigVertices": total_vertices,
        },
        "rubric": [
            {"name": "Delight", "evidence": "toy powers, rescue reactions, dialogue, sounds, generated objects"},
            {"name": "AI load-bearing", "evidence": "structured action policy, trace retrieval, memories, vision payloads"},
            {"name": "Originality", "evidence": "multi-agent embodied toy-room social physics prototype"},
            {"name": "Polish", "evidence": "hosted Space, runtime stack, brain trace, judge demo, readiness scorecard"},
        ],
    }


POLICY_REGISTRY_PATH_KEYS = (
    "policy_path",
    "checkpoint_path",
    "local_checkpoint_path",
    "seed_checkpoint_path",
    "adapter_path",
    "eval_path",
    "train_path",
    "manifest_path",
    "manifest_summary_path",
    "local_manifest_path",
    "local_manifest_summary_path",
    "proof_mp4",
    "proof_gif",
    "local_demo_mp4",
    "local_fallback_policy_path",
    "report_path",
    "artifact_archive",
)


def fireboy_policy_registry_status() -> dict[str, Any]:
    registry_path = FIREBOY_VLA_ROOT / "policy_registry.json"
    if not registry_path.exists():
        return {
            "ok": False,
            "reason": f"missing registry: {registry_path.relative_to(ROOT)}",
            "skills": [],
            "failedExperiments": [],
            "bodyProofs": [],
            "vlaModels": [],
        }

    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    skills = registry.get("skills", {}) if isinstance(registry.get("skills"), dict) else {}
    failed = registry.get("failed_experiments", {}) if isinstance(registry.get("failed_experiments"), dict) else {}
    proofs = registry.get("body_proofs", {}) if isinstance(registry.get("body_proofs"), dict) else {}
    vla_models = registry.get("vla_models", {}) if isinstance(registry.get("vla_models"), dict) else {}

    return {
        "ok": True,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "registryPath": registry_path.relative_to(ROOT).as_posix(),
        "version": registry.get("version"),
        "notes": registry.get("notes"),
        "fireboyGlb": _policy_path_payload(registry.get("fireboy_glb")),
        "skills": [
            _policy_entry_payload(
                name,
                _resolve_policy_alias(name, skills),
                section="skills",
                aliasOf=entry.get("alias_of"),
            )
            for name, entry in skills.items()
            if isinstance(entry, dict)
        ],
        "activeSkills": [
            _policy_entry_payload(
                name,
                _resolve_policy_alias(name, skills),
                section="skills",
                aliasOf=entry.get("alias_of"),
            )
            for name, entry in skills.items()
            if isinstance(entry, dict) and not entry.get("alias_of")
        ],
        "failedExperiments": [
            _policy_entry_payload(name, entry, section="failed_experiments")
            for name, entry in failed.items()
            if isinstance(entry, dict)
        ],
        "bodyProofs": [
            _policy_entry_payload(name, entry, section="body_proofs")
            for name, entry in proofs.items()
            if isinstance(entry, dict)
        ],
        "vlaModels": [
            _policy_entry_payload(name, entry, section="vla_models")
            for name, entry in vla_models.items()
            if isinstance(entry, dict)
        ],
    }


def _resolve_policy_alias(name: str, skills: dict[str, Any]) -> dict[str, Any]:
    current = name
    visited: set[str] = set()
    entry = skills.get(current)
    while isinstance(entry, dict) and entry.get("alias_of"):
        if current in visited:
            return {}
        visited.add(current)
        current = str(entry.get("alias_of"))
        entry = skills.get(current)
    return entry if isinstance(entry, dict) else {}


def _policy_entry_payload(
    name: str,
    entry: dict[str, Any],
    *,
    section: str,
    aliasOf: str | None = None,
) -> dict[str, Any]:
    paths = {
        key: _policy_path_payload(entry.get(key))
        for key in POLICY_REGISTRY_PATH_KEYS
        if entry.get(key)
    }
    eval_summary = _policy_eval_summary(paths.get("eval_path", {}).get("resolved"))
    train_summary = _policy_eval_summary(paths.get("train_path", {}).get("resolved"))
    manifest_summary = (
        _policy_eval_summary(paths.get("manifest_summary_path", {}).get("resolved"))
        or _policy_eval_summary(paths.get("local_manifest_summary_path", {}).get("resolved"))
    )
    report_summary = _policy_eval_summary(paths.get("report_path", {}).get("resolved"))
    media = {
        "mp4Url": paths.get("proof_mp4", {}).get("url") or paths.get("local_demo_mp4", {}).get("url") or "",
        "gifUrl": paths.get("proof_gif", {}).get("url") or "",
        "evalUrl": paths.get("eval_path", {}).get("url") or "",
        "reportUrl": paths.get("report_path", {}).get("url") or "",
    }
    return {
        "name": name,
        "aliasOf": aliasOf or "",
        "section": section,
        "task": entry.get("task") or entry.get("mode") or name,
        "lane": entry.get("lane") or entry.get("runtime") or "",
        "runtime": entry.get("runtime") or "",
        "modelId": entry.get("model_id") or "",
        "skills": entry.get("skills") if isinstance(entry.get("skills"), list) else [],
        "parameters": entry.get("parameters") if isinstance(entry.get("parameters"), list) else [],
        "status": entry.get("status") or "",
        "successes": entry.get("successes"),
        "episodes": entry.get("episodes"),
        "successRate": entry.get("success_rate"),
        "reason": entry.get("reason") or "",
        "note": entry.get("note") or "",
        "paths": paths,
        "media": media,
        "evalSummary": eval_summary,
        "trainSummary": train_summary,
        "manifestSummary": manifest_summary,
        "reportSummary": report_summary,
    }


def _policy_path_payload(path_value: Any) -> dict[str, Any]:
    if not path_value:
        return {"path": "", "resolved": "", "exists": False, "url": ""}
    path = Path(str(path_value))
    if not path.is_absolute():
        path = ROOT / path
    exists = path.exists()
    return {
        "path": str(path_value),
        "resolved": str(path),
        "exists": exists,
        "url": _policy_static_url(path) if exists else "",
        "sizeBytes": path.stat().st_size if exists and path.is_file() else None,
    }


def _policy_static_url(path: Path) -> str:
    roots = (
        (FIREBOY_RUNPOD_ARTIFACT_ROOT, "/fireboy-runpod-artifacts"),
        (FIREBOY_VLA_ROOT, "/fireboy-vla"),
        (ROOT / "fire-boy-rig", "/fire-boy-rig"),
        (ROOT / "assets", "/toy-assets"),
        (ROOT / "potential-char-images", "/potential-char-images"),
    )
    resolved = path.resolve()
    for root, prefix in roots:
        if not root.exists():
            continue
        try:
            rel = resolved.relative_to(root.resolve())
        except ValueError:
            continue
        return prefix + "/" + quote(rel.as_posix(), safe="/")
    return ""


def _policy_eval_summary(resolved_path: str | None) -> dict[str, Any] | None:
    if not resolved_path:
        return None
    path = Path(resolved_path)
    if not path.exists() or not path.is_file() or path.suffix.lower() != ".json":
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"error": str(exc)[:240]}
    summary: dict[str, Any] = {}
    for key in (
        "mode",
        "task",
        "success",
        "episodes",
        "successes",
        "success_rate",
        "frames",
        "smooth_alpha",
        "replan_interval",
        "rows",
        "rows_written",
        "train_rows",
        "val_rows",
        "device",
        "model_id",
        "policy_kind",
        "cache_hits",
        "state_mode",
        "action_type",
        "skipped",
    ):
        if key in payload:
            summary[key] = payload[key]
    if isinstance(payload.get("skill_names"), list):
        summary["skill_names"] = payload["skill_names"]
    if isinstance(payload.get("param_names"), list):
        summary["param_names"] = payload["param_names"]
    if isinstance(payload.get("skills"), dict):
        summary["skills"] = payload["skills"]
    metrics = payload.get("metrics")
    if isinstance(metrics, dict):
        for key in ("skill_accuracy", "param_mae", "confusion"):
            if key in metrics:
                summary[key] = metrics[key]
        if isinstance(metrics.get("param_mae_by_name"), dict):
            summary["param_mae_by_name"] = metrics["param_mae_by_name"]
    val_metrics = payload.get("val_metrics")
    if isinstance(val_metrics, dict):
        if "skill_accuracy" in val_metrics:
            summary["val_skill_accuracy"] = val_metrics["skill_accuracy"]
        if "param_mae" in val_metrics:
            summary["val_param_mae"] = val_metrics["param_mae"]
        if isinstance(val_metrics.get("param_mae_by_name"), dict):
            summary["val_param_mae_by_name"] = val_metrics["param_mae_by_name"]
    if isinstance(payload.get("report"), dict):
        report = payload["report"]
        for key in ("nbody", "njnt", "nu", "actuated_joints", "body_tree", "resembles_fireboy", "not_yet"):
            if key in report:
                summary[key] = report[key]
    reports = payload.get("reports")
    if isinstance(reports, list) and reports:
        summary["sampleReport"] = {
            key: reports[0].get(key)
            for key in ("success", "grasped", "eaten", "final_root_xy", "target_xy", "min_mouth_dist")
            if key in reports[0]
        }
    return summary


@server.get("/toy", response_class=HTMLResponse)
def toy_room() -> str:
    return toy_room_v3_html()


@server.get("/toy-v2", response_class=HTMLResponse)
def toy_room_v2() -> str:
    return (ROOT / "frontend" / "toy-v2.html").read_text(encoding="utf-8")


@server.get("/toy-v3", response_class=HTMLResponse)
def toy_room_v3() -> str:
    return toy_room_v3_html()


def toy_room_v3_html() -> str:
    html = (ROOT / "frontend" / "toy-v2.html").read_text(encoding="utf-8")
    replacements = {
        "<title>Toy Room v2</title>": "<title>Toy Room v3 | Fire Boy</title>",
        "<body>": '<body data-toybox-version="v3">',
        'aria-label="Toy Room v2 interactive physics stage"': 'aria-label="Toy Room v3 Fire Boy interactive physics stage"',
        'aria-label="Toy Room v2 controls"': 'aria-label="Toy Room v3 controls"',
        "<strong>Toy Room v2</strong>": "<strong>Toy Room v3</strong>",
        "<span>MiniCPM vision-action toybox</span>": "<span>Fire Boy virtual pet brain</span>",
        '<div class="section-title">Room</div>': '<div class="section-title">Player view</div>',
        '<div class="section-title">Vision</div>': '<div class="section-title">Fire Boy view</div>',
        '<a class="route-link glass" href="/pages">Pages</a>': '<a class="route-link glass" href="/toy-v2">v2</a><a class="route-link glass" href="/pages">Pages</a>',
        '<button id="modeButton" class="mode-button" type="button">Council</button>': '<button id="modeButton" class="mode-button" type="button">Fire Boy</button>',
        'placeholder="Teach, ask, or invent a toy-room spell"': 'placeholder="Talk to Fire Boy, move him, or ask him to play with a toy"',
        "/frontend/toybox/v2_main.js?v=20260614-grounded-pickup-walk": "/frontend/toybox/v2_main.js?v=20260614-mujoco-policy",
        "/frontend/toybox/v2_main.js?v=20260614-grounded-gestures": "/frontend/toybox/v2_main.js?v=20260614-mujoco-policy",
        "/frontend/toybox/v2_main.js?v=20260613-ai-evidence": "/frontend/toybox/v2_main.js?v=20260614-modal-debug-ui",
    }
    for source, target in replacements.items():
        html = html.replace(source, target)
    return html


@server.get("/pages", response_class=HTMLResponse)
def page_directory() -> str:
    return (ROOT / "frontend" / "pages.html").read_text(encoding="utf-8")


@server.get("/models", response_class=HTMLResponse)
def model_gallery() -> str:
    return (ROOT / "frontend" / "model-gallery.html").read_text(encoding="utf-8")


@server.get("/blender-models", response_class=HTMLResponse)
def blender_model_gallery() -> str:
    return (ROOT / "frontend" / "blender-models.html").read_text(encoding="utf-8")


@server.get("/parts-lab", response_class=HTMLResponse)
def parts_lab() -> str:
    return (ROOT / "frontend" / "parts-lab.html").read_text(encoding="utf-8")


@server.get("/fireboy-rigged", response_class=HTMLResponse)
def fireboy_rigged() -> str:
    return (ROOT / "frontend" / "fireboy-rigged.html").read_text(encoding="utf-8")


@server.get("/mujoco-policy", response_class=HTMLResponse)
def mujoco_policy_page() -> str:
    return (ROOT / "frontend" / "mujoco-policy.html").read_text(encoding="utf-8")


@server.get("/fireboy-policy-gallery", response_class=HTMLResponse)
def fireboy_policy_gallery() -> str:
    return (ROOT / "frontend" / "fireboy-policy-gallery.html").read_text(encoding="utf-8")


@server.get("/vla-research", response_class=HTMLResponse)
def vla_research_page() -> str:
    return (ROOT / "frontend" / "vla-research.html").read_text(encoding="utf-8")


@server.post("/api/pet-action")
async def pet_action(request: Request) -> JSONResponse:
    payload: dict[str, Any] = await request.json()
    started = time.perf_counter()
    action = run_vla_router_pet_action(payload) or run_mujoco_pet_action(payload) or choose_pet_action(payload)
    elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
    debug = action.setdefault("debug", {})
    if isinstance(debug, dict):
        debug["serverLatencyMs"] = elapsed_ms
        debug["cameraFrameSource"] = payload.get("cameraFrameSource") or ""
    try:
        record_pet_action(payload, action, elapsed_ms)
    except Exception as exc:
        if isinstance(debug, dict):
            debug["actionStoreError"] = str(exc)[:180]
    return JSONResponse(action)


@server.post("/api/mujoco-policy")
async def mujoco_policy(request: Request) -> JSONResponse:
    payload: dict[str, Any] = await request.json()
    action = run_mujoco_pet_action(payload)
    if action is None:
        return JSONResponse({"enabled": False, "reason": "command did not route to MuJoCo policy"}, status_code=404)
    return JSONResponse({"enabled": True, "action": action})


@server.post("/api/vla-router")
async def vla_router(request: Request) -> JSONResponse:
    payload: dict[str, Any] = await request.json()
    try:
        return JSONResponse({"ok": True, "result": route_vla(payload)})
    except Exception as exc:
        return JSONResponse({"ok": False, "status": vla_router_status(), "error": str(exc)[:800]}, status_code=503)


@server.get("/api/fireboy-policy-registry")
def fireboy_policy_registry() -> JSONResponse:
    return JSONResponse(fireboy_policy_registry_status())


@server.post("/api/mujoco-showcase")
async def mujoco_showcase(request: Request) -> JSONResponse:
    payload: dict[str, Any] = await request.json()
    mode = str(payload.get("mode") or "learned")
    try:
        return JSONResponse({"ok": True, "result": run_mujoco_showcase(mode)})
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)[:1000]}, status_code=500)


@server.post("/api/mujoco-audit")
async def mujoco_audit() -> JSONResponse:
    try:
        return JSONResponse({"ok": True, "result": run_mujoco_policy_audit()})
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)[:1400]}, status_code=500)


@server.post("/api/articulated-fireboy")
async def articulated_fireboy(request: Request) -> JSONResponse:
    payload: dict[str, Any] = await request.json()
    mode = str(payload.get("mode") or "all")
    try:
        return JSONResponse({"ok": True, "result": run_articulated_fireboy(mode)})
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)[:1400]}, status_code=500)


@server.get("/api/model-status")
def pet_model_status() -> JSONResponse:
    status = model_status()
    status["vlaRouter"] = vla_router_status()
    return JSONResponse(status)


@server.get("/api/pet-action-events")
def pet_action_events(limit: int = 50) -> JSONResponse:
    return JSONResponse(fetch_action_events(limit=limit))


@server.get("/api/pet-action-stats")
def pet_action_stats() -> JSONResponse:
    return JSONResponse(action_stats())


@server.get("/api/ai-evidence")
def ai_evidence(limit: int = 4) -> JSONResponse:
    return JSONResponse(ai_evidence_status(limit=limit))


@server.get("/api/judge-status")
def judge_status() -> JSONResponse:
    return JSONResponse(judge_readiness_status())


@server.get("/api/pet-memories")
def pet_memories(pet: str | None = None) -> JSONResponse:
    return JSONResponse({"memories": load_memories(pet, limit=16)})


@server.get("/api/training-dataset")
def training_dataset(format: str = "summary", limit: int = 4) -> Any:
    if format == "jsonl":
        return PlainTextResponse(
            training_dataset_jsonl(limit=limit),
            media_type="application/jsonl",
            headers={"Content-Disposition": 'attachment; filename="toy-room-v2-sft.jsonl"'},
        )
    return JSONResponse(training_dataset_summary(limit=limit))


@server.get("/api/glb-assets")
def glb_assets() -> JSONResponse:
    return JSONResponse({"assets": glb_asset_manifest()})


with gr.Blocks(title="Tiny Toybox", fill_height=True, fill_width=True) as demo:
    gr.HTML(
        """
        <iframe
            class="toy-frame"
            src="/pages"
            allow="camera; microphone"
            style="position: fixed; inset: 0; width: 100vw; height: 100vh; border: 0; display: block; background: #f6f2ea;"
        ></iframe>
        """,
        container=False,
        padding=False,
    )


app = gr.mount_gradio_app(server, demo, path="/")


if __name__ == "__main__":
    port = int(os.getenv("PORT", "65372"))
    uvicorn.run(app, host="0.0.0.0", port=port)
