"""Stage B: author animation clips on each base-body rig and export GLBs.

Run from the project root (after build_rig.py):

    blender --background --python fire-boy-rig/working/animate_and_export.py

Outputs (per character):
    fire-boy-rig/<slug>-rigged-full.glb          (mesh + rig + 6 clips)
    fire-boy-rig/working/<slug>-rig-animated.blend
    fire-boy-rig/previews/<slug>-clip-*.png      (check frames per clip)
"""

from __future__ import annotations

import math
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "fire-boy-rig"
WORK_DIR = OUT_DIR / "working"
PREVIEW_DIR = OUT_DIR / "previews"

FPS = 24
SLUGS = ("squeaky", "electraica", "fire-boy", "shark-girl")


def ident(slug: str) -> str:
    return slug.replace("-", "_")


def world_rot_euler(pbone, rx: float, ry: float, rz: float):
    """Convert a world-space rotation (degrees, applied Z@Y@X) to bone-local euler."""
    rot = (
        Matrix.Rotation(math.radians(rz), 4, "Z")
        @ Matrix.Rotation(math.radians(ry), 4, "Y")
        @ Matrix.Rotation(math.radians(rx), 4, "X")
    )
    rest = pbone.bone.matrix_local.to_3x3().to_4x4()
    return (rest.inverted() @ rot @ rest).to_euler("XYZ")


def world_loc(pbone, dx: float, dy: float, dz: float) -> Vector:
    rest3 = pbone.bone.matrix_local.to_3x3()
    return rest3.inverted() @ Vector((dx, dy, dz))


def key_channel(arm, frame: int, bone: str, rot=None, loc=None, scale=None) -> None:
    pbone = arm.pose.bones.get(bone)
    if pbone is None:
        return
    if rot is not None:
        pbone.rotation_euler = world_rot_euler(pbone, *rot)
        pbone.keyframe_insert("rotation_euler", frame=frame)
    if loc is not None:
        pbone.location = world_loc(pbone, *loc)
        pbone.keyframe_insert("location", frame=frame)
    if scale is not None:
        pbone.scale = Vector(scale)
        pbone.keyframe_insert("scale", frame=frame)


def reset_pose(arm) -> None:
    for pbone in arm.pose.bones:
        pbone.location = (0, 0, 0)
        pbone.rotation_euler = (0, 0, 0)
        pbone.scale = (1, 1, 1)


def new_action(arm, name: str):
    act = bpy.data.actions.new(name)
    ad = arm.animation_data_create()
    ad.action = act
    if hasattr(act, "slots") and hasattr(ad, "action_slot"):
        slot = act.slots.new(id_type="OBJECT", name=arm.name)
        ad.action_slot = slot
    return act


def author_clip(arm, name: str, frames: int, keys: dict[str, list[tuple]]) -> tuple:
    """keys: bone -> [(frame, kind, value)] with kind in rot/loc/scale."""
    reset_pose(arm)
    act = new_action(arm, name)
    for bone, channel in keys.items():
        for frame, kind, value in channel:
            key_channel(arm, frame, bone, **{kind: value})
    act.use_frame_range = True
    act.frame_start = 1
    act.frame_end = frames
    return act, frames


def clip_idle(arm):
    n = 48
    keys = {
        "Root": [(1, "loc", (0, 0, 0)), (25, "loc", (0, 0, -0.012)), (n, "loc", (0, 0, 0))],
        "Chest": [(1, "rot", (0, 0, 0)), (25, "rot", (3.0, 0, 0)), (n, "rot", (0, 0, 0))],
        "Head": [
            (1, "rot", (0, 0, 0)),
            (13, "rot", (1.5, 0, 3.0)),
            (25, "rot", (2.5, 0, 0)),
            (37, "rot", (1.5, 0, -3.0)),
            (n, "rot", (0, 0, 0)),
        ],
        "Crown": [
            (1, "rot", (0, 0, 0)),
            (7, "rot", (5.0, 4.0, 0)),
            (13, "rot", (0, -5.0, 0)),
            (19, "rot", (-5.0, 3.0, 0)),
            (25, "rot", (0, 0, 0)),
            (31, "rot", (5.0, -4.0, 0)),
            (37, "rot", (0, 5.0, 0)),
            (43, "rot", (-5.0, -3.0, 0)),
            (n, "rot", (0, 0, 0)),
        ],
        "UpperArm.L": [(1, "rot", (0, 0, 0)), (25, "rot", (4.0, 0, 2.0)), (n, "rot", (0, 0, 0))],
        "UpperArm.R": [(1, "rot", (0, 0, 0)), (25, "rot", (4.0, 0, -2.0)), (n, "rot", (0, 0, 0))],
    }
    return author_clip(arm, "Idle", n, keys)


