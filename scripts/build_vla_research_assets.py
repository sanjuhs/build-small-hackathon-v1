#!/usr/bin/env python3
"""Build the Fire Boy MiniCPM-V VLA research PDF and supporting charts."""

from __future__ import annotations

import json
import math
import shutil
import textwrap
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image as PdfImage,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
CHECKPOINTS = ROOT / "Fireboy-training-policy-vla" / "runpod-artifacts" / "checkpoints"
FRONTEND_RESEARCH = ROOT / "frontend" / "research"
OUTPUT_PDF_DIR = ROOT / "output" / "pdf"
PDF_NAME = "minicpm-v46-fireboy-vla-research-paper.pdf"
PDF_PATH = OUTPUT_PDF_DIR / PDF_NAME
FRONTEND_PDF_PATH = FRONTEND_RESEARCH / PDF_NAME

INK = "#172121"
MUTED = "#61706c"
TEAL = "#123238"
AQUA = "#66cbd8"
AMBER = "#f0bc42"
CORAL = "#ef7758"
PAPER = "#fffaf0"
LINE = "#d8d6cc"


def robust_json(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    decoder = json.JSONDecoder()
    best: tuple[int, dict[str, Any]] | None = None
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            obj, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            score = len(json.dumps(obj, sort_keys=True))
            if best is None or score > best[0]:
                best = (score, obj)
    if best is None:
        raise ValueError(f"No JSON object found in {path}")
    return best[1]


def rel(path: str) -> Path:
    return ROOT / path


def load_evidence() -> dict[str, Any]:
    frozen_train = robust_json(CHECKPOINTS / "fireboy_minicpm_vla_skill_param_head" / "train_minicpm_vla_skill_param_head.json")
    frozen_eval = robust_json(CHECKPOINTS / "fireboy_minicpm_vla_skill_param_head" / "eval_minicpm_vla_skill_param_head.json")
    lora_train = robust_json(CHECKPOINTS / "fireboy_minicpm_vla_lora_skill_param_head" / "train_minicpm_vla_lora_skill_param_head.json")
    lora_eval = robust_json(CHECKPOINTS / "fireboy_minicpm_vla_lora_skill_param_head" / "eval_minicpm_vla_lora_skill_param_head.json")
    residual_train = robust_json(CHECKPOINTS / "fireboy_minicpm_vla_action_head_residual_2048" / "train_minicpm_vla_action_head.json")
    lora_manip_train = robust_json(CHECKPOINTS / "fireboy_minicpm_vla_lora_residual_512" / "train_minicpm_vla_lora_action_head.json")
    skill_manifest = robust_json(CHECKPOINTS / "fireboy_minicpm_vla_skill_param_head" / "fireboy_vla_skill_params_allskill.summary.json")
    proof_summary = robust_json(ROOT / "fireboy-vla-physics" / "build" / "fireboy-policy-proof-bundle" / "summary.json")
    rig_report = robust_json(ROOT / "fire-boy-rig" / "working" / "fire-boy-rig-report.json")
    skeleton_alignment = robust_json(ROOT / "fireboy-vla-physics" / "build" / "inspection" / "fireboy_skeleton_alignment.json")
    articulated_report = robust_json(ROOT / "Fireboy-training-policy-vla" / "runpod-artifacts" / "runpod_artifacts" / "render_gate" / "articulated_report.json")

    def eval_file(folder: str, name: str) -> dict[str, Any]:
        return robust_json(CHECKPOINTS / folder / name)

    evals = {
        "one_step_pick": eval_file("fireboy_articulated_pick_up", "eval_pick_up.json"),
        "chunk_pick": eval_file("fireboy_articulated_pick_up_chunk", "eval_pick_up_chunk.json"),
        "one_step_eat": eval_file("fireboy_articulated_go_eat_berry", "eval_go_eat_berry.json"),
        "chunk_eat": eval_file("fireboy_articulated_go_eat_berry_chunk", "eval_go_eat_berry_chunk.json"),
        "initial_pick": eval_file("fireboy_vla_manifest_action_head", "eval_pick_up_manifest_head.json"),
        "initial_eat": eval_file("fireboy_vla_manifest_action_head", "eval_go_eat_berry_manifest_head.json"),
        "initial_run": eval_file("fireboy_vla_manifest_action_head", "eval_run_around_manifest_head.json"),
        "initial_go": eval_file("fireboy_vla_manifest_action_head", "eval_go_to_point_manifest_head.json"),
        "manip_pick": eval_file("fireboy_vla_manifest_action_head_manip", "eval_pick_up_manifest_head.json"),
        "manip_eat": eval_file("fireboy_vla_manifest_action_head_manip", "eval_go_eat_berry_manifest_head.json"),
        "residual_pick": eval_file("fireboy_minicpm_vla_action_head_residual_2048", "eval_pick_up_minicpm_vla.json"),
        "residual_eat": eval_file("fireboy_minicpm_vla_action_head_residual_2048", "eval_go_eat_berry_minicpm_vla.json"),
        "lora_pick": eval_file("fireboy_minicpm_vla_lora_residual_512_eval_3ep", "eval_pick_up_minicpm_vla.json"),
        "lora_eat": eval_file("fireboy_minicpm_vla_lora_residual_512_eval_3ep", "eval_go_eat_berry_minicpm_vla.json"),
        "allskill_pick": eval_file("fireboy_minicpm_vla_action_head_allskill_3072", "eval_pick_up_minicpm_vla.json"),
        "allskill_eat": eval_file("fireboy_minicpm_vla_action_head_allskill_3072", "eval_go_eat_berry_minicpm_vla.json"),
        "allskill_run": eval_file("fireboy_minicpm_vla_action_head_allskill_3072", "eval_run_around_minicpm_vla.json"),
        "allskill_go": eval_file("fireboy_minicpm_vla_action_head_allskill_3072", "eval_go_to_point_minicpm_vla.json"),
        "move_run": eval_file("fireboy_minicpm_vla_action_head_movement_992", "eval_run_around_minicpm_vla.json"),
        "move_go": eval_file("fireboy_minicpm_vla_action_head_movement_992", "eval_go_to_point_minicpm_vla.json"),
        "direct_go_1step": eval_file("fireboy_minicpm_vla_action_head_go_to_point_full_1step_480", "eval_go_to_point_minicpm_vla.json"),
        "direct_go_rootvel": eval_file("fireboy_minicpm_vla_action_head_go_to_point_rootvel_480", "eval_go_to_point_minicpm_vla.json"),
        "direct_go_recovery": eval_file("fireboy_minicpm_vla_action_head_go_to_point_recovery_rootvel_884", "eval_go_to_point_minicpm_vla.json"),
        "walk_clock": eval_file("fireboy_articulated_go_to_point_clock", "eval_go_to_point_clock_fixed_target.json"),
        "run_policy": eval_file("fireboy_articulated_run_around", "eval_run_around.json"),
    }

    return {
        "frozen_train": frozen_train,
        "frozen_eval": frozen_eval,
        "lora_train": lora_train,
        "lora_eval": lora_eval,
        "residual_train": residual_train,
        "lora_manip_train": lora_manip_train,
        "skill_manifest": skill_manifest,
        "proof_summary": proof_summary,
        "rig_report": rig_report,
        "skeleton_alignment": skeleton_alignment,
        "articulated_report": articulated_report,
        "evals": evals,
        "param_counts": {
            "frozen_skill_param_router_head": count_skill_param_router_head(input_dim=1066, hidden_dim=512, skill_count=4, param_dim=6),
            "residual_action_head": count_residual_action_head(vl_dim=1024, state_dim=27, output_dim=320, hidden_dim=512),
            "single_tower_action_head": count_single_tower(input_dim=1066, hidden_dim=512, output_dim=320),
            "lora_adapter": safetensors_param_count(
                ROOT / "Fireboy-training-policy-vla" / "runpod-artifacts" / "checkpoints" / "fireboy_minicpm_vla_lora_skill_param_head" / "lora_adapter" / "adapter_model.safetensors"
            ),
        },
    }


def linear_params(input_dim: int, output_dim: int) -> int:
    return input_dim * output_dim + output_dim


def count_skill_param_router_head(input_dim: int, hidden_dim: int, skill_count: int, param_dim: int) -> int:
    return (
        linear_params(input_dim, hidden_dim)
        + linear_params(hidden_dim, hidden_dim)
        + linear_params(hidden_dim, skill_count)
        + linear_params(hidden_dim, param_dim)
    )


def count_single_tower(input_dim: int, hidden_dim: int, output_dim: int) -> int:
    return linear_params(input_dim, hidden_dim) + linear_params(hidden_dim, hidden_dim) + linear_params(hidden_dim, output_dim)


def count_residual_action_head(vl_dim: int, state_dim: int, output_dim: int, hidden_dim: int) -> dict[str, int]:
    state_head = linear_params(state_dim, hidden_dim) + linear_params(hidden_dim, hidden_dim) + linear_params(hidden_dim, output_dim)
    vl_head = linear_params(vl_dim, 256) + linear_params(256, 256)
    residual = linear_params(256 + state_dim, hidden_dim) + linear_params(hidden_dim, output_dim)
    return {
        "total": state_head + vl_head + residual,
        "state_head": state_head,
        "vl_head": vl_head,
        "residual_head": residual,
    }


def safetensors_param_count(path: Path) -> dict[str, Any]:
    import struct

    if not path.exists():
        return {
            "total": 4_743_168,
            "tensor_count": 360,
            "layer_count": 24,
            "min_layer": 0,
            "max_layer": 23,
            "modules": {
                "down_proj": 884_736,
                "gate_proj": 884_736,
                "k_proj": 294_912,
                "o_proj": 393_216,
                "q_proj": 393_216,
                "up_proj": 884_736,
                "v_proj": 294_912,
                "visual": 712_704,
            },
            "source": "recorded_from_local_checkpoint_header",
        }

    data = path.read_bytes()
    header_len = struct.unpack("<Q", data[:8])[0]
    header = json.loads(data[8 : 8 + header_len])
    modules: dict[str, int] = {}
    layers: set[int] = set()
    total = 0
    tensor_count = 0
    for name, meta in header.items():
        if name == "__metadata__":
            continue
        shape = meta["shape"]
        count = 1
        for value in shape:
            count *= int(value)
        total += count
        tensor_count += 1
        if "language_model.layers." in name:
            layer = name.split("language_model.layers.", 1)[1].split(".", 1)[0]
            if layer.isdigit():
                layers.add(int(layer))
        parts = name.split(".")
        module = parts[-3] if len(parts) >= 3 else "unknown"
        modules[module] = modules.get(module, 0) + count
    return {
        "total": total,
        "tensor_count": tensor_count,
        "layer_count": len(layers),
        "min_layer": min(layers) if layers else None,
        "max_layer": max(layers) if layers else None,
        "modules": dict(sorted(modules.items())),
    }


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial Bold.ttf" if bold else "/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            pass
    return ImageFont.load_default()


def wrapped(draw: ImageDraw.ImageDraw, text: str, xy: tuple[int, int], width: int, fill: str, size: int = 24, bold: bool = False, line_gap: int = 6) -> int:
    fnt = font(size, bold)
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        trial = f"{current} {word}".strip()
        if draw.textbbox((0, 0), trial, font=fnt)[2] <= width or not current:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    x, y = xy
    for line in lines:
        draw.text((x, y), line, fill=fill, font=fnt)
        y += size + line_gap
    return y


def draw_card(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], title: str, body: str, fill: str, outline: str = LINE) -> None:
    draw.rounded_rectangle(box, radius=18, fill=fill, outline=outline, width=2)
    x1, y1, x2, _ = box
    y = wrapped(draw, title, (x1 + 22, y1 + 18), x2 - x1 - 44, INK, size=24, bold=True, line_gap=4)
    wrapped(draw, body, (x1 + 22, y + 8), x2 - x1 - 44, MUTED, size=18, line_gap=5)


