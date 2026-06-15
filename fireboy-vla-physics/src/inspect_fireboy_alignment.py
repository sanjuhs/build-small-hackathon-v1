from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from fireboy_articulated_mjcf import DEFAULT_XML_PATH, write_default_mjcf
from render_articulated_fireboy import ArticulatedFireboyDemo


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_GLB = ROOT / "fire-boy-rig" / "fire-boy-rigged-full.glb"
DEFAULT_OUT_DIR = ROOT / "fireboy-vla-physics" / "build" / "inspection"


GLB_BONES = {
    "pelvis": "Hips",
    "spine": "Spine",
    "chest": "Chest",
    "neck": "Neck",
    "head": "Head",
    "crown": "Crown",
    "shoulder_R": "UpperArm.R",
    "elbow_R": "LowerArm.R",
    "wrist_R": "Hand.R",
    "hand_R": "Hand.R",
    "shoulder_L": "UpperArm.L",
    "elbow_L": "LowerArm.L",
    "wrist_L": "Hand.L",
    "hand_L": "Hand.L",
    "hip_R": "UpperLeg.R",
    "knee_R": "LowerLeg.R",
    "ankle_R": "Foot.R",
    "foot_R": "Foot.R",
    "hip_L": "UpperLeg.L",
    "knee_L": "LowerLeg.L",
    "ankle_L": "Foot.L",
    "foot_L": "Foot.L",
}


MJ_NAMES = [
    "pelvis",
    "spine",
    "chest",
    "neck",
    "head",
    "crown",
    "shoulder_R",
    "elbow_R",
    "wrist_R",
    "hand_R",
    "shoulder_L",
    "elbow_L",
    "wrist_L",
    "hand_L",
    "hip_R",
    "knee_R",
    "ankle_R",
    "foot_R",
    "hip_L",
    "knee_L",
    "ankle_L",
    "foot_L",
    "mouth",
    "berry",
]


EDGES = [
    ("pelvis", "spine"),
    ("spine", "chest"),
    ("chest", "neck"),
    ("neck", "head"),
    ("head", "crown"),
    ("chest", "shoulder_R"),
    ("shoulder_R", "elbow_R"),
    ("elbow_R", "wrist_R"),
    ("wrist_R", "hand_R"),
    ("chest", "shoulder_L"),
    ("shoulder_L", "elbow_L"),
    ("elbow_L", "wrist_L"),
    ("wrist_L", "hand_L"),
    ("pelvis", "hip_R"),
    ("hip_R", "knee_R"),
    ("knee_R", "ankle_R"),
    ("ankle_R", "foot_R"),
    ("pelvis", "hip_L"),
    ("hip_L", "knee_L"),
    ("knee_L", "ankle_L"),
    ("ankle_L", "foot_L"),
]


@dataclass
class Skeleton:
    name: str
    points: dict[str, np.ndarray]

    def normalized(self, target_height: float = 1.0) -> "Skeleton":
        pts = {key: value.copy() for key, value in self.points.items()}
        zs = np.array([value[2] for value in pts.values()], dtype=np.float64)
        height = float(max(zs.max() - zs.min(), 1e-6))
        root = pts.get("pelvis", np.array([0.0, 0.0, zs.min()], dtype=np.float64)).copy()
        scale = target_height / height
        norm = {key: (value - root) * scale for key, value in pts.items()}
        return Skeleton(self.name, norm)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--glb", type=Path, default=DEFAULT_GLB)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--blender", type=str, default="blender")
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    glb_raw = extract_glb_skeleton(args.blender, args.glb)
    mj_raw = extract_mujoco_skeleton()

    glb = glb_raw.normalized()
    mj = mj_raw.normalized()
    overlay = args.out_dir / "fireboy_skeleton_overlay.png"
    draw_overlay(glb, mj, overlay)

    report = build_report(glb_raw, mj_raw, glb, mj, overlay)
    report_path = args.out_dir / "fireboy_skeleton_alignment.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"overlay": str(overlay), "report": str(report_path), **report["summary"]}, indent=2))