def clip_walk(arm):
    n = 32
    swing, knee, armswing = 30.0, 16.0, 18.0
    keys = {
        "UpperLeg.L": [
            (1, "rot", (-swing, 0, 0)),
            (9, "rot", (0, 0, 0)),
            (17, "rot", (swing, 0, 0)),
            (25, "rot", (0, 0, 0)),
            (n, "rot", (-swing, 0, 0)),
        ],
        "UpperLeg.R": [
            (1, "rot", (swing, 0, 0)),
            (9, "rot", (0, 0, 0)),
            (17, "rot", (-swing, 0, 0)),
            (25, "rot", (0, 0, 0)),
            (n, "rot", (swing, 0, 0)),
        ],
        "LowerLeg.L": [
            (1, "rot", (knee, 0, 0)),
            (9, "rot", (2 * knee, 0, 0)),
            (17, "rot", (0, 0, 0)),
            (n, "rot", (knee, 0, 0)),
        ],
        "LowerLeg.R": [
            (1, "rot", (0, 0, 0)),
            (17, "rot", (knee, 0, 0)),
            (25, "rot", (2 * knee, 0, 0)),
            (n, "rot", (0, 0, 0)),
        ],
        "UpperArm.L": [(1, "rot", (armswing, 0, 0)), (17, "rot", (-armswing, 0, 0)), (n, "rot", (armswing, 0, 0))],
        "UpperArm.R": [(1, "rot", (-armswing, 0, 0)), (17, "rot", (armswing, 0, 0)), (n, "rot", (-armswing, 0, 0))],
        "Root": [
            (1, "loc", (0, 0, -0.014)),
            (9, "loc", (0, 0, 0.012)),
            (17, "loc", (0, 0, -0.014)),
            (25, "loc", (0, 0, 0.012)),
            (n, "loc", (0, 0, -0.014)),
        ],
        "Hips": [(1, "rot", (0, 0, 7.0)), (17, "rot", (0, 0, -7.0)), (n, "rot", (0, 0, 7.0))],
        "Chest": [(1, "rot", (4.0, 0, -4.0)), (17, "rot", (4.0, 0, 4.0)), (n, "rot", (4.0, 0, -4.0))],
        "Head": [
            (1, "rot", (-2.0, 0, 0)),
            (9, "rot", (1.5, 0, 0)),
            (17, "rot", (-2.0, 0, 0)),
            (25, "rot", (1.5, 0, 0)),
            (n, "rot", (-2.0, 0, 0)),
        ],
        "Crown": [(1, "rot", (6.0, 0, 0)), (17, "rot", (-6.0, 0, 0)), (n, "rot", (6.0, 0, 0))],
    }
    return author_clip(arm, "Walk", n, keys)