def open_rgb(path: Path, background: str = "#ffffff") -> Image.Image:
    if not path.exists():
        image = Image.new("RGB", (960, 540), background)
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((28, 28, 932, 512), radius=24, fill="#fff8e8", outline=LINE, width=3)
        wrapped(draw, "Local rollout frame", (68, 78), 820, INK, size=38, bold=True)
        wrapped(draw, "This raw dataset image is kept outside git; the committed paper uses generated proof charts and browser-facing screenshots.", (68, 150), 805, MUTED, size=25)
        return image
    image = Image.open(path).convert("RGBA")
    base = Image.new("RGBA", image.size, background)
    base.alpha_composite(image)
    return base.convert("RGB")


def cover_image(path: Path, size: tuple[int, int], background: str = "#ffffff", contain: bool = False) -> Image.Image:
    image = open_rgb(path, background=background)
    target_w, target_h = size
    if contain:
        image.thumbnail(size, Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", size, background)
        canvas.paste(image, ((target_w - image.width) // 2, (target_h - image.height) // 2))
        return canvas
    scale = max(target_w / image.width, target_h / image.height)
    resized = image.resize((int(image.width * scale), int(image.height * scale)), Image.Resampling.LANCZOS)
    left = max(0, (resized.width - target_w) // 2)
    top = max(0, (resized.height - target_h) // 2)
    return resized.crop((left, top, left + target_w, top + target_h))


def draw_image_tile(
    draw: ImageDraw.ImageDraw,
    canvas: Image.Image,
    box: tuple[int, int, int, int],
    image_path: Path,
    title: str,
    caption: str,
    *,
    contain: bool = True,
    fill: str = "#ffffff",
) -> None:
    x1, y1, x2, y2 = box
    draw.rounded_rectangle(box, radius=18, fill=fill, outline=LINE, width=2)
    image_h = int((y2 - y1) * 0.64)
    crop = cover_image(image_path, (x2 - x1 - 28, image_h), background=fill, contain=contain)
    canvas.paste(crop, (x1 + 14, y1 + 14))
    text_y = y1 + 20 + image_h
    wrapped(draw, title, (x1 + 16, text_y), x2 - x1 - 32, INK, size=21, bold=True, line_gap=3)
    wrapped(draw, caption, (x1 + 16, text_y + 32), x2 - x1 - 32, MUTED, size=16, line_gap=4)


def chart_modeling_pipeline(path: Path) -> None:
    img = Image.new("RGB", (1500, 1100), PAPER)
    draw = ImageDraw.Draw(img)
    draw.text((54, 42), "Avatar modeling pipeline", fill=INK, font=font(48, True))
    wrapped(
        draw,
        "From concept art to SAM extraction, cleaned base body, Blender skeleton, animation clips, MuJoCo body matching, and Toy Room retarget proof.",
        (58, 104),
        1320,
        MUTED,
        24,
    )
    tiles = [
        ("potential-char-images/fire-boy.png", "1. concept", "Fire Boy source art used as the visual target."),
        ("assets/generated/previews/fire-boy-sam-cleaned.png", "2. SAM cleanup", "Standing, isolated base body after segmentation/extraction cleanup."),
        ("assets/generated/previews/fire-boy-sam-standing-rigged.png", "3. base rig", "SAM body prepared for a 20-bone humanoid skeleton."),
        ("fire-boy-rig/previews/fire-boy-fullrig-bones.png", "4. skeleton", "Blender preview with deform bones and x-ray checks."),
        ("fire-boy-rig/previews/fire-boy-clip-walk-f09.png", "5. clips", "Authored walk/run/jump/wave/cheer/dance/spin/throw/sit clips."),
        ("Fireboy-training-policy-vla/screenshots/fixed-glb-vs-mujoco-skeleton-overlay.png", "6. MuJoCo match", "GLB skeleton and MuJoCo body points aligned for retargeting."),
        ("Fireboy-training-policy-vla/screenshots/fixed-mujoco-fireboy-body.png", "7. physics body", "Simplified MJCF body with 32 actuators and contact sites."),
        ("Fireboy-training-policy-vla/proofs/toy-v3-fireboy-pickup-retarget-clean.png", "8. live retarget", "Policy rollout retargeted back onto the browser Fire Boy rig."),
    ]
    cols = 4
    tile_w = 335
    tile_h = 390
    x0 = 58
    y0 = 190
    gap_x = 28
    gap_y = 38
    for idx, (rel_path, title, caption) in enumerate(tiles):
        row, col = divmod(idx, cols)
        x = x0 + col * (tile_w + gap_x)
        y = y0 + row * (tile_h + gap_y)
        draw_image_tile(draw, img, (x, y, x + tile_w, y + tile_h), ROOT / rel_path, title, caption, contain=True)
    img.save(path)


def chart_simulation_sync(path: Path) -> None:
    img = Image.new("RGB", (1500, 900), "#ffffff")
    draw = ImageDraw.Draw(img)
    draw.text((54, 42), "Simulation and VM synchronization", fill=INK, font=font(45, True))
    wrapped(draw, "The practical loop was local orchestration plus disposable GPU machines: prepare assets locally, run training/eval on RunPod, copy JSON/MP4/checkpoints back, expose them in the browser, and keep Modal as the live serverless inference lane.", (58, 102), 1350, MUTED, 22)
    nodes = [
        ((70, 240, 360, 410), "Local repo", "Scripts, manifests, GLB assets, route/page code, and browser QA."),
        ((430, 240, 720, 410), "RunPod GPU pod", "RTX 6000 Ada/A40 for MiniCPM-V encoding, frozen heads, LoRA, and closed-loop eval."),
        ((790, 240, 1080, 410), "Artifact copyback", "Checkpoints, eval JSON, proof MP4/GIF, screenshots, and manifest summaries."),
        ((1150, 240, 1430, 410), "Toy Room demo", "FastAPI/Gradio app serves page, PDF, policy gallery, and live retarget bridge."),
        ((250, 575, 540, 745), "Modal L40S", "MiniCPM-o WebSocket gateway for command-time pet actions with Volume cache and Secret."),
        ((830, 575, 1120, 745), "Newton/Warp lane", "Future GPU physics route for scalable rollout generation and MJCF/USD traces."),
    ]
    for box, title, body in nodes:
        fill = "#eefafa" if "RunPod" in title or "Modal" in title else "#fff8e8" if "Newton" in title else "#ffffff"
        draw_card(draw, box, title, body, fill)
    arrows = [((360, 325), (430, 325)), ((720, 325), (790, 325)), ((1080, 325), (1150, 325)), ((395, 575), (230, 410)), ((975, 575), (935, 410))]
    for start, end in arrows:
        draw.line([start, end], fill=TEAL, width=6)
        ex, ey = end
        sx, sy = start
        angle = math.atan2(ey - sy, ex - sx)
        p1 = (ex - 18 * math.cos(angle - 0.55), ey - 18 * math.sin(angle - 0.55))
        p2 = (ex - 18 * math.cos(angle + 0.55), ey - 18 * math.sin(angle + 0.55))
        draw.polygon([end, p1, p2], fill=TEAL)
    img.save(path)


def chart_rollout_samples(path: Path) -> None:
    sample_paths = [
        "Fireboy-training-policy-vla/vla-rollouts/minicpm_slices/go_to_point_480_32step/datasets/fireboy_vla_slice/images/000026.jpg",
        "Fireboy-training-policy-vla/vla-rollouts/minicpm_slices/go_to_point_480_32step/datasets/fireboy_vla_slice/images/000153.jpg",
        "Fireboy-training-policy-vla/vla-rollouts/minicpm_slices/go_to_point_480_32step/datasets/fireboy_vla_slice/images/000231.jpg",
        "Fireboy-training-policy-vla/vla-rollouts/minicpm_slices/go_to_point_480_32step/datasets/fireboy_vla_slice/images/000351.jpg",
        "Fireboy-training-policy-vla/proofs/toy-v3-vla-live-bridge-pickup-ball.png",
        "Fireboy-training-policy-vla/proofs/toy-v3-vla-eat-berry-gui.png",
    ]
    captions = [
        ("sample frame", "Rendered room observation used in VLA manifests."),
        ("navigation", "Target-relative frames sampled every 5 simulation steps."),
        ("action chunk", "Rows pair image + state with a short action horizon."),
        ("scene variation", "Different camera/target arrangements for grounding."),
        ("pickup bridge", "Closed-loop proof retargeted into Toy Room v3."),
        ("eat berry", "Manipulation rollout with object/mouth state."),
    ]
    img = Image.new("RGB", (1500, 1000), PAPER)
    draw = ImageDraw.Draw(img)
    draw.text((54, 42), "Data and rollout evidence", fill=INK, font=font(46, True))
    wrapped(draw, "Images are not decoration: they are the observation side of the VLA rows and the proof side of the browser demo.", (58, 102), 1320, MUTED, 23)
    cols = 3
    tile_w = 440
    tile_h = 370
    x0, y0 = 58, 188
    for idx, rel_path in enumerate(sample_paths):
        row, col = divmod(idx, cols)
        x = x0 + col * 475
        y = y0 + row * 400
        title, cap = captions[idx]
        draw_image_tile(draw, img, (x, y, x + tile_w, y + tile_h), ROOT / rel_path, title, cap, contain=False)
    img.save(path)


def chart_parameter_summary(path: Path, evidence: dict[str, Any]) -> None:
    counts = evidence["param_counts"]
    img = Image.new("RGB", (1500, 900), "#ffffff")
    draw = ImageDraw.Draw(img)
    draw.text((54, 42), "VLA head sizes and sampled rows", fill=INK, font=font(44, True))
    rows = [
        ("Frozen router head", counts["frozen_skill_param_router_head"], "1066 -> 512 -> 512 -> skill(4) + params(6)"),
        ("Residual action head", counts["residual_action_head"]["total"], "VL branch + state controller + residual 10x32 action chunk"),
        ("LoRA adapter", counts["lora_adapter"]["total"], "rank 8 adapters on q/k/v/o and MLP projections, layers 0-23"),
    ]
    max_value = max(row[1] for row in rows)
    x0, y0 = 90, 190
    for idx, (label, value, desc) in enumerate(rows):
        y = y0 + idx * 150
        draw.text((x0, y), label, fill=INK, font=font(27, True))
        draw.text((x0, y + 34), f"{value:,} trainable parameters", fill=TEAL, font=font(25, True))
        wrapped(draw, desc, (x0, y + 70), 500, MUTED, size=18)
        bar_x = 690
        bar_w = int((value / max_value) * 650)
        color = [TEAL, CORAL, AQUA][idx]
        draw.rounded_rectangle((bar_x, y + 10, bar_x + bar_w, y + 74), radius=16, fill=color)
    manifest = evidence["skill_manifest"]
    draw_card(
        draw,
        (90, 675, 1410, 820),
        "Skill-parameter manifest",
        f"{manifest['rows_written']:,} rows with images required: pick_up {manifest['tasks']['pick_up']}, go_eat_berry {manifest['tasks']['go_eat_berry']}, run_around {manifest['tasks']['run_around']}, go_to_point {manifest['tasks']['go_to_point']}. Outputs are skill_parameters_v1.",
        "#fff8e8",
    )
    img.save(path)


def chart_training_roadmap(path: Path, evidence: dict[str, Any]) -> None:
    img = Image.new("RGB", (1500, 900), PAPER)
    draw = ImageDraw.Draw(img)
    draw.text((54, 42), "Policy training ladder", fill=INK, font=font(45, True))
    wrapped(
        draw,
        "The hackathon policy moved from behavior cloning to action chunks, residual MiniCPM-V heads, and finally a demo-safe skill router. RL comes after the simulator can generate enough failures.",
        (58, 102),
        1320,
        MUTED,
        22,
    )
    steps = [
        ((60, 245, 300, 455), "1. Rollouts", "MuJoCo frames + robot state + commands + action traces."),
        ((335, 245, 575, 455), "2. Behavior cloning", "Fast first signal, but one-step contact actions averaged phases."),
        ((610, 245, 850, 455), "3. Action chunks", "10 x 32 actuator targets made pick/eat phase-aware."),
        ((885, 245, 1125, 455), "4. Residual VLA", "MiniCPM-V embedding adjusts a state-dominant controller."),
        ((1160, 245, 1435, 455), "5. Router", "Skill id + six parameters dispatch into proved policies."),
    ]
    for box, title, body in steps:
        fill = "#ffffff" if "Rollouts" in title else "#eefafa" if "VLA" in title else "#fff8e8" if "Router" in title else "#fff0eb"
        draw_card(draw, box, title, body, fill)
    for x in [300, 575, 850, 1125]:
        draw.line([(x, 350), (x + 35, 350)], fill=TEAL, width=6)
        draw.polygon([(x + 35, 350), (x + 17, 339), (x + 17, 361)], fill=TEAL)
    frozen = evidence["frozen_eval"]["metrics"]
    lora = evidence["lora_eval"]["metrics"]
    draw_card(
        draw,
        (125, 585, 665, 760),
        "Observed loss lesson",
        f"Frozen router: 512/512 skills, MAE {frozen['param_mae']:.4f}. LoRA router: perfect skills too, but MAE {lora['param_mae']:.4f}; numeric grounding mattered more than classifier accuracy.",
        "#ffffff",
    )
    draw_card(
        draw,
        (835, 585, 1375, 760),
        "Future RL layer",
        "Start from imitation, then reward task success, contact stability, smoothness, energy, curiosity, and personality once rollout throughput is high enough.",
        "#eefafa",
    )
    img.save(path)


def chart_future_stack(path: Path) -> None:
    img = Image.new("RGB", (1500, 900), "#ffffff")
    draw = ImageDraw.Draw(img)
    draw.text((54, 42), "Future single-brain virtual pet stack", fill=INK, font=font(43, True))
    wrapped(
        draw,
        "A bigger version should split slow multimodal cognition from millisecond reflexes: MiniCPM/Omni-style brain for goals and personality, small local policies for contact and motion.",
        (58, 102),
        1320,
        MUTED,
        22,
    )
    nodes = [
        ((70, 230, 430, 430), "Slow pet brain", "MiniCPM-V / MiniCPM-o style model sees, hears, remembers, chooses goals, and emits structured plans.", "#eefafa"),
        ((570, 230, 930, 430), "Validated action contract", "JSON/action tokens are clipped, checked, and routed into skills before touching physics.", "#fff8e8"),
        ((1070, 230, 1430, 430), "Fast reflex controller", "Distilled local policy handles balance, contact correction, hand motion, and object attachment.", "#fff0eb"),
        ((70, 585, 430, 770), "Memory + personality", "Habits, preferences, recent interactions, exploration state, and style rewards.", "#ffffff"),
        ((570, 585, 930, 770), "Modal / local inference", "Warm GPU workers for the big brain; quantized local heads for fast repeated action.", "#ffffff"),
        ((1070, 585, 1430, 770), "Rollout factory", "MuJoCo/Newton randomized rooms generate failures, relabeling, imitation data, and RL rewards.", "#eefafa"),
    ]
    for box, title, body, fill in nodes:
        draw_card(draw, box, title, body, fill)
    arrows = [
        ((430, 330), (570, 330)),
        ((930, 330), (1070, 330)),
        ((1250, 430), (1250, 585)),
        ((1070, 680), (930, 680)),
        ((570, 680), (430, 680)),
        ((250, 585), (250, 430)),
    ]
    for start, end in arrows:
        draw.line([start, end], fill=TEAL, width=6)
        ex, ey = end
        sx, sy = start
        angle = math.atan2(ey - sy, ex - sx)
        p1 = (ex - 18 * math.cos(angle - 0.55), ey - 18 * math.sin(angle - 0.55))
        p2 = (ex - 18 * math.cos(angle + 0.55), ey - 18 * math.sin(angle + 0.55))
        draw.polygon([end, p1, p2], fill=TEAL)
    img.save(path)


def chart_architecture(path: Path) -> None:
    img = Image.new("RGB", (1500, 880), PAPER)
    draw = ImageDraw.Draw(img)
    draw.text((54, 44), "MiniCPM-V 4.6 to Fire Boy VLA", fill=INK, font=font(50, True))
    wrapped(draw, "The demo freezes the vision-language backbone first, adds a state-aware router/action head, then dispatches safe skills into MuJoCo proof policies while Modal runs the live MiniCPM-o pet brain.", (58, 112), 1320, MUTED, 25)
    cards = [
        ((70, 250, 385, 440), "Inputs", "Room camera image, user instruction, robot state, target objects, previous action, stage flags.", "#ffffff"),
        ((455, 250, 770, 440), "Frozen backbone", "MiniCPM-V 4.6 hidden states are mean-pooled into a 1024-d vision-language embedding.", "#eefafa"),
        ((840, 250, 1155, 440), "Router head", "MLP trunk predicts skill logits and continuous target parameters, then applies bounds and stabilization.", "#fff4d7"),
        ((455, 570, 770, 760), "Manipulation VLA", "Residual fusion action head produces normalized 10x32 joint-target chunks for pick/eat rollouts.", "#fff0eb"),
        ((840, 570, 1155, 760), "Skill dispatch", "walk_to, run_around, pick_up, find_and_eat_berry route into MP4-proven policies.", "#ffffff"),
    ]
    for box, title, body, fill in cards:
        draw_card(draw, box, title, body, fill)
    arrows = [
        ((385, 345), (455, 345)),
        ((770, 345), (840, 345)),
        ((997, 440), (997, 570)),
        ((770, 665), (840, 665)),
        ((612, 440), (612, 570)),
    ]
    for start, end in arrows:
        draw.line([start, end], fill=TEAL, width=6)
        ex, ey = end
        if start[0] != end[0]:
            draw.polygon([(ex, ey), (ex - 18, ey - 11), (ex - 18, ey + 11)], fill=TEAL)
        else:
            draw.polygon([(ex, ey), (ex - 11, ey - 18), (ex + 11, ey - 18)], fill=TEAL)
    draw_card(draw, (1210, 250, 1450, 760), "Runtime proof", "Toy Room v3 shows the same chain as UI evidence: command -> router/debug packet -> retargeted Fire Boy rig -> policy gallery MP4/JSON proof.", "#f7fbfa")
    draw.line([(1155, 345), (1210, 345)], fill=TEAL, width=6)
    draw.polygon([(1210, 345), (1192, 334), (1192, 356)], fill=TEAL)
    img.save(path)


def draw_bar_chart(path: Path, title: str, bars: list[tuple[str, float, str]], *, value_suffix: str = "%", max_value: float = 100.0) -> None:
    img = Image.new("RGB", (1500, 900), "#ffffff")
    draw = ImageDraw.Draw(img)
    draw.text((60, 44), title, fill=INK, font=font(43, True))
    chart_x, chart_y, chart_w, chart_h = 130, 160, 1230, 590
    draw.line([(chart_x, chart_y + chart_h), (chart_x + chart_w, chart_y + chart_h)], fill=LINE, width=3)
    draw.line([(chart_x, chart_y), (chart_x, chart_y + chart_h)], fill=LINE, width=3)
    for i in range(6):
        y = chart_y + chart_h - i * chart_h / 5
        draw.line([(chart_x, y), (chart_x + chart_w, y)], fill="#ece9de", width=1)
        label = f"{int(i * max_value / 5)}{value_suffix}"
        draw.text((55, y - 12), label, fill=MUTED, font=font(18))
    slot = chart_w / len(bars)
    for idx, (label, value, color) in enumerate(bars):
        x1 = chart_x + idx * slot + slot * 0.18
        x2 = chart_x + (idx + 1) * slot - slot * 0.18
        height = max(0, min(value, max_value)) / max_value * chart_h
        y1 = chart_y + chart_h - height
        draw.rounded_rectangle((x1, y1, x2, chart_y + chart_h), radius=12, fill=color)
        draw.text((x1 + 4, y1 - 32), f"{value:.0f}{value_suffix}", fill=INK, font=font(22, True))
        wrapped(draw, label, (int(x1), chart_y + chart_h + 26), int(x2 - x1 + 18), INK, size=18, bold=True, line_gap=3)
    img.save(path)


def draw_grouped_bar_chart(path: Path, title: str, labels: list[str], frozen: list[float], lora: list[float]) -> None:
    img = Image.new("RGB", (1500, 900), "#ffffff")
    draw = ImageDraw.Draw(img)
    draw.text((60, 44), title, fill=INK, font=font(42, True))
    draw.rectangle((980, 62, 1018, 82), fill=TEAL)
    draw.text((1030, 55), "Frozen router", fill=INK, font=font(22, True))
    draw.rectangle((980, 102, 1018, 122), fill=CORAL)
    draw.text((1030, 95), "LoRA router", fill=INK, font=font(22, True))
    chart_x, chart_y, chart_w, chart_h = 120, 170, 1260, 560
    max_value = max(frozen + lora) * 1.15
    for i in range(6):
        y = chart_y + chart_h - i * chart_h / 5
        draw.line([(chart_x, y), (chart_x + chart_w, y)], fill="#ece9de", width=1)
        draw.text((42, y - 12), f"{i * max_value / 5:.2f}", fill=MUTED, font=font(18))
    draw.line([(chart_x, chart_y + chart_h), (chart_x + chart_w, chart_y + chart_h)], fill=LINE, width=3)
    slot = chart_w / len(labels)
    for idx, label in enumerate(labels):
        x = chart_x + idx * slot
        for j, (value, color) in enumerate(((frozen[idx], TEAL), (lora[idx], CORAL))):
            x1 = x + slot * (0.18 + j * 0.28)
            x2 = x1 + slot * 0.22
            y1 = chart_y + chart_h - value / max_value * chart_h
            draw.rounded_rectangle((x1, y1, x2, chart_y + chart_h), radius=10, fill=color)
        wrapped(draw, label.replace("_", " "), (int(x + 4), chart_y + chart_h + 24), int(slot - 8), INK, size=17, bold=True, line_gap=3)
    img.save(path)


def draw_line_chart(path: Path, title: str, series: list[tuple[str, list[tuple[float, float]], str]], y_label: str) -> None:
    img = Image.new("RGB", (1500, 900), "#ffffff")
    draw = ImageDraw.Draw(img)
    draw.text((60, 44), title, fill=INK, font=font(42, True))
    chart_x, chart_y, chart_w, chart_h = 130, 170, 1210, 560
    all_x = [x for _, points, _ in series for x, _ in points]
    all_y = [y for _, points, _ in series for _, y in points]
    x_min, x_max = min(all_x), max(all_x)
    y_min, y_max = 0.0, max(all_y) * 1.18
    for i in range(6):
        y = chart_y + chart_h - i * chart_h / 5
        draw.line([(chart_x, y), (chart_x + chart_w, y)], fill="#ece9de", width=1)
        draw.text((42, y - 12), f"{y_min + i * (y_max - y_min) / 5:.3f}", fill=MUTED, font=font(18))
    draw.text((50, 790), y_label, fill=MUTED, font=font(19, True))
    legend_x = 940
    for idx, (name, _, color) in enumerate(series):
        draw.rectangle((legend_x, 62 + idx * 40, legend_x + 38, 82 + idx * 40), fill=color)
        draw.text((legend_x + 50, 55 + idx * 40), name, fill=INK, font=font(22, True))
    for _, points, color in series:
        mapped: list[tuple[float, float]] = []
        for x, y in points:
            px = chart_x + (x - x_min) / max(1e-9, x_max - x_min) * chart_w
            py = chart_y + chart_h - (y - y_min) / max(1e-9, y_max - y_min) * chart_h
            mapped.append((px, py))
        draw.line(mapped, fill=color, width=5)
        for px, py in mapped:
            draw.ellipse((px - 6, py - 6, px + 6, py + 6), fill=color)
    draw.line([(chart_x, chart_y + chart_h), (chart_x + chart_w, chart_y + chart_h)], fill=LINE, width=3)
    draw.line([(chart_x, chart_y), (chart_x, chart_y + chart_h)], fill=LINE, width=3)
    img.save(path)


def build_charts(evidence: dict[str, Any]) -> dict[str, Path]:
    FRONTEND_RESEARCH.mkdir(parents=True, exist_ok=True)
    charts = {
        "architecture": FRONTEND_RESEARCH / "vla-architecture.png",
        "success": FRONTEND_RESEARCH / "vla-success-progression.png",
        "mae": FRONTEND_RESEARCH / "vla-router-param-mae.png",
        "loss": FRONTEND_RESEARCH / "vla-router-loss-curve.png",
        "active": FRONTEND_RESEARCH / "vla-active-skills.png",
        "modeling": FRONTEND_RESEARCH / "vla-modeling-pipeline.png",
        "sync": FRONTEND_RESEARCH / "vla-vm-sync.png",
        "rollouts": FRONTEND_RESEARCH / "vla-rollout-samples.png",
        "parameters": FRONTEND_RESEARCH / "vla-parameter-summary.png",
        "training": FRONTEND_RESEARCH / "vla-training-roadmap.png",
        "future": FRONTEND_RESEARCH / "vla-future-stack.png",
    }
    chart_architecture(charts["architecture"])
    chart_modeling_pipeline(charts["modeling"])
    chart_simulation_sync(charts["sync"])
    chart_rollout_samples(charts["rollouts"])
    chart_parameter_summary(charts["parameters"], evidence)
    chart_training_roadmap(charts["training"], evidence)
    chart_future_stack(charts["future"])
    evals = evidence["evals"]
    draw_bar_chart(
        charts["success"],
        "Experiment success rates",
        [
            ("single-step pick", 100 * evals["one_step_pick"]["success_rate"], CORAL),
            ("chunk pick", 100 * evals["chunk_pick"]["success_rate"], TEAL),
            ("first mixed pick", 100 * evals["initial_pick"]["success_rate"], AMBER),
            ("first mixed eat", 100 * evals["initial_eat"]["success_rate"], AMBER),
            ("focused manip", 100 * evals["manip_pick"]["success_rate"], TEAL),
            ("all-skill go", 100 * evals["allskill_go"]["success_rate"], CORAL),
            ("router skill acc", 100 * evidence["frozen_eval"]["metrics"]["skill_accuracy"], AQUA),
        ],
    )
    metrics_frozen = evidence["frozen_eval"]["metrics"]["param_mae_by_name"]
    metrics_lora = evidence["lora_eval"]["metrics"]["param_mae_by_name"]
    labels = list(metrics_frozen)
    draw_grouped_bar_chart(
        charts["mae"],
        "Router parameter MAE by output",
        labels,
        [float(metrics_frozen[label]) for label in labels],
        [float(metrics_lora[label]) for label in labels],
    )
    frozen_history = evidence["frozen_train"]["history"]
    lora_history = evidence["lora_train"]["history"]
    draw_line_chart(
        charts["loss"],
        "Router validation curve",
        [
            ("frozen val param loss", [(float(row["step"]), float(row["val_param_loss"])) for row in frozen_history], TEAL),
            ("LoRA val param MAE", [(float(row["step"]), float(row["val_param_mae"])) for row in lora_history], CORAL),
        ],
        "lower is better",
    )
    draw_bar_chart(
        charts["active"],
        "Final active skill proof",
        [
            ("walk_to 20/20", 100 * evals["walk_clock"]["success_rate"], TEAL),
            ("run_around 20/20", 100 * evals["run_policy"]["success_rate"], TEAL),
            ("pick_up LoRA 3/3", 100 * evals["lora_pick"]["success_rate"], CORAL),
            ("eat_berry LoRA 3/3", 100 * evals["lora_eat"]["success_rate"], CORAL),
            ("frozen router 512/512", 100 * evidence["frozen_eval"]["metrics"]["skill_accuracy"], AQUA),
            ("LoRA router 256/256", 100 * evidence["lora_eval"]["metrics"]["skill_accuracy"], AQUA),
        ],
    )
    return charts


def p(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(text, style)


def bullets(items: list[str], style: ParagraphStyle) -> ListFlowable:
    return ListFlowable(
        [ListItem(Paragraph(item, style), leftIndent=12) for item in items],
        bulletType="bullet",
        leftIndent=16,
        bulletFontName="Helvetica",
        bulletFontSize=8,
    )


def table(rows: list[list[Any]], widths: list[float], header: bool = True) -> Table:
    processed = []
    cell_style = ParagraphStyle("Cell", fontName="Helvetica", fontSize=8.3, leading=10.3, textColor=colors.HexColor(INK))
    head_style = ParagraphStyle("HeadCell", parent=cell_style, fontName="Helvetica-Bold", textColor=colors.white)
    for row_index, row in enumerate(rows):
        processed.append([
            cell if not isinstance(cell, str) else Paragraph(cell, head_style if row_index == 0 and header else cell_style)
            for cell in row
        ])
    tbl = Table(processed, colWidths=widths, repeatRows=1 if header else 0)
    commands = [
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor(LINE)),
        ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor(LINE)),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]
    if header:
        commands.extend([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(TEAL)),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ])
    for row in range(1 if header else 0, len(rows)):
        if row % 2 == 0:
            commands.append(("BACKGROUND", (0, row), (-1, row), colors.HexColor("#fbf8ef")))
    tbl.setStyle(TableStyle(commands))
    return tbl


def add_footer(canvas: Any, doc: Any) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor(MUTED))
    canvas.drawString(0.65 * inch, 0.38 * inch, "Fire Boy MiniCPM-V 4.6 VLA research paper")
    canvas.drawRightString(7.85 * inch, 0.38 * inch, f"Page {doc.page}")
    canvas.restoreState()


def build_pdf(evidence: dict[str, Any], charts: dict[str, Path]) -> None:
    OUTPUT_PDF_DIR.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("TitleBig", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=27, leading=31, alignment=TA_CENTER, textColor=colors.HexColor(INK), spaceAfter=12))
    styles.add(ParagraphStyle("Subtitle", parent=styles["Normal"], fontSize=11.5, leading=15, alignment=TA_CENTER, textColor=colors.HexColor(MUTED), spaceAfter=16))
    styles.add(ParagraphStyle("Section", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=17, leading=21, textColor=colors.HexColor(TEAL), spaceBefore=12, spaceAfter=7))
    styles.add(ParagraphStyle("Subsection", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=12.5, leading=15, textColor=colors.HexColor(INK), spaceBefore=9, spaceAfter=5))
    styles.add(ParagraphStyle("BodyCopy", parent=styles["BodyText"], fontSize=9.7, leading=13.2, textColor=colors.HexColor(INK), spaceAfter=6))
    styles.add(ParagraphStyle("Small", parent=styles["BodyText"], fontSize=8.2, leading=10.5, textColor=colors.HexColor(MUTED), spaceAfter=5))
    styles.add(ParagraphStyle("Pull", parent=styles["BodyText"], fontName="Helvetica-Bold", fontSize=11.2, leading=15, textColor=colors.HexColor(TEAL), leftIndent=12, rightIndent=12, spaceBefore=8, spaceAfter=8))
    styles.add(ParagraphStyle("CodeBlock", parent=styles["Code"], fontName="Courier", fontSize=7.4, leading=9.4, textColor=colors.HexColor(INK), backColor=colors.HexColor("#f6f3ea"), borderColor=colors.HexColor(LINE), borderWidth=0.4, borderPadding=6, spaceBefore=6, spaceAfter=8))
    doc = SimpleDocTemplate(str(PDF_PATH), pagesize=letter, rightMargin=0.62 * inch, leftMargin=0.62 * inch, topMargin=0.62 * inch, bottomMargin=0.62 * inch)
    story: list[Any] = []
    body = styles["BodyCopy"]
    small = styles["Small"]

    story.append(p("Turning MiniCPM-V 4.6 Into a Fire Boy Vision-Language-Action Policy", styles["TitleBig"]))
    story.append(p("Technical report v3 - A practical, arXiv-style account of AI-age virtual pets, frozen vision-language backbones, SAM-to-rig asset construction, residual action heads, skill-parameter routers, MuJoCo/Newton simulation lanes, RunPod training evidence, Modal inference, and OpenAI Codex-assisted experiment iteration.", styles["Subtitle"]))
    story.append(PdfImage(str(charts["architecture"]), width=7.0 * inch, height=4.1 * inch))
    story.append(Spacer(1, 0.12 * inch))
    story.append(p("<b>Abstract.</b> This paper documents the path from a general multimodal model, MiniCPM-V 4.6, to an embodied VLA controller for Fire Boy, a small rigged virtual pet. The central engineering decision was to freeze the MiniCPM-V backbone first, extract a stable vision-language embedding, and train small action modules around it: a state-residual action head for contact-rich manipulation and a skill-parameter router for demo-safe open-ended commands. The best shipped route is not a single monolithic low-level policy. It is a router that selects proven skills and predicts continuous target parameters, while separate policy lanes supply movement, manipulation, retargeting, proof videos, and runtime UI evidence.", body))
    story.append(p("<b>Core result.</b> Single-step manipulation failed at 0/20. Chunked manipulation reached 20/20. A frozen MiniCPM-V residual action head reached 3/3 pick and 3/3 eat on RunPod. A LoRA manipulation variant also reached 3/3 and 3/3 in the eval-only gate. The final frozen skill-parameter router reached 512/512 skill decisions with mean parameter MAE 0.0170; the LoRA router kept perfect skill classification but had worse eval MAE at 0.0629, so the frozen router remained the safer promoted model.", styles["Pull"]))

    story.append(p("Project Objective: An AI-Age Virtual Toy", styles["Section"]))
    story.append(p("The project objective came from a prior attempt to build a real robot. The practical question became: what if the most important part of the robot could be built first as a virtual toy? Fire Boy is meant to sit in the lineage of Talking Tom, Tamagotchi, and imaginary Pokemon-like companions, but updated for multimodal AI, physics, memory, and learned action. The goal is not a mascot over a chatbot. The goal is a small creature that sees its room, understands speech and text, forms habits, plays with objects, reacts physically, and makes bounded decisions on its own.", body))
    story.append(p("That motivation changes the technical requirements. A virtual pet cannot feel alive if every behavior is a hard-coded animation. It needs perception, action, feedback, memory, and a loop that can improve from rollouts. A real robot would add hardware cost and safety complexity immediately; a virtual body lets the project explore embodiment first: rigging, collisions, grasping, retargeting, reward design, state tracking, and personality. The hackathon artifact is intentionally small, but it tests the core thesis that a tiny VLA plus a toy-room physics stack can become the seed of a living digital companion.", body))
    story.append(table([
        ["Design goal", "What it means in this build"],
        ["Natural interaction", "Typed/spoken commands map into PET actions, router decisions, and visible Fire Boy behavior."],
        ["Embodied agency", "The pet receives room images, state, targets, prior action, and stage flags before acting."],
        ["Habits and personality", "Future work adds memory, style rewards, curiosity rewards, and multi-agent toy interactions."],
        ["Small-model access", "MiniCPM-class backbones keep experiments closer to consumer-grade deployment than giant VLA stacks."],
        ["Real-robot bridge", "A virtual humanoid pet can eventually share training ideas with physical humanoid robots once hardware is ready."],
    ], [1.6 * inch, 5.3 * inch]))

    story.append(p("Contributions", styles["Section"]))
    story.append(bullets([
        "A reproducible asset pipeline from concept image to SAM-derived base body, Blender skeleton, GLB animation clips, MuJoCo matching, and Toy Room browser retargeting.",
        "A MiniCPM-V 4.6 frozen-encoder VLA router that predicts four embodied skills and six continuous parameters with 814,090 trainable head parameters.",
        "A residual low-level action head with 1,078,912 trainable parameters for 10-step x 32-actuator manipulation chunks.",
        "A direct comparison between frozen-router and LoRA-router behavior, including exact adapter size: 4,743,168 LoRA trainable parameters across language-model layers 0-23.",
        "An evidence-first workflow: every promoted behavior is tied to manifest rows, eval JSON, screenshots, or rendered MP4/GIF proof.",
    ], body))

    story.append(PageBreak())
    story.append(p("Asset Modeling: From Concept Art to Rigged Avatar", styles["Section"]))
    story.append(PdfImage(str(charts["modeling"]), width=7.0 * inch, height=5.13 * inch))
    rig = evidence["rig_report"]
    story.append(p("The embodied policy only works because the visual character, browser rig, and simulator body share a consistent skeleton. Fire Boy began as a 2D source character, then moved through SAM-style segmentation and 3D extraction, cleanup, base-body rigging, skeleton placement, animation authoring, and MuJoCo body matching. The rig report records a single connected body component, 3,311 vertices, zero unweighted vertices, and no rigidified runaway shells for the Fire Boy base body.", body))
    story.append(table([
        ["Pipeline stage", "Artifact", "Implementation note"],
        ["Source art", "potential-char-images/fire-boy.png", "Reference image for identity, silhouette, flame crown, proportions, and color."],
        ["SAM/extraction", "assets/generated/previews/fire-boy-sam-cleaned.png", "The raw generated/SAM body is cleaned into a standing unclothed base body."],
        ["Rig build", "fire-boy-rig/working/build_rig.py", "Builds Root -> Hips -> Spine -> Chest -> Neck -> Head -> Crown, plus shoulders, elbows, hands, hips, knees, and feet."],
        ["Animation export", "fire-boy-rig/working/animate_and_export.py", "Authors idle, walk, run, jump, wave, cheer, dance, spin, throw, and sit clips for glTF export."],
        ["Browser runtime", "fire-boy-rig/fire-boy-rigged-full.glb", "Three.js loads the same GLB for Toy Room v3 and the rigged-character inspector."],
    ], [1.2 * inch, 2.35 * inch, 3.35 * inch]))
    story.append(Preformatted("""# Rebuild rigged avatars from the repo root
blender --background --python fire-boy-rig/working/build_rig.py
blender --background --python fire-boy-rig/working/animate_and_export.py

# Rig quality checks written by the build
fire-boy-rig/working/fire-boy-rig-report.json
fire-boy-rig/previews/fire-boy-fullrig-bones.png""", styles["CodeBlock"]))

    story.append(p("Skeleton, MuJoCo Body, and Retarget Synchronization", styles["Section"]))
    align = evidence["skeleton_alignment"]["summary"]
    articulated = evidence["articulated_report"]["report"]
    story.append(p("The MuJoCo model is deliberately not the original high-detail mesh. The training body is a simplified MJCF tree with robust primitive geometry, contact sites, and 32 actuators. This avoids fragile raw-mesh collision during early training. The skeleton inspection script maps the GLB rig points to the MuJoCo body points; the current alignment report has 22 common points and a max normalized point error of 0.0 for the exported matching pass.", body))
    story.append(table([
        ["Quantity", "Value", "Meaning"],
        ["GLB/MuJoCo common points", str(align["common_points"]), "Named skeleton landmarks shared by browser rig and simulator body."],
        ["Max normalized point error", str(align["max_normalized_point_error"]), "Alignment error after the matching transform in the inspected skeleton overlay."],
        ["MuJoCo bodies", str(articulated["nbody"]), "Simplified physical body tree for stable control."],
        ["MuJoCo joints", str(articulated["njnt"]), "Root slides/yaw plus limb, torso, wrist, gripper, and leg joints."],
        ["Actuators", str(articulated["nu"]), "The 32-dimensional action vector used by action chunks."],
    ], [1.9 * inch, 1.0 * inch, 4.0 * inch]))
    story.append(Preformatted("""# Body proof lane
python fireboy-vla-physics/src/inspect_fireboy_alignment.py
python fireboy-vla-physics/src/render_articulated_fireboy.py --mode body

# Runtime bridge idea
MuJoCo qpos/action trace -> retargetTrajectory -> Three.js GLB bones
object state -> heldObjectAnchor -> browser toy interaction""", styles["CodeBlock"]))

    story.append(PageBreak())
    story.append(p("Virtual Machines, Artifact Sync, and Reproducibility", styles["Section"]))
    story.append(PdfImage(str(charts["sync"]), width=7.0 * inch, height=4.2 * inch))
    story.append(p("The system used local development for orchestration and UI, RunPod GPU pods for MiniCPM-V encoding/training/evaluation, and Modal for the live MiniCPM-o browser action brain. The important discipline was to copy artifacts back into stable repo paths before claiming success: checkpoints under runpod-artifacts/checkpoints, MP4/GIF evidence under runpod_artifacts, summaries under vla-rollouts, and browser-facing proof pages under frontend. Pods were treated as disposable; the repo became the memory of the experiment.", body))
    story.append(bullets([
        "Local machine: authored scripts, generated pages/PDF, served FastAPI/Gradio app, ran browser QA, and kept the policy registry visible.",
        "RunPod RTX 6000 Ada: scaled frozen residual MiniCPM-V action-head training and manipulation evaluation.",
        "RunPod NVIDIA A40: trained and evaluated the frozen and LoRA skill-parameter routers.",
        "Modal L40S: hosted the MiniCPM-o 4.5 WebSocket gateway with Volume cache and Secret-based model access.",
        "NVIDIA Newton/Warp: documented as the next GPU physics lane for rollout throughput and USD/MJCF-compatible traces.",
    ], body))

    story.append(p("VLA Head Sizes and Sampling", styles["Section"]))
    story.append(PdfImage(str(charts["parameters"]), width=7.0 * inch, height=4.2 * inch))
    counts = evidence["param_counts"]
    story.append(p(f"The promoted frozen router trains only the head: {counts['frozen_skill_param_router_head']:,} parameters over a 1066-dimensional fused input. The input is 1024 MiniCPM-V vision-language features plus 42 state features. The residual action head is larger, {counts['residual_action_head']['total']:,} parameters, because it contains a state controller branch, a vision-language branch, and a residual fusion branch that outputs a 10-step by 32-actuator action chunk. The LoRA experiments add {counts['lora_adapter']['total']:,} adapter parameters at rank 8 across q_proj, k_proj, v_proj, o_proj, gate_proj, up_proj, and down_proj modules on 24 language-model layers.", body))
    story.append(table([
        ["Model piece", "Trainable parameters", "Notes"],
        ["Frozen skill-parameter router head", f"{counts['frozen_skill_param_router_head']:,}", "Two 512-wide MLP trunk layers plus skill and parameter heads."],
        ["Residual action head", f"{counts['residual_action_head']['total']:,}", f"State branch {counts['residual_action_head']['state_head']:,}; VL branch {counts['residual_action_head']['vl_head']:,}; residual branch {counts['residual_action_head']['residual_head']:,}."],
        ["LoRA adapter", f"{counts['lora_adapter']['total']:,}", f"{counts['lora_adapter']['tensor_count']} tensors across layers {counts['lora_adapter']['min_layer']}-{counts['lora_adapter']['max_layer']}."],
        ["Base MiniCPM-V 4.6", "Frozen for promoted router", "The report trains heads/adapters, not the full backbone, in the promoted path."],
    ], [2.0 * inch, 1.6 * inch, 3.3 * inch]))
    story.append(Preformatted("""# Router head architecture
features = concat(normalize(vl_embedding_1024), normalize(robot_state_42))
h = SiLU(Linear(1066, 512)(features))
h = SiLU(Linear(512, 512)(h))
skill_logits = Linear(512, 4)(h)
params = Linear(512, 6)(h)

loss = cross_entropy(skill_logits, skill_id) + 0.35 * mse(params, target_params)""", styles["CodeBlock"]))

    story.append(PageBreak())
    story.append(p("Sampling and Rollout Rows", styles["Section"]))
    story.append(PdfImage(str(charts["rollouts"]), width=7.0 * inch, height=4.67 * inch))
    story.append(p("The dataset is assembled from rendered rollout observations rather than from still screenshots alone. The first four-skill manifest contained 64 episodes and 2,368 image/manifest rows, with 16 episodes per task and a stride of 5 simulation steps. The focused manipulation manifest expanded contact tasks to 144 episodes and 6,192 rows, still using 10-step chunks. The all-skill skill-parameter manifest wrote 3,072 rows with images required: 1,028 pick_up, 1,052 go_eat_berry, 512 run_around, and 480 go_to_point.", body))

    story.append(p("Policy Training Ladder", styles["Section"]))
    story.append(PdfImage(str(charts["training"]), width=7.0 * inch, height=4.2 * inch))
    story.append(p("The policy was trained as a staged system instead of a single heroic end-to-end model. Behavior cloning was the first useful tool because it directly pairs observations with successful actions. It made the data path inspectable, but it also exposed why one-step control is weak for contact. Action chunks fixed the phase problem for manipulation by asking the head to emit a short future trajectory. The residual VLA head then let MiniCPM-V features adjust a state-dominant controller. The skill-parameter router became the public demo layer because it routes into skills that already have closed-loop proof.", body))
    story.append(bullets([
        "Why behavior cloning first: it is stable, cheap, and lets every row be inspected as image + command + state + label.",
        "Why action chunks: they preserve approach, contact, lift, and transfer phases that a single next action averages away.",
        "Why a router for the demo: the router can choose the right proved skill while low-level policies continue improving separately.",
        "Why RL later: reinforcement learning is powerful only after the simulator can generate enough randomized successes, failures, recoveries, and reward diagnostics.",
    ], body))

    story.append(p("1. Problem Statement", styles["Section"]))
    story.append(p("MiniCPM-V 4.6 already sees images and reads language, but it does not naturally emit MuJoCo joint targets, stable navigation parameters, or a browser-safe action contract. A VLA conversion therefore has three jobs: preserve the multimodal understanding, expose robot state, and constrain the model's output into actions that can be executed, evaluated, and debugged. Fire Boy makes this concrete: the model sees a toy room frame, reads a command such as “pick up the berry” or “walk toward me,” receives body and target state, and must produce either a short joint-action chunk or a skill with continuous parameters.", body))
    story.append(bullets([
        "Inputs: image, instruction, robot state, target/object metadata, previous action, task and stage flags.",
        "Backbone: MiniCPM-V 4.6 with a 1024-dimensional pooled vision-language feature in the training artifacts.",
        "Outputs: either normalized joint target chunks, or a high-level skill id plus target_x, target_y, target_z, radius, speed_hint, and object_is_berry.",
        "Runtime contract: every model decision must fit the Toy Room PET action path, policy gallery proof, and trace/debug panels.",
    ], body))

    story.append(p("2. General Recipe: Turning Any VLM Into a VLA", styles["Section"]))
    story.append(p("The Fire Boy system is useful as a recipe because it does not require the base model to be born as a robot model. In theory, any model with stable image-language hidden states can become a VLA if the surrounding system supplies proprioception, action labels, loss functions, and closed-loop evaluation.", body))
    recipe_rows = [
        ["Step", "Purpose", "Fire Boy implementation"],
        ["Freeze first", "Avoid destabilizing visual-language knowledge while the action interface is still immature.", "MiniCPM-V parameters are frozen for the first router/action-head runs; only compact heads learn."],
        ["Add state", "A VLM cannot infer joint velocity, grasp status, root pose, or previous action from pixels alone.", "State vectors include navigation geometry, hand/mouth/object positions, task flags, stage flags, grasp/eaten bits, and previous action."],
        ["Choose action granularity", "Low-level actions are expressive but brittle; skills are safer for demos and sparse data.", "The project tested one-step actions, action chunks, residual low-level heads, and finally a skill-parameter router."],
        ["Train on successful rollouts", "Behavior cloning needs aligned observations and actions from trajectories that actually solve the task.", "RunPod-generated MuJoCo rollouts and MiniCPM-V image manifests produced JSONL rows with images, state, commands, and labels."],
        ["Close the loop", "Offline loss is not enough for physics. The model must survive compounding error.", "Every promoted claim required eval JSON and MP4/GIF proof."],
        ["Adapt later", "LoRA can tune the backbone once the head and labels are reliable.", "LoRA rank 8 / alpha 16 runs were tested after frozen residual/router baselines."],
    ]
    story.append(table(recipe_rows, [0.95 * inch, 2.0 * inch, 4.0 * inch]))

    story.append(p("2.1. VLA Conversion Methods Beyond This Build", styles["Subsection"]))
    story.append(p("The current method is deliberately conservative: freeze MiniCPM-V, expose robot state, and train compact heads. It is a good hackathon route because it is cheap and debuggable, but it is not the only way to build a VLA. The next serious study should compare several routes under the same simulator, same objects, and same closed-loop scoring.", body))
    story.append(table([
        ["Method", "Mechanism", "Main advantage", "Main risk"],
        ["Frozen encoder + head", "Train MLP/router/action heads on top of MiniCPM-V embeddings.", "Stable and cheap; good for first demos.", "May not adapt visual-language features to action semantics."],
        ["LoRA / QLoRA", "Add low-rank adapters to attention/MLP layers plus heads.", "More expressive while still much cheaper than full fine-tuning.", "Can preserve skill accuracy while degrading coordinates, as this run showed."],
        ["Action-token fine-tuning", "Teach the model to emit structured skill tokens, coordinates, or action chunks.", "Closer to a single-brain controller.", "Needs strict validation or malformed actions can enter the runtime."],
        ["Diffusion / flow policy head", "Generate trajectory chunks from a learned action distribution.", "Good for playful or multimodal behavior where many actions are valid.", "Harder to debug and usually needs more data."],
        ["World model + planner", "Predict future latent states, then plan or search over actions.", "Best for long-horizon pet goals and habits.", "More moving pieces and more failure modes."],
        ["Imitation + RL", "Start from behavior cloning, then improve with simulated rewards.", "Can discover recovery behavior and style.", "Reward hacking if the sim and reward are immature."],
    ], [1.1 * inch, 2.05 * inch, 1.85 * inch, 1.9 * inch]))

    story.append(PageBreak())
    story.append(p("3. Model and Router Architecture", styles["Section"]))
    story.append(p("The final router is intentionally small. MiniCPM-V supplies a pooled multimodal embedding. A state vector supplies the body and task variables the image cannot reliably encode. The router concatenates normalized vision-language and state features, passes them through a SiLU MLP trunk, and emits two heads: a categorical skill head and a continuous parameter head.", body))
    story.append(table([
        ["Router part", "What it does", "Why it exists"],
        ["MiniCPM-V encoder", "Runs the image/instruction through MiniCPM-V 4.6 and mean-pools final hidden states with the attention mask.", "Provides visual-language grounding without training the whole model on the first pass."],
        ["State constructor", "Builds direct or derived features from robot_state, scene targets, nav clock, hand/mouth/object positions, task flags, stage flags, previous action, grasp/eaten bits.", "Prevents the VLM from hallucinating proprioception and gives the head closed-loop context."],
        ["MLP trunk", "Linear -> SiLU -> Linear -> SiLU over the fused vector.", "Small enough to train fast on RunPod while still learning task-conditioned parameter maps."],
        ["Skill head", "Predicts walk_to, run_around, pick_up, or find_and_eat_berry.", "Turns open-ended language into a bounded action vocabulary with proof videos."],
        ["Parameter head", "Predicts target_x, target_y, target_z, radius, speed_hint, object_is_berry.", "Carries continuous grounding into the skill policies."],
        ["Bounds and stabilizers", "Clips parameters to scene-safe ranges, copies explicit target coordinates from parsed scene metadata, and prefers heuristic skill when commands are explicit unless forced neural.", "Makes the demo robust: the learned router participates without allowing unsafe or incoherent outputs."],
        ["Dispatch", "Maps the chosen skill to registry:walk_to, registry:run_around, registry:pick_up, or registry:find_and_eat_berry.", "Connects model choice to the same execution path used by Toy Room v3 and the policy gallery."],
    ], [1.25 * inch, 2.7 * inch, 2.95 * inch]))
    story.append(p("This router is not a cheat around VLA. It is one of the two useful forms of VLA for small embodied demos: instead of emitting every motor command directly, it emits the next embodied skill and its grounded parameters. That is still vision-language-action: pixels and language condition a physical action, but the action is represented at the level where the available data is reliable.", body))

    story.append(p("4. Action Heads and Why Chunks Won", styles["Section"]))
    story.append(p("The low-level branch trained action heads that output joint targets. The failed first attempt predicted a single action per state. For manipulation, that collapses phases such as approach, reach above, descend, close, lift, and mouth transfer into an averaged control. The result looked plausible in loss but failed closed-loop contact. The fix was action chunking: predict a short horizon of future joint targets so the head can represent phase progression.", body))
    story.append(PdfImage(str(charts["success"]), width=7.0 * inch, height=4.2 * inch))
    story.append(table([
        ["Experiment", "Data / architecture", "Closed-loop result", "Interpretation"],
        ["Single-step pick/eat", "State-action policy, no chunk horizon.", "pick_up 0/20; go_eat_berry 0/20.", "Averaged across contact phases; could not close grasp/eat loops."],
        ["Chunked manipulation", "Action chunks for pick_up and go_eat_berry.", "pick_up 20/20; go_eat_berry 20/20.", "Temporal chunking made phase transitions learnable."],
        ["First mixed manifest", "64 episodes, 2368 image rows, four tasks.", "pick_up 2/8, eat 2/8, run 8/8, go_to 7/8.", "Pipeline worked, but contact tasks were underrepresented."],
        ["Focused manip manifest", "144 episodes, 6192 rows, pick/eat focus.", "pick_up 12/12; go_eat_berry 12/12.", "Data balance mattered more than model novelty."],
        ["Frozen residual MiniCPM-V head", "2048 rows, state_residual_fusion_v1, VL residual scale 0.12, action_std_floor 0.01.", "pick_up 3/3; go_eat_berry 3/3.", "State-dominant controller plus small VL residual was stable."],
        ["All-skill direct action head", "3072 rows across manipulation and movement.", "pick_up 2/2, run 2/2, eat 0/2, go_to 0/2.", "One shared low-level head was not reliable enough for the demo."],
    ], [1.35 * inch, 2.2 * inch, 1.35 * inch, 2.0 * inch]))

    story.append(PageBreak())
    story.append(p("5. Losses, MAE, and What the Curves Say", styles["Section"]))
    frozen_metrics = evidence["frozen_eval"]["metrics"]
    lora_metrics = evidence["lora_eval"]["metrics"]
    story.append(p(f"The promoted frozen router trained on {evidence['frozen_train']['rows']} rows ({evidence['frozen_train']['train_rows']} train, {evidence['frozen_train']['val_rows']} validation) and evaluated on {evidence['frozen_eval']['rows']} rows. Its skill accuracy was {frozen_metrics['skill_accuracy']:.3f}, with overall parameter MAE {frozen_metrics['param_mae']:.4f}. The LoRA router trained on {evidence['lora_train']['rows']} rows and evaluated on {evidence['lora_eval']['rows']} rows. It also achieved perfect skill accuracy, but its parameter MAE rose to {lora_metrics['param_mae']:.4f}. That is why the frozen router is the safer public demo router even though the LoRA run proved the backbone can be adapted.", body))
    story.append(PdfImage(str(charts["loss"]), width=7.0 * inch, height=4.2 * inch))
    story.append(Spacer(1, 0.08 * inch))
    story.append(PdfImage(str(charts["mae"]), width=7.0 * inch, height=4.2 * inch))
    story.append(p("The LoRA router's confusion matrix was still perfect, so the failure mode was not command classification. The problem was parameter precision, especially target_y. For embodied control, small coordinate errors become visible because the downstream skill has to move through space and interact with objects. This is a good example of why VLA evaluation cannot stop at language accuracy.", body))

    story.append(PageBreak())
    story.append(p("6. Final Demo Policy Stack", styles["Section"]))
    story.append(PdfImage(str(charts["active"]), width=7.0 * inch, height=4.2 * inch))
    story.append(table([
        ["Final skill", "Policy source", "Evidence"],
        ["walk_to", "mujoco_articulated_policy go_to_point clock policy", "20/20 eval success, local Toy Room trajectory retargeting, player-camera target support."],
        ["run_around", "mujoco_articulated_policy run_around", "20/20 eval success and live route retargeting."],
        ["pick_up", "MiniCPM-V LoRA manipulation checkpoint / rollout manifest bridge", "3/3 eval gate; Toy Room v3 retargeted object anchoring to Fire Boy hands."],
        ["find_and_eat_berry", "MiniCPM-V LoRA manipulation checkpoint / rollout manifest bridge", "3/3 eval gate; live bridge reports eaten state and mouth transfer."],
        ["router", "Frozen MiniCPM-V skill-parameter head", "512/512 skill decisions, parameter MAE 0.0170, perfect 4x4 confusion matrix."],
    ], [1.25 * inch, 2.3 * inch, 3.35 * inch]))
    story.append(p("The runtime bridge retargets proof trajectories onto the Fire Boy GLB body. Movement skills use articulated MuJoCo rollout trajectories. Pick and eat use successful MiniCPM-V rollout-manifest joint states while preserving the object interaction. This distinction matters: the public demo is honest that contact-rich grasping is proven through recorded/evaluated policy paths and retargeting, not through a fully generalized learned grasp planner for every new object.", body))

    story.append(p("7. Simulation: MuJoCo, NVIDIA Newton, and Why Physics Was the Bottleneck", styles["Section"]))
    story.append(p("The project treated physics as the source of truth. MuJoCo generated the concrete policy proof for this build: eval JSON, MP4/GIF rollouts, body rendering, and Toy Room trajectory retargeting. NVIDIA Newton was investigated as the next GPU physics lane because it is designed around NVIDIA Warp/OpenUSD and can align with MuJoCo Warp-style workflows. The plan was to load or adapt the Fire Boy MJCF/URDF asset, validate CUDA rollouts, export qpos/action traces, and produce MP4/USD/NPZ artifacts. The final artifact remains MuJoCo-backed; Newton is documented as the GPU scaling path rather than overclaimed as the source of the shipped proof.", body))
    story.append(bullets([
        "Newton lane target: Fire Boy asset -> Newton/MuJoCo Warp load test on cuda:0 -> rollout qpos/action trace -> MP4/USD/NPZ proof.",
        "Fallback rule: if direct Fire Boy adapter fails, validate Newton with a supported robot example and keep Fire Boy in the MuJoCo lane.",
        "Reason to care: VLA quality is bounded by simulation quality. Better GPU rollout throughput means more diverse image-state-action data and more closed-loop failures found before the browser demo.",
    ], body))

    story.append(p("8. Hardware and Cloud Runtime", styles["Section"]))
    story.append(table([
        ["Component", "Hardware / service", "Role"],
        ["Modal MiniCPM-o runtime", "Modal L40S GPU, Modal Volume minicpm-omni-cache, Modal Secret for Hugging Face token.", "Live Toy Room v3 action-brain gateway for MiniCPM-o 4.5, with serverless scale-to-zero behavior."],
        ["MiniCPM-V residual action head", "RunPod NVIDIA RTX 6000 Ada Generation.", "Frozen MiniCPM-V 4.6 manipulation head, 2048 rows, 3/3 pick and 3/3 eat."],
        ["Frozen skill-parameter router", "RunPod NVIDIA A40.", "MiniCPM-V 4.6 frozen router, 512-row held-out eval with perfect skill accuracy."],
        ["LoRA skill-parameter router", "RunPod NVIDIA A40.", "Rank 8 / alpha 16 adapter experiment; perfect skill selection but worse parameter MAE."],
        ["Local app", "FastAPI/Gradio-style local server plus Three.js/CANNON frontend.", "Playable browser surface, screenshot evidence, PDF/page delivery, policy gallery, and debug APIs."],
    ], [1.45 * inch, 2.35 * inch, 3.1 * inch]))

    story.append(PageBreak())
    story.append(p("9. Modal Inference and Toy Room Integration", styles["Section"]))
    story.append(p("Modal is used for serverless multimodal inference rather than batch training in the shipped browser path. The Modal app wraps the OpenBMB MiniCPM-o 4.5 demo stack, caches model weights in a Modal Volume, and exposes a WebSocket chat gateway. Toy Room v3 sends one command-driven /api/pet-action call per typed, spoken, or quick-button command. The server opens one Modal turn, validates streamed model output into the PET action JSON contract, records tokens/latency/debug fields, and sends a bounded update back to the browser.", body))
    story.append(p("This matters for demo quality because the model is load-bearing but not mysterious. The page can show which brain mode is active, how many tokens were used, whether a fallback policy ran, and which target or skill was selected. The same transparency pattern is used for the VLA router: the compact router result contains skill, confidence, neural skill, parameters, dispatch, policy kind, model id, device, and latency.", body))

    story.append(p("9.1. Full Fine-Tuning and Single-Brain Future", styles["Subsection"]))
    story.append(PdfImage(str(charts["future"]), width=7.0 * inch, height=4.2 * inch))
    story.append(p("The long-term version can use a MiniCPM-V, MiniCPM-o, or future MiniCPM/Omni-class model as the slow high-level pet brain. Full fine-tuning would train on multimodal episodes: observation frames, state summaries, user utterances, action tokens, reward tags, memory events, and outcome labels. The model could learn to emit structured plans such as choose_goal, choose_skill, target_object, target_pose, and style. A validated runtime would then translate those plans into fast motor policies.", body))
    story.append(p("A single brain is attractive because it can unify perception, memory, language, and action. The practical architecture should still be hierarchical. The slow brain can run on Modal or a warm GPU worker and decide what the pet wants to do. A small local reflex policy should run in milliseconds and handle continuous motion, contact correction, object attachment, and animation blending. This split is what makes the pet feel responsive while still letting a multimodal model provide personality and reasoning.", body))
    story.append(table([
        ["Optimization target", "Technique"],
        ["Startup cost", "Warm Modal containers, cached model weights, preloaded tokenizer/processor, and persistent volume cache."],
        ["Per-turn latency", "Compress state, reuse image/frame embeddings, stream output, and validate compact action JSON instead of long prose."],
        ["Millisecond actions", "Distill learned skills into local heads; run WebGPU/WASM/ONNX or a small server-side policy in the inner loop."],
        ["Cost", "Quantization, LoRA adapters, smaller MiniCPM-class backbones, and routing only hard perception moments to the big brain."],
        ["Quality", "Mine failed rollouts, add recovery demonstrations, run DAgger-style relabeling, and use RL only after reward checks are robust."],
    ], [1.7 * inch, 5.2 * inch]))

    story.append(p("10. Codex as the Experiment Partner", styles["Section"]))
    story.append(p("OpenAI Codex was not only used to write prose at the end. The repo history shows Codex-assisted implementation and hardening across the build: shipping Toy Room v3, adding the Fire Boy command loop, wiring a MiniCPM-V action brain, routing Toy Room v3 through Modal MiniCPM, adding trace diagnostics, hardening Modal WebSocket timeouts, keeping the MiniCPM-V loop live, making locomotion and pickup physical, grounding pickup targets, and adding grounded gestures. In practical terms, OpenAI Codex helped turn a messy research loop into commit-sized steps: scaffold a path, run the app, inspect artifacts, patch the exact boundary that failed, and preserve the evidence trail.", body))
    story.append(table([
        ["Commit theme", "What Codex helped stabilize"],
        ["Toy Room v3 ship path", "Single Fire Boy demo page, controls, command loop, and playable action surface."],
        ["MiniCPM-V action brain", "Vision/action route, endpoint configurability, and fallback honesty."],
        ["Modal MiniCPM route", "Serverless WebSocket adapter, action JSON validation, timeout hardening, and trace metrics."],
        ["Physics grounding", "Pickup targets, locomotion, gestures, policy gallery proof, and browser-visible debug panels."],
        ["Research artifacts", "Runbooks, experiment summaries, screenshots, PDF/page generation, and presentable demo narrative."],
    ], [1.65 * inch, 5.25 * inch]))

    story.append(p("11. What Failed and Why That Was Useful", styles["Section"]))
    story.append(p("The failures are the most important part of the paper because they explain the final architecture. Direct low-level VLA is seductive, but small embodied agents expose every weakness: contact discontinuities, phase averaging, root drift, saturation, and data imbalance. The direct go_to_point MiniCPM-V variants failed repeatedly at 0/5 in one-step, root-velocity, and recovery-data settings. The all-skill low-level head failed eat and go_to_point despite passing pick and run. These failures argued for a router-first public demo and a continued research lane for low-level policies.", body))
    story.append(bullets([
        "One-step actions lost phase information; action chunks fixed manipulation.",
        "A single mixed low-level head underfit the different control regimes of contact manipulation and navigation.",
        "LoRA improved adaptability but did not automatically improve numeric grounding; frozen router parameters were better in the held-out eval.",
        "Closed-loop evaluation found problems that offline loss alone would have hidden.",
    ], body))

    story.append(p("12. Limitations and Next Work", styles["Section"]))
    story.append(p("The current demo is best described as a practical VLA system, not a solved general robotics model. It can route commands, ground targets, and show evaluated policy rollouts in action. It does not yet prove arbitrary contact-rich grasping of every object, long-horizon household planning, or Newton-native Fire Boy training at scale. The right next work is to push the Newton/Warp lane, generate larger randomized rollouts, keep the router as the safe outer policy, and train specialized low-level heads per skill until each skill can survive broader closed-loop randomized tests.", body))
    story.append(bullets([
        "Promote frozen router for demo; keep LoRA router as a research checkpoint until parameter MAE improves.",
        "Expand movement data with randomized targets including player-camera, object affordances, and spatial references.",
        "Train skill-specific low-level heads rather than forcing one shared head to solve all regimes.",
        "Use Newton/Warp or another GPU physics path to multiply rollout throughput and discover sim failures earlier.",
        "Keep every claim backed by eval JSON plus rendered proof video, then reflect that evidence on the page.",
        "Move beyond the virtual pet level with randomized object physics, multi-room tasks, language-conditioned reward models, longer action chunks, tactile/contact labels, and a fully Newton-native training/eval lane.",
        "Distill the router into smaller on-device policies once the skill interface stabilizes, while keeping MiniCPM-V as a sparse visual planner for hard perception moments.",
        "Add long-lived memory and habit formation so Fire Boy can develop preferences, routines, and a recognizable personality over repeated sessions.",
        "Revisit the original multi-agent toy idea: several virtual pets interacting with each other, the user, and shared objects in ways that can be observed but not fully scripted.",
        "Use the same virtual-pet control stack as a preparation ground for future humanoid robots: perception, state, safety bounds, action tokens, low-level controllers, and recovery policies transfer conceptually even when hardware changes.",
    ], body))
    story.append(Spacer(1, 0.08 * inch))
    story.append(p("References", styles["Section"]))
    story.append(table([
        ["Reference", "Why it matters here"],
        ["OpenBMB MiniCPM-V 4.6 model card, https://huggingface.co/openbmb/MiniCPM-V-4.6", "Backbone used for the frozen vision-language encoder and LoRA experiments."],
        ["Kirillov et al., Segment Anything, arXiv:2304.02643, https://arxiv.org/abs/2304.02643", "Segmentation/asset extraction inspiration for the SAM-based character workflow."],
        ["MuJoCo documentation, https://mujoco.readthedocs.io and https://mujoco.org", "Physics simulator used for articulated body, rollouts, and policy proof."],
        ["NVIDIA Newton Physics Engine, https://developer.nvidia.com/newton-physics and https://newton-physics.github.io/newton/stable/", "Future GPU physics lane built around Warp/OpenUSD and MuJoCo Warp integration."],
        ["Modal docs, https://modal.com/docs", "Serverless GPU/runtime infrastructure used by the MiniCPM-o gateway."],
        ["OpenAI Codex, https://openai.com/codex/", "Agentic coding environment used to scaffold, debug, document, and package the experiment."],
    ], [3.25 * inch, 3.65 * inch]))
    story.append(Spacer(1, 0.08 * inch))
    story.append(p("Appendix: key artifact paths include Fireboy-training-policy-vla/minicpm-vla-action-head-scaffold.md, Fireboy-training-policy-vla/overnight-goal-runpod-newton-kimodo-vla-plan.md, Fireboy-training-policy-vla/runpod-results-2026-06-15.md, fireboy-vla-physics/src/vla_router_runtime.py, src/vla_router_policy.py, and fireboy-vla-physics/build/fireboy-policy-proof-bundle/summary.json.", small))

    doc.build(story, onFirstPage=add_footer, onLaterPages=add_footer)
    FRONTEND_RESEARCH.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(PDF_PATH, FRONTEND_PDF_PATH)


def write_evidence_json(evidence: dict[str, Any], charts: dict[str, Path]) -> None:
    payload = {
        "pdf": f"/frontend/research/{PDF_NAME}",
        "charts": {name: f"/frontend/research/{path.name}" for name, path in charts.items()},
        "router": {
            "frozen_eval": evidence["frozen_eval"]["metrics"],
            "lora_eval": evidence["lora_eval"]["metrics"],
            "frozen_rows": evidence["frozen_train"]["rows"],
            "lora_rows": evidence["lora_train"]["rows"],
        },
        "param_counts": evidence["param_counts"],
        "skill_manifest": evidence["skill_manifest"],
        "proof_validation": evidence["proof_summary"]["validation"],
    }
    (FRONTEND_RESEARCH / "vla-evidence.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> None:
    evidence = load_evidence()
    charts = build_charts(evidence)
    build_pdf(evidence, charts)
    write_evidence_json(evidence, charts)
    print(json.dumps({
        "pdf": str(PDF_PATH),
        "frontend_pdf": str(FRONTEND_PDF_PATH),
        "charts": {key: str(value) for key, value in charts.items()},
    }, indent=2))


if __name__ == "__main__":
    main()