def extract_glb_skeleton(blender: str, glb_path: Path) -> Skeleton:
    blender_code = r'''
import bpy
import json
import sys
from pathlib import Path

glb_path = Path(sys.argv[-2])
out_path = Path(sys.argv[-1])
bpy.ops.import_scene.gltf(filepath=str(glb_path))
armatures = [obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"]
if not armatures:
    raise SystemExit("No armature found in GLB")
arm = armatures[0]
mw = arm.matrix_world
payload = {"armature": arm.name, "bones": {}}
for bone in arm.data.bones:
    head = mw @ bone.head_local
    tail = mw @ bone.tail_local
    payload["bones"][bone.name] = {
        "parent": bone.parent.name if bone.parent else None,
        "head": [float(head.x), float(head.y), float(head.z)],
        "tail": [float(tail.x), float(tail.y), float(tail.z)],
        "length": float(bone.length),
    }
out_path.write_text(json.dumps(payload), encoding="utf-8")
'''
    with tempfile.TemporaryDirectory() as tmp:
        script_path = Path(tmp) / "extract_glb.py"
        out_path = Path(tmp) / "glb_skeleton.json"
        script_path.write_text(blender_code, encoding="utf-8")
        subprocess.run(
            [blender, "--background", "--factory-startup", "--python", str(script_path), "--", str(glb_path), str(out_path)],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        payload = json.loads(out_path.read_text(encoding="utf-8"))

    bones = payload["bones"]
    points: dict[str, np.ndarray] = {}
    for label, bone_name in GLB_BONES.items():
        bone = bones.get(bone_name)
        if not bone:
            continue
        if label in {"elbow_R", "wrist_R", "elbow_L", "wrist_L", "knee_R", "ankle_R", "knee_L", "ankle_L"}:
            points[label] = np.array(bone["head"], dtype=np.float64)
        elif label in {"hand_R", "hand_L", "foot_R", "foot_L", "crown"}:
            points[label] = np.array(bone["tail"], dtype=np.float64)
        else:
            points[label] = np.array(bone["head"], dtype=np.float64)

    return Skeleton("real GLB", canonicalize_glb_axes(points))


def canonicalize_glb_axes(points: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    # Blender GLB coordinates here use Z as vertical, but Fireboy's left/right
    # spread is on GLB X while the MuJoCo character uses Y. Map GLB right
    # (positive X) to MuJoCo right (negative Y) before overlaying.
    return {name: np.array([point[1], -point[0], point[2]], dtype=np.float64) for name, point in points.items()}


def extract_mujoco_skeleton() -> Skeleton:
    write_default_mjcf(DEFAULT_XML_PATH)
    demo = ArticulatedFireboyDemo(width=320, height=240, render_enabled=False)
    try:
        demo.reset()
        mujoco = demo.mujoco
        points: dict[str, np.ndarray] = {}
        for body_name, label in [
            ("spine", "spine"),
            ("chest", "chest"),
            ("neck", "neck"),
            ("head", "head"),
            ("upper_arm_R", "shoulder_R"),
            ("lower_arm_R", "elbow_R"),
            ("hand_R", "wrist_R"),
            ("upper_arm_L", "shoulder_L"),
            ("lower_arm_L", "elbow_L"),
            ("hand_L", "wrist_L"),
            ("upper_leg_R", "hip_R"),
            ("lower_leg_R", "knee_R"),
            ("foot_R", "ankle_R"),
            ("upper_leg_L", "hip_L"),
            ("lower_leg_L", "knee_L"),
            ("foot_L", "ankle_L"),
            ("berry", "berry"),
        ]:
            bid = mujoco.mj_name2id(demo.model, mujoco.mjtObj.mjOBJ_BODY, body_name)
            points[label] = np.asarray(demo.data.xpos[bid], dtype=np.float64).copy()
        points["pelvis"] = geom_center(demo, "hip_glow")
        points["hand_R"] = demo.site_pos("right_hand")
        points["hand_L"] = demo.site_pos("left_hand")
        points["mouth"] = demo.site_pos("mouth")
        points["crown"] = geom_center(demo, "flame_tip")
        points["foot_R"] = geom_center(demo, "foot_R_geom")
        points["foot_L"] = geom_center(demo, "foot_L_geom")
        return Skeleton("MuJoCo", points)
    finally:
        demo.close()


def geom_center(demo: ArticulatedFireboyDemo, geom_name: str) -> np.ndarray:
    gid = demo.mujoco.mj_name2id(demo.model, demo.mujoco.mjtObj.mjOBJ_GEOM, geom_name)
    return np.asarray(demo.data.geom_xpos[gid], dtype=np.float64).copy()


def build_report(glb_raw: Skeleton, mj_raw: Skeleton, glb: Skeleton, mj: Skeleton, overlay: Path) -> dict[str, Any]:
    common = sorted(set(glb.points) & set(mj.points))
    distances = {name: round(float(np.linalg.norm(glb.points[name] - mj.points[name])), 4) for name in common}
    limb_lengths = {
        "glb": limb_lengths_for(glb),
        "mujoco": limb_lengths_for(mj),
    }
    elbow_delta = {
        side: round(float(np.linalg.norm(glb.points[f"elbow_{side}"] - mj.points[f"elbow_{side}"])), 4)
        for side in ["R", "L"]
        if f"elbow_{side}" in glb.points and f"elbow_{side}" in mj.points
    }
    return {
        "summary": {
            "overlay": str(overlay),
            "common_points": len(common),
            "max_normalized_point_error": round(max(distances.values()) if distances else 0.0, 4),
            "right_elbow_normalized_error": elbow_delta.get("R"),
            "left_elbow_normalized_error": elbow_delta.get("L"),
            "right_arm_length_ratio_mj_over_glb": safe_ratio(
                limb_lengths["mujoco"].get("right_arm_total"),
                limb_lengths["glb"].get("right_arm_total"),
            ),
            "left_arm_length_ratio_mj_over_glb": safe_ratio(
                limb_lengths["mujoco"].get("left_arm_total"),
                limb_lengths["glb"].get("left_arm_total"),
            ),
        },
        "limb_lengths_normalized": limb_lengths,
        "point_distances_normalized": distances,
        "raw_points": {
            "glb": serialize_points(glb_raw.points),
            "mujoco": serialize_points(mj_raw.points),
        },
        "normalized_points": {
            "glb": serialize_points(glb.points),
            "mujoco": serialize_points(mj.points),
        },
    }


def limb_lengths_for(skel: Skeleton) -> dict[str, float]:
    pairs = {
        "right_upper_arm": ("shoulder_R", "elbow_R"),
        "right_lower_arm": ("elbow_R", "wrist_R"),
        "right_hand": ("wrist_R", "hand_R"),
        "left_upper_arm": ("shoulder_L", "elbow_L"),
        "left_lower_arm": ("elbow_L", "wrist_L"),
        "left_hand": ("wrist_L", "hand_L"),
        "right_upper_leg": ("hip_R", "knee_R"),
        "right_lower_leg": ("knee_R", "ankle_R"),
        "right_foot": ("ankle_R", "foot_R"),
        "left_upper_leg": ("hip_L", "knee_L"),
        "left_lower_leg": ("knee_L", "ankle_L"),
        "left_foot": ("ankle_L", "foot_L"),
    }
    out = {
        name: round(distance(skel.points, a, b), 4)
        for name, (a, b) in pairs.items()
        if a in skel.points and b in skel.points
    }
    if {"right_upper_arm", "right_lower_arm", "right_hand"} <= set(out):
        out["right_arm_total"] = round(out["right_upper_arm"] + out["right_lower_arm"] + out["right_hand"], 4)
    if {"left_upper_arm", "left_lower_arm", "left_hand"} <= set(out):
        out["left_arm_total"] = round(out["left_upper_arm"] + out["left_lower_arm"] + out["left_hand"], 4)
    return out


def distance(points: dict[str, np.ndarray], a: str, b: str) -> float:
    return float(np.linalg.norm(points[a] - points[b]))


def safe_ratio(a: float | None, b: float | None) -> float | None:
    if a is None or b is None or abs(b) < 1e-9:
        return None
    return round(float(a / b), 4)


def serialize_points(points: dict[str, np.ndarray]) -> dict[str, list[float]]:
    return {name: [round(float(v), 5) for v in point] for name, point in sorted(points.items())}


def draw_overlay(glb: Skeleton, mj: Skeleton, path: Path) -> None:
    image = Image.new("RGB", (1200, 900), (250, 248, 242))
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    origin = np.array([600.0, 720.0])
    scale = 530.0

    def project(point: np.ndarray) -> tuple[float, float]:
        # Front view: horizontal body width is Y, vertical is Z.
        return float(origin[0] + point[1] * scale), float(origin[1] - point[2] * scale)

    draw.text((40, 34), "Fireboy skeleton overlay: real GLB rig (blue) vs current MuJoCo body (red)", fill=(20, 20, 20), font=font)
    draw.text((40, 58), "Front projection after pelvis alignment and height normalization. Elbow/wrist errors are geometric, not rendering perspective.", fill=(70, 70, 70), font=font)
    draw.line((60, 805, 1140, 805), fill=(210, 204, 190), width=2)

    draw_skeleton(draw, glb, project, edge_fill=(47, 96, 210), point_fill=(31, 72, 180), width=7, radius=7)
    draw_skeleton(draw, mj, project, edge_fill=(218, 70, 50), point_fill=(185, 42, 28), width=4, radius=5)

    for label in ["shoulder_R", "elbow_R", "wrist_R", "hand_R", "shoulder_L", "elbow_L", "wrist_L", "hand_L", "mouth", "berry"]:
        if label in mj.points:
            x, y = project(mj.points[label])
            draw.text((x + 8, y - 8), label, fill=(120, 35, 28), font=font)

    legend_x, legend_y = 840, 42
    draw.line((legend_x, legend_y, legend_x + 42, legend_y), fill=(47, 96, 210), width=7)
    draw.text((legend_x + 54, legend_y - 7), "real GLB rig", fill=(31, 72, 180), font=font)
    draw.line((legend_x, legend_y + 30, legend_x + 42, legend_y + 30), fill=(218, 70, 50), width=5)
    draw.text((legend_x + 54, legend_y + 23), "current MuJoCo body", fill=(185, 42, 28), font=font)

    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def draw_skeleton(
    draw: ImageDraw.ImageDraw,
    skel: Skeleton,
    project: Any,
    edge_fill: tuple[int, int, int],
    point_fill: tuple[int, int, int],
    width: int,
    radius: int,
) -> None:
    for a, b in EDGES:
        if a in skel.points and b in skel.points:
            draw.line((*project(skel.points[a]), *project(skel.points[b])), fill=edge_fill, width=width)
    for name in MJ_NAMES:
        if name in skel.points:
            x, y = project(skel.points[name])
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=point_fill, outline=(255, 255, 255), width=1)


if __name__ == "__main__":
    main()