def clip_run(arm):
    n = 20
    swing, knee, armswing = 46.0, 26.0, 36.0
    keys = {
        "UpperLeg.L": [(1, "rot", (-swing, 0, 0)), (11, "rot", (swing, 0, 0)), (n, "rot", (-swing, 0, 0))],
        "UpperLeg.R": [(1, "rot", (swing, 0, 0)), (11, "rot", (-swing, 0, 0)), (n, "rot", (swing, 0, 0))],
        "LowerLeg.L": [
            (1, "rot", (knee, 0, 0)),
            (6, "rot", (2.2 * knee, 0, 0)),
            (11, "rot", (4.0, 0, 0)),
            (n, "rot", (knee, 0, 0)),
        ],
        "LowerLeg.R": [
            (1, "rot", (4.0, 0, 0)),
            (11, "rot", (knee, 0, 0)),
            (16, "rot", (2.2 * knee, 0, 0)),
            (n, "rot", (4.0, 0, 0)),
        ],
        "UpperArm.L": [(1, "rot", (armswing, 0, 0)), (11, "rot", (-armswing, 0, 0)), (n, "rot", (armswing, 0, 0))],
        "UpperArm.R": [(1, "rot", (-armswing, 0, 0)), (11, "rot", (armswing, 0, 0)), (n, "rot", (-armswing, 0, 0))],
        "LowerArm.L": [(1, "rot", (-20.0, 0, 0)), (n, "rot", (-20.0, 0, 0))],
        "LowerArm.R": [(1, "rot", (-20.0, 0, 0)), (n, "rot", (-20.0, 0, 0))],
        "Root": [
            (1, "loc", (0, 0, -0.03)),
            (6, "loc", (0, 0, 0.035)),
            (11, "loc", (0, 0, -0.03)),
            (16, "loc", (0, 0, 0.035)),
            (n, "loc", (0, 0, -0.03)),
        ],
        "Spine": [(1, "rot", (10.0, 0, 0)), (n, "rot", (10.0, 0, 0))],
        "Hips": [(1, "rot", (0, 0, 9.0)), (11, "rot", (0, 0, -9.0)), (n, "rot", (0, 0, 9.0))],
        "Head": [(1, "rot", (-5.0, 0, 0)), (n, "rot", (-5.0, 0, 0))],
        "Crown": [
            (1, "rot", (12.0, 0, 0)),
            (6, "rot", (2.0, 5.0, 0)),
            (11, "rot", (12.0, -5.0, 0)),
            (16, "rot", (2.0, 0, 0)),
            (n, "rot", (12.0, 0, 0)),
        ],
    }
    return author_clip(arm, "Run", n, keys)


def clip_jump(arm):
    n = 48
    keys = {
        "Root": [
            (1, "loc", (0, 0, 0)),
            (10, "loc", (0, 0, -0.10)),
            (16, "loc", (0, 0, 0.18)),
            (23, "loc", (0, 0, 0.26)),
            (30, "loc", (0, 0, 0.0)),
            (34, "loc", (0, 0, -0.07)),
            (42, "loc", (0, 0, 0)),
            (n, "loc", (0, 0, 0)),
        ],
        "Hips": [
            (1, "scale", (1, 1, 1)),
            (10, "scale", (1.06, 1.06, 0.9)),
            (16, "scale", (0.96, 0.96, 1.08)),
            (23, "scale", (1, 1, 1)),
            (34, "scale", (1.06, 1.06, 0.92)),
            (42, "scale", (1, 1, 1)),
        ],
        "UpperLeg.L": [
            (1, "rot", (0, 0, 0)),
            (10, "rot", (-32.0, 0, 0)),
            (16, "rot", (10.0, 0, 0)),
            (23, "rot", (-38.0, 0, 6.0)),
            (30, "rot", (-8.0, 0, 0)),
            (34, "rot", (-28.0, 0, 0)),
            (42, "rot", (0, 0, 0)),
        ],
        "UpperLeg.R": [
            (1, "rot", (0, 0, 0)),
            (10, "rot", (-32.0, 0, 0)),
            (16, "rot", (10.0, 0, 0)),
            (23, "rot", (-38.0, 0, -6.0)),
            (30, "rot", (-8.0, 0, 0)),
            (34, "rot", (-28.0, 0, 0)),
            (42, "rot", (0, 0, 0)),
        ],
        "LowerLeg.L": [
            (1, "rot", (0, 0, 0)),
            (10, "rot", (45.0, 0, 0)),
            (16, "rot", (-6.0, 0, 0)),
            (23, "rot", (50.0, 0, 0)),
            (34, "rot", (38.0, 0, 0)),
            (42, "rot", (0, 0, 0)),
        ],
        "LowerLeg.R": [
            (1, "rot", (0, 0, 0)),
            (10, "rot", (45.0, 0, 0)),
            (16, "rot", (-6.0, 0, 0)),
            (23, "rot", (50.0, 0, 0)),
            (34, "rot", (38.0, 0, 0)),
            (42, "rot", (0, 0, 0)),
        ],
        "UpperArm.L": [
            (1, "rot", (0, 0, 0)),
            (10, "rot", (35.0, 0, 0)),
            (16, "rot", (-72.0, 20.0, 0)),
            (23, "rot", (-58.0, 30.0, 0)),
            (30, "rot", (15.0, 0, 0)),
            (42, "rot", (0, 0, 0)),
        ],
        "UpperArm.R": [
            (1, "rot", (0, 0, 0)),
            (10, "rot", (35.0, 0, 0)),
            (16, "rot", (-72.0, -20.0, 0)),
            (23, "rot", (-58.0, -30.0, 0)),
            (30, "rot", (15.0, 0, 0)),
            (42, "rot", (0, 0, 0)),
        ],
        "Spine": [
            (1, "rot", (0, 0, 0)),
            (10, "rot", (16.0, 0, 0)),
            (16, "rot", (-8.0, 0, 0)),
            (23, "rot", (-4.0, 0, 0)),
            (34, "rot", (12.0, 0, 0)),
            (42, "rot", (0, 0, 0)),
        ],
        "Head": [
            (1, "rot", (0, 0, 0)),
            (10, "rot", (10.0, 0, 0)),
            (16, "rot", (-10.0, 0, 0)),
            (23, "rot", (-6.0, 0, 0)),
            (34, "rot", (8.0, 0, 0)),
            (42, "rot", (0, 0, 0)),
        ],
        "Crown": [
            (1, "rot", (0, 0, 0)),
            (10, "rot", (14.0, 0, 0)),
            (16, "rot", (-16.0, 0, 0)),
            (23, "rot", (-10.0, 0, 0)),
            (30, "rot", (12.0, 0, 0)),
            (42, "rot", (0, 0, 0)),
        ],
    }
    return author_clip(arm, "Jump", n, keys)


