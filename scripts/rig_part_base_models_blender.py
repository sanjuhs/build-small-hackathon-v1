"""Rig v2 SAM base bodies and assemble socketed prop test models.

Run from the project root:

    blender --background --python scripts/rig_part_base_models_blender.py

Outputs:
    assets/generated/part-models/rigged-bases/*-base-rigged.glb
    assets/generated/part-models/assemblies/*-assembled.glb
    assets/generated/part-models/mixamo-fbx/*-base-*.fbx
    assets/generated/part-models/blend-scenes/*-assembly.blend
    assets/generated/previews/*-part-base-rigged.png
    assets/generated/previews/*-part-assembly.png
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "assets" / "generated" / "part-concepts" / "parts-manifest.json"
RAW_ROOT = ROOT / "assets" / "generated" / "part-models" / "raw"
OUT_ROOT = ROOT / "assets" / "generated" / "part-models"
RIGGED_BASE_DIR = OUT_ROOT / "rigged-bases"
ASSEMBLY_DIR = OUT_ROOT / "assemblies"
MIXAMO_DIR = OUT_ROOT / "mixamo-fbx"
BLEND_DIR = OUT_ROOT / "blend-scenes"
PREVIEW_DIR = ROOT / "assets" / "generated" / "previews"


CHARACTER_ORDER = ("squeaky", "electraica", "fire-boy", "shark-girl")
DEFORM_BONES = (
    "Root",
    "Spine",
    "Head",
    "Arm.L",
    "Hand.L",
    "Arm.R",
    "Hand.R",
    "Leg.L",
    "Foot.L",
    "Leg.R",
    "Foot.R",
)
SOCKET_BONES = ("Hat", "Backpack", "Chest", "Prop.L", "Prop.R")
PROP_MASS_KG = {
    "headwear": 0.09,
    "backpack": 0.34,
    "handheld-prop": 0.14,
    "clothing": 0.08,
    "strap": 0.05,
}


def clear_scene() -> None:
    bpy.ops.object.mode_set(mode="OBJECT") if bpy.ops.object.mode_set.poll() else None
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()
    for action in list(bpy.data.actions):
        bpy.data.actions.remove(action)


def material(name: str, color: tuple[float, float, float, float], roughness: float = 0.82) -> bpy.types.Material:
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = color
        bsdf.inputs["Roughness"].default_value = roughness
        if "Metallic" in bsdf.inputs:
            bsdf.inputs["Metallic"].default_value = 0
    return mat


def look_at(obj: bpy.types.Object, target: tuple[float, float, float]) -> None:
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def setup_render_scene(slug: str) -> None:
    world = bpy.context.scene.world or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.color = (1.0, 0.97, 0.91)
    bpy.context.scene.render.resolution_x = 1200
    bpy.context.scene.render.resolution_y = 1200
    try:
        bpy.context.scene.render.engine = "BLENDER_EEVEE_NEXT"
    except TypeError:
        bpy.context.scene.render.engine = "BLENDER_EEVEE"
    if hasattr(bpy.context.scene, "eevee"):
        bpy.context.scene.eevee.taa_render_samples = 96

    floor_mat = material(f"{slug}_socket_floor", (0.98, 0.93, 0.82, 1), 0.9)
    bpy.ops.mesh.primitive_cylinder_add(vertices=96, radius=1.7, depth=0.045, location=(0, 0.13, -0.30))
    floor = bpy.context.object
    floor.name = f"{slug}_socket_plinth"
    floor.scale.x = 1.12
    floor.scale.y = 0.9
    floor.data.materials.append(floor_mat)

    bpy.ops.object.light_add(type="AREA", location=(0.0, -3.9, 4.8))
    key = bpy.context.object
    key.name = f"{slug}_front_softbox"
    key.data.energy = 820
    key.data.size = 5.2

    bpy.ops.object.light_add(type="AREA", location=(-3.0, -2.3, 3.0))
    fill = bpy.context.object
    fill.name = f"{slug}_warm_fill"
    fill.data.energy = 275
    fill.data.size = 3.3
    fill.data.color = (1.0, 0.88, 0.72)

    bpy.ops.object.light_add(type="POINT", location=(2.7, -2.0, 2.5))
    rim = bpy.context.object
    rim.name = f"{slug}_cool_rim"
    rim.data.energy = 90
    rim.data.color = (0.78, 0.95, 1.0)

    bpy.ops.object.camera_add(location=(0, -5.9, 1.35))
    camera = bpy.context.object
    camera.name = f"{slug}_socket_camera"
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = 2.75
    look_at(camera, (0, 0, 0.92))
    bpy.context.scene.camera = camera


def imported_objects(path: Path) -> list[bpy.types.Object]:
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    return [obj for obj in bpy.data.objects if obj not in before]


def mesh_objects(objects: list[bpy.types.Object]) -> list[bpy.types.Object]:
    return [obj for obj in objects if obj.type == "MESH"]


def top_level_objects(objects: list[bpy.types.Object]) -> list[bpy.types.Object]:
    object_set = set(objects)
    return [obj for obj in objects if obj.parent not in object_set]


def bbox_for(objects: list[bpy.types.Object]) -> tuple[Vector, Vector]:
    min_v = Vector((math.inf, math.inf, math.inf))
    max_v = Vector((-math.inf, -math.inf, -math.inf))
    meshes = mesh_objects(objects)
    if not meshes:
        return Vector((-0.5, -0.5, 0)), Vector((0.5, 0.5, 1))
    for obj in meshes:
        for corner in obj.bound_box:
            point = obj.matrix_world @ Vector(corner)
            min_v.x = min(min_v.x, point.x)
            min_v.y = min(min_v.y, point.y)
            min_v.z = min(min_v.z, point.z)
            max_v.x = max(max_v.x, point.x)
            max_v.y = max(max_v.y, point.y)
            max_v.z = max(max_v.z, point.z)
    return min_v, max_v


def clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def smoothstep(edge0: float, edge1: float, value: float) -> float:
    if edge0 == edge1:
        return 1.0 if value >= edge1 else 0.0
    t = clamp((value - edge0) / (edge1 - edge0))
    return t * t * (3.0 - 2.0 * t)


def segment_falloff(point: Vector, head: Vector, tail: Vector, radius: float) -> float:
    segment = tail - head
    length_squared = max(segment.length_squared, 1e-8)
    factor = clamp((point - head).dot(segment) / length_squared)
    nearest = head + segment * factor
    distance = (point - nearest).length
    normalized = distance / max(radius, 1e-4)
    return 1.0 / (1.0 + normalized**4)


def normalized_top_weights(raw: dict[str, float], limit: int = 4) -> list[tuple[str, float]]:
    items = [(name, weight) for name, weight in raw.items() if weight > 1e-5]
    if not items:
        return [("Spine", 1.0)]
    items.sort(key=lambda item: item[1], reverse=True)
    items = items[:limit]
    total = sum(weight for _, weight in items) or 1.0
    return [(name, weight / total) for name, weight in items]


def clean_meshes(objects: list[bpy.types.Object]) -> None:
    for obj in mesh_objects(objects):
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.ops.object.shade_smooth()
        obj.select_set(False)
        obj.data.validate(clean_customdata=False)
        obj.data.update()
        for polygon in obj.data.polygons:
            polygon.use_smooth = True

        normal = obj.modifiers.new("toybox_weighted_normals", "WEIGHTED_NORMAL")
        normal.keep_sharp = True
        normal.weight = 50

        for mat in obj.data.materials:
            if not mat:
                continue
            mat.use_nodes = True
            bsdf = mat.node_tree.nodes.get("Principled BSDF")
            if bsdf:
                if "Roughness" in bsdf.inputs:
                    bsdf.inputs["Roughness"].default_value = 0.78
                if "Metallic" in bsdf.inputs:
                    bsdf.inputs["Metallic"].default_value = 0


def normalize_and_bake(objects: list[bpy.types.Object], slug: str, target_height: float = 2.25) -> None:
    min_v, max_v = bbox_for(objects)
    center = (min_v + max_v) / 2
    size = max_v - min_v
    height = max(size.z, 0.01)
    scale = target_height / height

    root = bpy.data.objects.new(f"{slug}_base_normalize_root", None)
    bpy.context.collection.objects.link(root)
    for obj in top_level_objects(objects):
        world = obj.matrix_world.copy()
        obj.parent = root
        obj.matrix_world = world
    root.scale = (scale, scale, scale)
    root.location = (-center.x * scale, -center.y * scale, -min_v.z * scale)

    for obj in top_level_objects(objects):
        world = obj.matrix_world.copy()
        obj.parent = None
        obj.matrix_world = world
    bpy.data.objects.remove(root, do_unlink=True)

    for obj in mesh_objects(objects):
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)


def create_armature(slug: str, objects: list[bpy.types.Object]) -> tuple[bpy.types.Object, list[tuple[str, Vector, Vector]]]:
    min_v, max_v = bbox_for(objects)
    size = max_v - min_v
    height = max(size.z, 1.0)
    width = max(size.x, 0.9)
    depth = max(size.y, 0.55)
    center_x = (min_v.x + max_v.x) / 2
    center_y = (min_v.y + max_v.y) / 2
    z0 = min_v.z

    def p(x: float, y: float, z: float) -> Vector:
        return Vector((center_x + x * width, center_y + y * depth, z0 + z * height))

    bones = [
        ("Root", p(0, 0, 0.26), p(0, 0, 0.38), None),
        ("Spine", p(0, 0, 0.38), p(0, 0, 0.62), "Root"),
        ("Head", p(0, 0, 0.62), p(0, 0, 0.91), "Spine"),
        ("Arm.L", p(-0.17, -0.04, 0.59), p(-0.34, -0.15, 0.42), "Spine"),
        ("Hand.L", p(-0.34, -0.15, 0.42), p(-0.48, -0.22, 0.38), "Arm.L"),
        ("Arm.R", p(0.17, -0.04, 0.59), p(0.34, -0.15, 0.42), "Spine"),
        ("Hand.R", p(0.34, -0.15, 0.42), p(0.48, -0.22, 0.38), "Arm.R"),
        ("Leg.L", p(-0.12, 0.00, 0.30), p(-0.20, -0.03, 0.12), "Root"),
        ("Foot.L", p(-0.20, -0.03, 0.12), p(-0.28, -0.12, 0.04), "Leg.L"),
        ("Leg.R", p(0.12, 0.00, 0.30), p(0.20, -0.03, 0.12), "Root"),
        ("Foot.R", p(0.20, -0.03, 0.12), p(0.28, -0.12, 0.04), "Leg.R"),
        ("Hat", p(0, -0.01, 0.91), p(0, -0.01, 1.05), "Head"),
        ("Backpack", p(0, 0.30, 0.58), p(0, 0.45, 0.46), "Spine"),
        ("Chest", p(0, -0.30, 0.52), p(0, -0.42, 0.52), "Spine"),
        ("Prop.L", p(-0.48, -0.22, 0.38), p(-0.56, -0.27, 0.38), "Hand.L"),
        ("Prop.R", p(0.48, -0.22, 0.38), p(0.56, -0.27, 0.38), "Hand.R"),
    ]

    arm_data = bpy.data.armatures.new(f"{slug}_Toybox_BaseRig")
    armature = bpy.data.objects.new(f"{slug}_Toybox_BaseRig", arm_data)
    bpy.context.collection.objects.link(armature)
    bpy.context.view_layer.objects.active = armature
    armature.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")

    edit_bones = {}
    for name, head, tail, parent in bones:
        bone = arm_data.edit_bones.new(name)
        bone.head = head
        bone.tail = tail
        bone.roll = 0
        bone.use_deform = name in DEFORM_BONES
        if parent:
            bone.parent = edit_bones[parent]
            bone.use_connect = False
        edit_bones[name] = bone

    bpy.ops.object.mode_set(mode="POSE")
    for pose_bone in armature.pose.bones:
        pose_bone.rotation_mode = "XYZ"
    bpy.ops.object.mode_set(mode="OBJECT")
    armature.show_in_front = True
    armature.data.display_type = "STICK"
    armature["toybox_rig_version"] = "aligned_chibi_v4"
    armature["toybox_deform_bones"] = ", ".join(DEFORM_BONES)
    armature["toybox_socket_bones"] = ", ".join(SOCKET_BONES)
    return armature, [(name, head, tail) for name, head, tail, _ in bones]


def clear_vertex_groups(obj: bpy.types.Object) -> None:
    while obj.vertex_groups:
        obj.vertex_groups.remove(obj.vertex_groups[0])


def assign_weights(objects: list[bpy.types.Object], armature: bpy.types.Object) -> None:
    min_v, max_v = bbox_for(objects)
    size = max_v - min_v
    height = max(size.z, 1.0)
    width = max(size.x, 0.9)
    center_x = (min_v.x + max_v.x) / 2
    z0 = min_v.z
    bone_segments = {
        bone.name: (bone.head_local.copy(), bone.tail_local.copy())
        for bone in armature.data.bones
        if bone.name in DEFORM_BONES
    }
    root_head, root_tail = bone_segments["Root"]

    for obj in mesh_objects(objects):
        clear_vertex_groups(obj)
        groups = {name: obj.vertex_groups.new(name=name) for name in DEFORM_BONES}
        for vertex in obj.data.vertices:
            world = obj.matrix_world @ vertex.co
            xf = (world.x - center_x) / width
            zf = (world.z - z0) / height
            ax = abs(xf)
            side = ".L" if xf < 0 else ".R"

            raw = {
                "Root": (
                    0.78 * (1.0 - smoothstep(0.34, 0.52, zf))
                    + 1.15 * segment_falloff(world, root_head, root_tail, width * 0.24)
                ),
                "Spine": 1.45 * smoothstep(0.28, 0.45, zf) * (1.0 - smoothstep(0.60, 0.76, zf)),
                "Head": 1.65 * smoothstep(0.56, 0.69, zf),
            }

            arm_mask = (
                smoothstep(0.20, 0.34, ax)
                * smoothstep(0.32, 0.42, zf)
                * (1.0 - smoothstep(0.64, 0.76, zf))
            )
            if arm_mask > 0.015:
                arm_name = f"Arm{side}"
                hand_name = f"Hand{side}"
                arm_head, arm_tail = bone_segments[arm_name]
                hand_head, hand_tail = bone_segments[hand_name]
                raw[arm_name] = arm_mask * (0.28 + 1.55 * segment_falloff(world, arm_head, arm_tail, width * 0.18))
                raw[hand_name] = arm_mask * (0.18 + 1.65 * segment_falloff(world, hand_head, hand_tail, width * 0.15))
                raw["Spine"] *= max(0.18, 1.0 - arm_mask * 0.78)
                raw["Root"] *= max(0.28, 1.0 - arm_mask * 0.55)

            leg_mask = smoothstep(0.05, 0.16, ax) * (1.0 - smoothstep(0.34, 0.48, zf))
            if leg_mask > 0.015:
                leg_name = f"Leg{side}"
                foot_name = f"Foot{side}"
                leg_head, leg_tail = bone_segments[leg_name]
                foot_head, foot_tail = bone_segments[foot_name]
                raw[leg_name] = leg_mask * (0.24 + 1.55 * segment_falloff(world, leg_head, leg_tail, width * 0.15))
                raw[foot_name] = leg_mask * (0.16 + 1.45 * segment_falloff(world, foot_head, foot_tail, width * 0.14))
                raw["Root"] *= max(0.22, 1.0 - leg_mask * 0.70)
                raw["Spine"] *= max(0.16, 1.0 - leg_mask * 0.82)

            # Keep large plush heads from stealing shoulder and earphone vertices into the arms.
            if zf > 0.66:
                raw = {"Head": raw.get("Head", 1.0), "Spine": raw.get("Spine", 0.0) * 0.24}

            for bone_name, weight in normalized_top_weights(raw):
                groups[bone_name].add([vertex.index], weight, "ADD")

        mod = obj.modifiers.new("toybox_base_armature", "ARMATURE")
        mod.object = armature
        if hasattr(mod, "use_deform_preserve_volume"):
            mod.use_deform_preserve_volume = True
        obj.parent = armature
        obj["toybox_role"] = "rigged_base_mesh"
        obj["toybox_weighting"] = "aligned_chibi_v4"


def set_pose_frame(armature: bpy.types.Object, frame: int, pose: dict[str, tuple[float, float, float]]) -> None:
    bpy.context.scene.frame_set(frame)
    animated_bones = ("Root", "Head", "Arm.L", "Hand.L", "Arm.R", "Hand.R", "Leg.L", "Foot.L", "Leg.R", "Foot.R")
    for bone_name in animated_bones:
        bone = armature.pose.bones.get(bone_name)
        if not bone:
            continue
        if bone_name == "Root":
            bone.location = pose.get(bone_name, (0, 0, 0))
            bone.keyframe_insert("location", frame=frame)
        else:
            bone.rotation_euler = pose.get(bone_name, (0, 0, 0))
            bone.keyframe_insert("rotation_euler", frame=frame)


def build_action(
    armature: bpy.types.Object,
    action_name: str,
    frames: list[tuple[int, dict[str, tuple[float, float, float]]]],
) -> None:
    armature.animation_data_clear()
    armature.animation_data_create()
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode="POSE")
    for frame, pose in frames:
        set_pose_frame(armature, frame, pose)
    action = armature.animation_data.action
    if action:
        action.name = action_name
    bpy.ops.object.mode_set(mode="OBJECT")


def animate_base(armature: bpy.types.Object, end_frame: int = 72) -> None:
    bpy.context.view_layer.objects.active = armature
    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end = end_frame

    build_action(
        armature,
        "Idle bounce",
        [
            (1, {"Root": (0, 0, 0), "Head": (0, 0, -0.03), "Arm.L": (0.03, 0, 0.05), "Arm.R": (-0.03, 0, -0.05)}),
            (24, {"Root": (0, 0, 0.035), "Head": (0.03, 0, 0.06), "Arm.L": (0.08, 0, -0.10), "Arm.R": (-0.08, 0, 0.10)}),
            (48, {"Root": (0, 0, 0), "Head": (0, 0, -0.03), "Arm.L": (0.03, 0, 0.05), "Arm.R": (-0.03, 0, -0.05)}),
        ],
    )
    build_action(
        armature,
        "Friendly wave",
        [
            (1, {"Root": (0, 0, 0), "Head": (0, 0, -0.02), "Arm.R": (-0.15, 0, 0.20), "Hand.R": (0, 0, 0.10)}),
            (16, {"Root": (0, 0, 0.018), "Head": (0.02, 0, 0.04), "Arm.R": (-0.65, 0, 0.46), "Hand.R": (0, 0, -0.42)}),
            (32, {"Root": (0, 0, 0.018), "Head": (0.02, 0, 0.04), "Arm.R": (-0.65, 0, 0.46), "Hand.R": (0, 0, 0.42)}),
            (48, {"Root": (0, 0, 0), "Head": (0, 0, -0.02), "Arm.R": (-0.15, 0, 0.20), "Hand.R": (0, 0, 0.10)}),
        ],
    )
    build_action(
        armature,
        "Tiny waddle",
        [
            (1, {"Root": (-0.025, 0, 0), "Head": (0.00, 0, -0.02), "Arm.L": (0.05, 0, 0.14), "Arm.R": (-0.05, 0, -0.14), "Leg.L": (0.08, 0, 0.08), "Leg.R": (-0.06, 0, -0.06)}),
            (18, {"Root": (0.025, 0, 0.03), "Head": (0.03, 0, 0.04), "Arm.L": (0.08, 0, -0.14), "Arm.R": (-0.08, 0, 0.14), "Leg.L": (-0.06, 0, -0.06), "Leg.R": (0.08, 0, 0.08)}),
            (36, {"Root": (-0.025, 0, 0), "Head": (0.00, 0, -0.02), "Arm.L": (0.05, 0, 0.14), "Arm.R": (-0.05, 0, -0.14), "Leg.L": (0.08, 0, 0.08), "Leg.R": (-0.06, 0, -0.06)}),
        ],
    )
    build_action(
        armature,
        "Happy hop",
        [
            (1, {"Root": (0, 0, 0), "Head": (0, 0, -0.02), "Arm.L": (0.08, 0, 0.18), "Arm.R": (-0.08, 0, -0.18), "Leg.L": (0.02, 0, 0.03), "Leg.R": (-0.02, 0, -0.03)}),
            (14, {"Root": (0, 0, -0.018), "Head": (-0.03, 0, -0.04), "Arm.L": (0.20, 0, 0.24), "Arm.R": (-0.20, 0, -0.24), "Leg.L": (0.10, 0, 0.08), "Leg.R": (-0.10, 0, -0.08)}),
            (28, {"Root": (0, 0, 0.085), "Head": (0.05, 0, 0.07), "Arm.L": (-0.20, 0, -0.32), "Arm.R": (0.20, 0, 0.32), "Leg.L": (-0.10, 0, -0.06), "Leg.R": (0.10, 0, 0.06)}),
            (44, {"Root": (0, 0, 0), "Head": (0, 0, -0.02), "Arm.L": (0.08, 0, 0.18), "Arm.R": (-0.08, 0, -0.18), "Leg.L": (0.02, 0, 0.03), "Leg.R": (-0.02, 0, -0.03)}),
        ],
    )
    armature.animation_data.action = bpy.data.actions.get("Idle bounce")
    bpy.context.scene.frame_set(24)


def add_rig_preview_visuals(slug: str, bones: list[tuple[str, Vector, Vector]]) -> list[bpy.types.Object]:
    rig_mat = material(f"{slug}_socket_rig_cyan", (0.06, 0.78, 0.92, 1), 0.36)
    joint_mat = material(f"{slug}_socket_rig_gold", (1.0, 0.74, 0.18, 1), 0.42)
    visuals: list[bpy.types.Object] = []
    for name, head, tail in bones:
        head_v = Vector((head.x, head.y - 0.82, head.z))
        tail_v = Vector((tail.x, tail.y - 0.82, tail.z))
        mid = (head_v + tail_v) / 2
        length = (tail_v - head_v).length
        bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.009, depth=length, location=mid)
        line = bpy.context.object
        line.name = f"{slug}_RigPreviewLine_{name}"
        line.rotation_euler = (tail_v - head_v).to_track_quat("Z", "Y").to_euler()
        line.data.materials.append(rig_mat)
        bpy.ops.object.shade_smooth()
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, location=head_v)
        joint = bpy.context.object
        joint.name = f"{slug}_RigPreviewJoint_{name}"
        joint.scale = (0.024, 0.024, 0.024)
        joint.data.materials.append(joint_mat)
        bpy.ops.object.shade_smooth()
        visuals.extend([line, joint])
    return visuals


def render_png(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.context.scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)


def export_glb(path: Path, objects: list[bpy.types.Object], include_animations: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.export_scene.gltf(
        filepath=str(path),
        export_format="GLB",
        use_selection=True,
        export_apply=False,
        export_animations=include_animations,
        export_frame_range=True,
        export_extras=True,
    )


def export_fbx(path: Path, objects: list[bpy.types.Object], include_armature: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.export_scene.fbx(
        filepath=str(path),
        use_selection=True,
        add_leaf_bones=False,
        bake_anim=include_armature,
        object_types={"MESH", "ARMATURE"} if include_armature else {"MESH"},
    )


def target_size_for(part: dict[str, Any], body_size: Vector) -> float:
    kind = part.get("kind")
    attach = part.get("attach")
    part_id = part.get("id", "")
    height = max(body_size.z, 1.0)
    width = max(body_size.x, 0.9)
    if "guitar" in part_id and kind == "handheld-prop":
        return height * 0.46
    if "flute" in part_id:
        return width * 0.58
    if "pocket-clock" in part_id:
        return width * 0.32
    if "hex-nut" in part_id or "bolt" in part_id:
        return width * 0.24
    if "tuxedo" in part_id:
        return width * 0.34
    if "chest-plate" in part_id:
        return width * 0.32
    if "bowtie" in part_id:
        return width * 0.24
    if kind == "backpack":
        return height * 0.36
    if kind == "headwear":
        return width * 0.42
    if kind == "clothing":
        return width * (0.48 if attach == "Spine" else 0.36)
    if kind == "strap":
        return height * 0.54
    if kind == "handheld-prop":
        return width * 0.28
    return width * 0.32


def target_location_for(part: dict[str, Any], body_min: Vector, body_max: Vector, prop_size: Vector) -> tuple[Vector, str]:
    body_size = body_max - body_min
    center_x = (body_min.x + body_max.x) / 2
    center_y = (body_min.y + body_max.y) / 2
    z0 = body_min.z
    attach = part.get("attach", "Root")
    kind = part.get("kind", "")
    part_id = part.get("id", "")

    if attach == "Hat":
        return Vector((center_x, center_y - 0.04 * body_size.y, body_max.z + prop_size.z * 0.24)), "Hat"
    if attach == "Backpack":
        return Vector((center_x, body_max.y + prop_size.y * 0.30, z0 + body_size.z * 0.53)), "Backpack"
    if "guitar" in part_id and kind == "handheld-prop":
        return Vector((center_x + body_size.x * 0.22, body_min.y - prop_size.y * 0.42, z0 + body_size.z * 0.34)), "Prop.R"
    if "flute" in part_id:
        return Vector((center_x + body_size.x * 0.30, body_min.y - prop_size.y * 0.45, z0 + body_size.z * 0.32)), "Prop.R"
    if "tuxedo" in part_id:
        return Vector((center_x, body_min.y - prop_size.y * 0.50, z0 + body_size.z * 0.33)), "Chest"
    if "chest-plate" in part_id:
        return Vector((center_x, body_min.y - prop_size.y * 0.50, z0 + body_size.z * 0.40)), "Chest"
    if "bowtie" in part_id:
        return Vector((center_x, body_min.y - prop_size.y * 0.48, z0 + body_size.z * 0.55)), "Chest"
    if attach == "Prop.L":
        return Vector((body_min.x - prop_size.x * 0.16, body_min.y - prop_size.y * 0.45, z0 + body_size.z * 0.36)), "Prop.L"
    if attach == "Prop.R":
        return Vector((body_max.x + prop_size.x * 0.16, body_min.y - prop_size.y * 0.45, z0 + body_size.z * 0.36)), "Prop.R"
    if kind == "strap":
        return Vector((center_x, body_min.y - prop_size.y * 0.46, z0 + body_size.z * 0.50)), "Chest"
    return Vector((center_x, body_min.y - prop_size.y * 0.50, z0 + body_size.z * 0.48)), "Chest"


def imported_part_root(slug: str, part: dict[str, Any], body_min: Vector, body_max: Vector) -> bpy.types.Object:
    part_id = part["id"]
    path = RAW_ROOT / slug / f"{part_id}-sam.glb"
    if not path.exists():
        raise FileNotFoundError(path)

    imported = imported_objects(path)
    clean_meshes(imported)
    root = bpy.data.objects.new(f"{part_id}_socket_root", None)
    bpy.context.collection.objects.link(root)
    for obj in top_level_objects(imported):
        world = obj.matrix_world.copy()
        obj.parent = root
        obj.matrix_world = world

    min_v, max_v = bbox_for(imported)
    prop_size = max_v - min_v
    max_dim = max(prop_size.x, prop_size.y, prop_size.z, 0.01)
    body_size = body_max - body_min
    scale = target_size_for(part, body_size) / max_dim
    center = (min_v + max_v) / 2
    root.scale = (scale, scale, scale)
    root.location = -center * scale
    bpy.context.view_layer.update()

    placed_min, placed_max = bbox_for(imported)
    placed_size = placed_max - placed_min
    target, attach_bone = target_location_for(part, body_min, body_max, placed_size)
    placed_center = (placed_min + placed_max) / 2
    root.location += target - placed_center

    mass = PROP_MASS_KG.get(part.get("kind", ""), 0.1)
    for obj in mesh_objects(imported):
        obj["toybox_role"] = "socketed_prop"
        obj["toybox_part_id"] = part_id
        obj["toybox_attach_bone"] = attach_bone
        obj["toybox_mass_kg"] = mass
        obj["toybox_can_detach"] = True
        try:
            bpy.ops.object.select_all(action="DESELECT")
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
            bpy.ops.rigidbody.object_add(type="ACTIVE")
            obj.rigid_body.mass = mass
            obj.rigid_body.friction = 0.68
            obj.rigid_body.restitution = 0.12
        except Exception:
            pass

    root["toybox_role"] = "socket_root"
    root["toybox_part_id"] = part_id
    root["toybox_attach_bone"] = attach_bone
    root["toybox_mass_kg"] = mass
    return root


def parent_to_bone_keep_world(obj: bpy.types.Object, armature: bpy.types.Object, bone_name: str) -> None:
    world = obj.matrix_world.copy()
    obj.parent = armature
    obj.parent_type = "BONE"
    obj.parent_bone = bone_name
    obj.matrix_world = world


def animate_prop_attach(root: bpy.types.Object, attach_bone: str, index: int) -> None:
    base_location = root.location.copy()
    side = -1 if attach_bone.endswith(".L") else 1
    if attach_bone in {"Hat", "Backpack", "Chest"}:
        side = -1 if index % 2 else 1
    staged_offset = Vector((side * (0.55 + 0.08 * index), -0.45, 0.24 + 0.03 * index))
    for frame, location in (
        (1, base_location + staged_offset),
        (36, base_location),
        (72, base_location),
        (96, base_location + staged_offset * 0.34),
    ):
        bpy.context.scene.frame_set(frame)
        root.location = location
        root.keyframe_insert("location", frame=frame)
    root.location = base_location


def collect_export_objects(armature: bpy.types.Object, base_objects: list[bpy.types.Object], prop_roots: list[bpy.types.Object]) -> list[bpy.types.Object]:
    selected = [armature, *mesh_objects(base_objects)]
    for root in prop_roots:
        selected.append(root)
        selected.extend(root.children_recursive)
    return selected


def load_manifest() -> list[dict[str, Any]]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    characters = manifest["characters"]
    order = {slug: index for index, slug in enumerate(CHARACTER_ORDER)}
    return sorted(characters, key=lambda item: order.get(item["slug"], 99))


def process_character(character: dict[str, Any]) -> None:
    slug = character["slug"]
    label = character["name"]
    base_id = character["base"]["id"]
    base_path = RAW_ROOT / slug / f"{base_id}-sam.glb"
    if not base_path.exists():
        raise FileNotFoundError(base_path)

    clear_scene()
    setup_render_scene(slug)
    base_objects = imported_objects(base_path)
    clean_meshes(base_objects)
    normalize_and_bake(base_objects, slug)

    for obj in mesh_objects(base_objects):
        obj["toybox_character"] = slug
        obj["toybox_role"] = "base_body"

    body_min, body_max = bbox_for(base_objects)
    body_size = body_max - body_min

    export_fbx(MIXAMO_DIR / f"{slug}-base-mesh.fbx", mesh_objects(base_objects), include_armature=False)

    armature, bones = create_armature(slug, base_objects)
    assign_weights(base_objects, armature)
    animate_base(armature)

    rig_visuals = add_rig_preview_visuals(slug, bones)
    render_png(PREVIEW_DIR / f"{slug}-part-base-rigged.png")
    for visual in rig_visuals:
        bpy.data.objects.remove(visual, do_unlink=True)

    base_export_objects = [armature, *mesh_objects(base_objects)]
    export_glb(RIGGED_BASE_DIR / f"{slug}-base-rigged.glb", base_export_objects)
    export_fbx(MIXAMO_DIR / f"{slug}-base-rigged.fbx", base_export_objects, include_armature=True)

    prop_roots: list[bpy.types.Object] = []
    for index, part in enumerate(character["parts"], start=1):
        root = imported_part_root(slug, part, body_min, body_max)
        attach_bone = root.get("toybox_attach_bone", "Spine")
        parent_to_bone_keep_world(root, armature, attach_bone)
        animate_prop_attach(root, attach_bone, index)
        prop_roots.append(root)

    bpy.context.scene.frame_set(36)
    render_png(PREVIEW_DIR / f"{slug}-part-assembly.png")

    all_export_objects = collect_export_objects(armature, base_objects, prop_roots)
    export_glb(ASSEMBLY_DIR / f"{slug}-assembled.glb", all_export_objects)

    BLEND_DIR.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_DIR / f"{slug}-assembly.blend"))
    print(f"{label}: rigged base, Mixamo FBX, and assembly exported")


def main() -> None:
    for directory in (RIGGED_BASE_DIR, ASSEMBLY_DIR, MIXAMO_DIR, BLEND_DIR, PREVIEW_DIR):
        directory.mkdir(parents=True, exist_ok=True)
    for character in load_manifest():
        process_character(character)


if __name__ == "__main__":
    main()