def clip_wave(arm):
    n = 48
    lift = (-50.0, -65.0, 0)
    keys = {
        "UpperArm.R": [
            (1, "rot", (0, 0, 0)),
            (8, "rot", lift),
            (40, "rot", lift),
            (n, "rot", (0, 0, 0)),
        ],
        "LowerArm.R": [
            (1, "rot", (0, 0, 0)),
            (8, "rot", (0, -20.0, 0)),
            (13, "rot", (0, -20.0, 22.0)),
            (19, "rot", (0, -20.0, -22.0)),
            (25, "rot", (0, -20.0, 22.0)),
            (31, "rot", (0, -20.0, -22.0)),
            (40, "rot", (0, -20.0, 0)),
            (n, "rot", (0, 0, 0)),
        ],
        "Hand.R": [
            (1, "rot", (0, 0, 0)),
            (13, "rot", (0, 0, 16.0)),
            (19, "rot", (0, 0, -16.0)),
            (25, "rot", (0, 0, 16.0)),
            (31, "rot", (0, 0, -16.0)),
            (n, "rot", (0, 0, 0)),
        ],
        "Head": [
            (1, "rot", (0, 0, 0)),
            (12, "rot", (0, -6.0, 4.0)),
            (36, "rot", (0, -6.0, 4.0)),
            (n, "rot", (0, 0, 0)),
        ],
        "Chest": [(1, "rot", (0, 0, 0)), (12, "rot", (0, -4.0, 0)), (36, "rot", (0, -4.0, 0)), (n, "rot", (0, 0, 0))],
        "UpperArm.L": [(1, "rot", (0, 0, 0)), (25, "rot", (4.0, 0, 3.0)), (n, "rot", (0, 0, 0))],
        "Crown": [
            (1, "rot", (0, 0, 0)),
            (13, "rot", (4.0, 6.0, 0)),
            (25, "rot", (-4.0, -6.0, 0)),
            (37, "rot", (4.0, 6.0, 0)),
            (n, "rot", (0, 0, 0)),
        ],
    }
    return author_clip(arm, "Wave", n, keys)


def clip_cheer(arm):
    n = 40
    up_l = (-100.0, 20.0, 0)
    up_r = (-100.0, -20.0, 0)
    keys = {
        "UpperArm.L": [
            (1, "rot", (0, 0, 0)),
            (8, "rot", up_l),
            (14, "rot", (-85.0, 16.0, 0)),
            (20, "rot", up_l),
            (26, "rot", (-85.0, 16.0, 0)),
            (32, "rot", up_l),
            (n, "rot", (0, 0, 0)),
        ],
        "UpperArm.R": [
            (1, "rot", (0, 0, 0)),
            (8, "rot", up_r),
            (14, "rot", (-85.0, -16.0, 0)),
            (20, "rot", up_r),
            (26, "rot", (-85.0, -16.0, 0)),
            (32, "rot", up_r),
            (n, "rot", (0, 0, 0)),
        ],
        "Root": [
            (1, "loc", (0, 0, 0)),
            (8, "loc", (0, 0, -0.03)),
            (14, "loc", (0, 0, 0.05)),
            (20, "loc", (0, 0, -0.03)),
            (26, "loc", (0, 0, 0.05)),
            (32, "loc", (0, 0, -0.02)),
            (n, "loc", (0, 0, 0)),
        ],
        "Head": [
            (1, "rot", (0, 0, 0)),
            (14, "rot", (-8.0, 0, 5.0)),
            (26, "rot", (-8.0, 0, -5.0)),
            (n, "rot", (0, 0, 0)),
        ],
        "Spine": [(1, "rot", (0, 0, 0)), (14, "rot", (-6.0, 0, 0)), (26, "rot", (-6.0, 0, 0)), (n, "rot", (0, 0, 0))],
        "Crown": [
            (1, "rot", (0, 0, 0)),
            (8, "rot", (10.0, 8.0, 0)),
            (14, "rot", (-12.0, -8.0, 0)),
            (20, "rot", (10.0, 8.0, 0)),
            (26, "rot", (-12.0, -8.0, 0)),
            (n, "rot", (0, 0, 0)),
        ],
    }
    return author_clip(arm, "Cheer", n, keys)


def clip_dance(arm):
    n = 48
    keys = {
        "Hips": [
            (1, "rot", (0, -10.0, 0)),
            (13, "rot", (0, 10.0, 0)),
            (25, "rot", (0, -10.0, 0)),
            (37, "rot", (0, 10.0, 0)),
            (n, "rot", (0, -10.0, 0)),
        ],
        "Chest": [
            (1, "rot", (0, 6.0, 0)),
            (13, "rot", (0, -6.0, 0)),
            (25, "rot", (0, 6.0, 0)),
            (37, "rot", (0, -6.0, 0)),
            (n, "rot", (0, 6.0, 0)),
        ],
        "Root": [
            (1, "loc", (0, 0, -0.02)),
            (7, "loc", (0, 0, 0.015)),
            (13, "loc", (0, 0, -0.02)),
            (19, "loc", (0, 0, 0.015)),
            (25, "loc", (0, 0, -0.02)),
            (31, "loc", (0, 0, 0.015)),
            (37, "loc", (0, 0, -0.02)),
            (43, "loc", (0, 0, 0.015)),
            (n, "loc", (0, 0, -0.02)),
        ],
        "UpperArm.L": [
            (1, "rot", (-70.0, 25.0, 0)),
            (13, "rot", (20.0, 0, 0)),
            (25, "rot", (-70.0, 25.0, 0)),
            (37, "rot", (20.0, 0, 0)),
            (n, "rot", (-70.0, 25.0, 0)),
        ],
        "UpperArm.R": [
            (1, "rot", (20.0, 0, 0)),
            (13, "rot", (-70.0, -25.0, 0)),
            (25, "rot", (20.0, 0, 0)),
            (37, "rot", (-70.0, -25.0, 0)),
            (n, "rot", (20.0, 0, 0)),
        ],
        "Head": [
            (1, "rot", (3.0, 0, -6.0)),
            (13, "rot", (-3.0, 0, 6.0)),
            (25, "rot", (3.0, 0, -6.0)),
            (37, "rot", (-3.0, 0, 6.0)),
            (n, "rot", (3.0, 0, -6.0)),
        ],
        "Crown": [
            (1, "rot", (0, 8.0, 0)),
            (13, "rot", (0, -8.0, 0)),
            (25, "rot", (0, 8.0, 0)),
            (37, "rot", (0, -8.0, 0)),
            (n, "rot", (0, 8.0, 0)),
        ],
    }
    return author_clip(arm, "Dance", n, keys)


def clip_spin(arm):
    n = 32
    keys = {
        "Root": [
            (1, "rot", (0, 0, 0)),
            (11, "rot", (0, 0, 120.0)),
            (21, "rot", (0, 0, 240.0)),
            (n, "rot", (0, 0, 360.0)),
        ],
        "UpperArm.L": [
            (1, "rot", (0, 0, 0)),
            (8, "rot", (-45.0, 30.0, 0)),
            (24, "rot", (-45.0, 30.0, 0)),
            (n, "rot", (0, 0, 0)),
        ],
        "UpperArm.R": [
            (1, "rot", (0, 0, 0)),
            (8, "rot", (-45.0, -30.0, 0)),
            (24, "rot", (-45.0, -30.0, 0)),
            (n, "rot", (0, 0, 0)),
        ],
        "Crown": [
            (1, "rot", (0, 0, 0)),
            (11, "rot", (-10.0, 0, 0)),
            (21, "rot", (-10.0, 0, 0)),
            (n, "rot", (0, 0, 0)),
        ],
        "Head": [(1, "rot", (0, 0, 0)), (16, "rot", (-4.0, 0, 0)), (n, "rot", (0, 0, 0))],
    }
    return author_clip(arm, "Spin", n, keys)


def clip_throw(arm):
    """Wind up and hurl with the right hand — doubles as a fireball cast."""
    n = 36
    keys = {
        "Chest": [
            (1, "rot", (0, 0, 0)),
            (9, "rot", (-6.0, 0, 22.0)),
            (15, "rot", (8.0, 0, -18.0)),
            (22, "rot", (4.0, 0, -10.0)),
            (n, "rot", (0, 0, 0)),
        ],
        "Spine": [
            (1, "rot", (0, 0, 0)),
            (9, "rot", (-6.0, 0, 8.0)),
            (15, "rot", (10.0, 0, -8.0)),
            (n, "rot", (0, 0, 0)),
        ],
        "UpperArm.R": [
            (1, "rot", (0, 0, 0)),
            (9, "rot", (45.0, -30.0, 0)),
            (15, "rot", (-95.0, -5.0, 0)),
            (22, "rot", (-60.0, 0, 0)),
            (n, "rot", (0, 0, 0)),
        ],
        "LowerArm.R": [
            (1, "rot", (0, 0, 0)),
            (9, "rot", (30.0, 0, 0)),
            (15, "rot", (-15.0, 0, 0)),
            (n, "rot", (0, 0, 0)),
        ],
        "Hand.R": [
            (1, "rot", (0, 0, 0)),
            (9, "rot", (15.0, 0, 0)),
            (15, "rot", (-20.0, 0, 0)),
            (n, "rot", (0, 0, 0)),
        ],
        "UpperArm.L": [
            (1, "rot", (0, 0, 0)),
            (9, "rot", (-25.0, 10.0, 0)),
            (15, "rot", (25.0, 0, 0)),
            (n, "rot", (0, 0, 0)),
        ],
        "UpperLeg.L": [
            (1, "rot", (0, 0, 0)),
            (9, "rot", (8.0, 0, 0)),
            (15, "rot", (-10.0, 0, 0)),
            (n, "rot", (0, 0, 0)),
        ],
        "UpperLeg.R": [
            (1, "rot", (0, 0, 0)),
            (9, "rot", (-8.0, 0, 0)),
            (15, "rot", (10.0, 0, 0)),
            (n, "rot", (0, 0, 0)),
        ],
        "Head": [
            (1, "rot", (0, 0, 0)),
            (9, "rot", (-4.0, 0, -12.0)),
            (15, "rot", (4.0, 0, 8.0)),
            (n, "rot", (0, 0, 0)),
        ],
        "Crown": [
            (1, "rot", (0, 0, 0)),
            (9, "rot", (8.0, 0, 0)),
            (15, "rot", (-14.0, 0, 0)),
            (22, "rot", (4.0, 0, 0)),
            (n, "rot", (0, 0, 0)),
        ],
    }
    return author_clip(arm, "Throw", n, keys)


def clip_sit(arm):
    """Sit down on the floor, settle, and stand back up."""
    n = 56
    seat = -0.15
    keys = {
        "Root": [
            (1, "loc", (0, 0, 0)),
            (10, "loc", (0, 0, -0.08)),
            (18, "loc", (0, 0, seat)),
            (38, "loc", (0, 0, seat)),
            (48, "loc", (0, 0, -0.06)),
            (n, "loc", (0, 0, 0)),
        ],
        "UpperLeg.L": [
            (1, "rot", (0, 0, 0)),
            (10, "rot", (-40.0, 0, 0)),
            (18, "rot", (-78.0, 0, 10.0)),
            (38, "rot", (-78.0, 0, 10.0)),
            (48, "rot", (-30.0, 0, 0)),
            (n, "rot", (0, 0, 0)),
        ],
        "UpperLeg.R": [
            (1, "rot", (0, 0, 0)),
            (10, "rot", (-40.0, 0, 0)),
            (18, "rot", (-78.0, 0, -10.0)),
            (38, "rot", (-78.0, 0, -10.0)),
            (48, "rot", (-30.0, 0, 0)),
            (n, "rot", (0, 0, 0)),
        ],
        "LowerLeg.L": [
            (1, "rot", (0, 0, 0)),
            (10, "rot", (35.0, 0, 0)),
            (18, "rot", (68.0, 0, 0)),
            (38, "rot", (68.0, 0, 0)),
            (48, "rot", (26.0, 0, 0)),
            (n, "rot", (0, 0, 0)),
        ],
        "LowerLeg.R": [
            (1, "rot", (0, 0, 0)),
            (10, "rot", (35.0, 0, 0)),
            (18, "rot", (68.0, 0, 0)),
            (38, "rot", (68.0, 0, 0)),
            (48, "rot", (26.0, 0, 0)),
            (n, "rot", (0, 0, 0)),
        ],
        "Spine": [
            (1, "rot", (0, 0, 0)),
            (10, "rot", (10.0, 0, 0)),
            (18, "rot", (4.0, 0, 0)),
            (38, "rot", (4.0, 0, 0)),
            (48, "rot", (12.0, 0, 0)),
            (n, "rot", (0, 0, 0)),
        ],
        "UpperArm.L": [
            (1, "rot", (0, 0, 0)),
            (18, "rot", (12.0, 8.0, 0)),
            (38, "rot", (12.0, 8.0, 0)),
            (n, "rot", (0, 0, 0)),
        ],
        "UpperArm.R": [
            (1, "rot", (0, 0, 0)),
            (18, "rot", (12.0, -8.0, 0)),
            (38, "rot", (12.0, -8.0, 0)),
            (n, "rot", (0, 0, 0)),
        ],
        "Head": [
            (1, "rot", (0, 0, 0)),
            (18, "rot", (3.0, 0, 0)),
            (26, "rot", (1.0, 0, 4.0)),
            (32, "rot", (3.0, 0, -4.0)),
            (38, "rot", (3.0, 0, 0)),
            (n, "rot", (0, 0, 0)),
        ],
        "Crown": [
            (1, "rot", (0, 0, 0)),
            (14, "rot", (10.0, 0, 0)),
            (20, "rot", (-6.0, 0, 0)),
            (38, "rot", (0, 4.0, 0)),
            (48, "rot", (8.0, 0, 0)),
            (n, "rot", (0, 0, 0)),
        ],
    }
    return author_clip(arm, "Sit", n, keys)


# ---------------------------------------------------------------- rendering


def material(name, color, roughness=0.86):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = color
        bsdf.inputs["Roughness"].default_value = roughness
    return mat


def look_at(obj, target) -> None:
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def setup_render_scene() -> None:
    world = bpy.context.scene.world or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.color = (1.0, 0.97, 0.90)
    bpy.context.scene.render.resolution_x = 800
    bpy.context.scene.render.resolution_y = 800
    try:
        bpy.context.scene.render.engine = "BLENDER_EEVEE_NEXT"
    except TypeError:
        bpy.context.scene.render.engine = "BLENDER_EEVEE"
    bpy.context.scene.eevee.taa_render_samples = 48

    bpy.ops.object.light_add(type="AREA", location=(0.0, -3.9, 4.6))
    bpy.context.object.data.energy = 760
    bpy.context.object.data.size = 5.2
    bpy.ops.object.light_add(type="AREA", location=(-2.9, -2.4, 2.7))
    bpy.context.object.data.energy = 250
    bpy.context.object.data.size = 3.2

    bpy.ops.object.camera_add(location=(-2.6, -3.6, 1.1))
    camera = bpy.context.object
    camera.data.lens = 60
    look_at(camera, (0, 0, 0.5))
    bpy.context.scene.camera = camera


def render_check_frames(slug: str, arm, clips: dict[str, tuple]) -> None:
    setup_render_scene()
    scene = bpy.context.scene
    check_frames = {
        "Idle": (25,),
        "Walk": (1, 9, 17),
        "Run": (1, 6),
        "Jump": (10, 16, 23),
        "Wave": (19,),
        "Cheer": (14,),
        "Dance": (13,),
        "Spin": (11,),
        "Throw": (15,),
        "Sit": (26,),
    }
    ad = arm.animation_data
    for name, (act, _length) in clips.items():
        ad.action = None
        reset_pose(arm)  # channels a clip doesn't key keep stale values otherwise
        ad.action = act
        if hasattr(act, "slots") and hasattr(ad, "action_slot"):
            ad.action_slot = act.slots[0]
        for frame in check_frames.get(name, (1,)):
            scene.frame_set(frame)
            scene.render.filepath = str(PREVIEW_DIR / f"{slug}-clip-{name.lower()}-f{frame:02d}.png")
            bpy.ops.render.render(write_still=True)
    ad.action = None


def push_nla(arm, clips: dict[str, tuple]) -> None:
    ad = arm.animation_data
    ad.action = None
    for name, (act, length) in clips.items():
        track = ad.nla_tracks.new()
        track.name = name
        strip = track.strips.new(name, 1, act)
        if hasattr(strip, "action_slot") and hasattr(act, "slots") and len(act.slots):
            try:
                strip.action_slot = act.slots[0]
            except Exception:
                pass
        strip.action_frame_start = 1
        strip.action_frame_end = length
        track.mute = False


def export_glb(slug: str, arm) -> Path:
    mesh = bpy.data.objects[f"{ident(slug)}_Body"]
    bpy.ops.object.select_all(action="DESELECT")
    mesh.select_set(True)
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    out = OUT_DIR / f"{slug}-rigged-full.glb"
    bpy.ops.export_scene.gltf(
        filepath=str(out),
        export_format="GLB",
        use_selection=True,
        export_animations=True,
        export_animation_mode="NLA_TRACKS",
        export_force_sampling=True,
        export_optimize_animation_size=False,
    )
    return out


def process(slug: str) -> None:
    blend = WORK_DIR / f"{slug}-rig.blend"
    bpy.ops.wm.open_mainfile(filepath=str(blend))
    scene = bpy.context.scene
    scene.render.fps = FPS
    arm = bpy.data.objects[f"{ident(slug)}_FullRig"]

    clips = {}
    for fn in (clip_idle, clip_walk, clip_run, clip_jump, clip_wave, clip_cheer, clip_dance, clip_spin, clip_throw, clip_sit):
        act, length = fn(arm)
        clips[act.name] = (act, length)

    render_check_frames(slug, arm, clips)
    reset_pose(arm)
    push_nla(arm, clips)
    out = export_glb(slug, arm)
    bpy.ops.wm.save_as_mainfile(filepath=str(WORK_DIR / f"{slug}-rig-animated.blend"))
    print("EXPORTED", out)


def main() -> None:
    for slug in SLUGS:
        if (WORK_DIR / f"{slug}-rig.blend").exists():
            process(slug)


main()
