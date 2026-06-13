"""Convert downloaded Mixamo FBX files into GLB motion-test assets.

Place downloaded FBX files under:

    assets/generated/part-models/mixamo-downloads/<character-slug>/*.fbx

Then run:

    blender --background --python scripts/import_mixamo_motions_blender.py

Outputs:
    assets/generated/part-models/mixamo-motion-tests/<character-slug>/*.glb
    assets/generated/previews/*-mixamo-*.png
"""

from __future__ import annotations

import math
import re
from pathlib import Path

import bpy
from mathutils import Quaternion
from mathutils import Vector


ROOT = Path(__file__).resolve().parents[1]
INPUT_ROOT = ROOT / "assets" / "generated" / "part-models" / "mixamo-downloads"
OUTPUT_ROOT = ROOT / "assets" / "generated" / "part-models" / "mixamo-motion-tests"
RIGGED_BASE_ROOT = ROOT / "assets" / "generated" / "part-models" / "rigged-bases"
PREVIEW_ROOT = ROOT / "assets" / "generated" / "previews"

CHARACTER_SLUGS = ("squeaky", "electraica", "fire-boy", "shark-girl")
MIXAMO_TO_TOYBOX = {
    "Spine": "mixamorig:Spine1",
    "Head": "mixamorig:Head",
    "Arm.L": "mixamorig:LeftArm",
    "Hand.L": "mixamorig:LeftForeArm",
    "Arm.R": "mixamorig:RightArm",
    "Hand.R": "mixamorig:RightForeArm",
    "Leg.L": "mixamorig:LeftUpLeg",
    "Foot.L": "mixamorig:LeftFoot",
    "Leg.R": "mixamorig:RightUpLeg",
    "Foot.R": "mixamorig:RightFoot",
}
MOTION_STRENGTH = {
    "Spine": 0.38,
    "Head": 0.45,
    "Arm.L": 0.72,
    "Hand.L": 0.62,
    "Arm.R": 0.72,
    "Hand.R": 0.62,
    "Leg.L": 0.58,
    "Foot.L": 0.62,
    "Leg.R": 0.58,
    "Foot.R": 0.62,
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

    floor_mat = material(f"{slug}_mixamo_floor", (0.98, 0.93, 0.82, 1), 0.9)
    bpy.ops.mesh.primitive_cylinder_add(vertices=96, radius=1.7, depth=0.045, location=(0, 0.13, -0.035))
    floor = bpy.context.object
    floor.name = f"{slug}_mixamo_preview_floor"
    floor.scale.x = 1.12
    floor.scale.y = 0.9
    floor.data.materials.append(floor_mat)

    bpy.ops.object.light_add(type="AREA", location=(0.0, -3.9, 4.8))
    key = bpy.context.object
    key.name = f"{slug}_mixamo_key"
    key.data.energy = 820
    key.data.size = 5.2

    bpy.ops.object.light_add(type="AREA", location=(-3.0, -2.3, 3.0))
    fill = bpy.context.object
    fill.name = f"{slug}_mixamo_fill"
    fill.data.energy = 260
    fill.data.size = 3.3
    fill.data.color = (1.0, 0.88, 0.72)

    bpy.ops.object.camera_add(location=(0, -5.9, 1.35))
    camera = bpy.context.object
    camera.name = f"{slug}_mixamo_camera"
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = 2.75
    look_at(camera, (0, 0, 0.92))
    bpy.context.scene.camera = camera


def slugify(value: str) -> str:
    value = value.lower().replace("_", "-")
    value = re.sub(r"[^a-z0-9-]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value or "motion"


def titleize(value: str) -> str:
    return slugify(value).replace("-", " ").title()


def imported_objects(path: Path) -> list[bpy.types.Object]:
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=str(path))
    return [obj for obj in bpy.data.objects if obj not in before]


def imported_glb_objects(path: Path) -> list[bpy.types.Object]:
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    return [obj for obj in bpy.data.objects if obj not in before]


def mesh_objects(objects: list[bpy.types.Object]) -> list[bpy.types.Object]:
    return [obj for obj in objects if obj.type == "MESH"]


def top_level_objects(objects: list[bpy.types.Object]) -> list[bpy.types.Object]:
    object_set = set(objects)
    return [obj for obj in objects if obj.parent not in object_set]


def armature_object(objects: list[bpy.types.Object]) -> bpy.types.Object:
    for obj in objects:
        if obj.type == "ARMATURE":
            return obj
    raise RuntimeError("No armature found")


def bbox_for(objects: list[bpy.types.Object]) -> tuple[Vector, Vector]:
    min_v = Vector((math.inf, math.inf, math.inf))
    max_v = Vector((-math.inf, -math.inf, -math.inf))
    meshes = mesh_objects(objects)
    if not meshes:
        return Vector((-0.5, -0.5, 0)), Vector((0.5, 0.5, 1))
    bpy.context.view_layer.update()
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


def clean_materials(objects: list[bpy.types.Object]) -> None:
    for obj in mesh_objects(objects):
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        try:
            bpy.ops.object.shade_smooth()
        except Exception:
            pass
        obj.select_set(False)
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


def normalize_under_root(objects: list[bpy.types.Object], slug: str, target_height: float = 2.25) -> bpy.types.Object:
    min_v, max_v = bbox_for(objects)
    center = (min_v + max_v) / 2
    size = max_v - min_v
    height = max(size.z, 0.01)
    scale = target_height / height

    root = bpy.data.objects.new(f"{slug}_mixamo_normalize_root", None)
    bpy.context.collection.objects.link(root)
    for obj in top_level_objects(objects):
        world = obj.matrix_world.copy()
        obj.parent = root
        obj.matrix_world = world
    root.scale = (scale, scale, scale)
    root.location = (-center.x * scale, -center.y * scale, -min_v.z * scale)
    return root


def remove_actions() -> None:
    for action in list(bpy.data.actions):
        bpy.data.actions.remove(action)


def remove_objects(objects: list[bpy.types.Object]) -> None:
    for obj in objects:
        if obj.name in bpy.data.objects:
            bpy.data.objects.remove(obj, do_unlink=True)


def source_height(armature: bpy.types.Object) -> float:
    min_z = math.inf
    max_z = -math.inf
    for bone in armature.data.bones:
        min_z = min(min_z, bone.head_local.z, bone.tail_local.z)
        max_z = max(max_z, bone.head_local.z, bone.tail_local.z)
    return max(max_z - min_z, 0.01)


def action_range(action: bpy.types.Action) -> tuple[int, int]:
    start, end = action.frame_range
    return int(math.floor(start)), int(math.ceil(end))


def pose_bone_swing(armature: bpy.types.Object, bone_name: str) -> Quaternion:
    data_bone = armature.data.bones.get(bone_name)
    pose_bone = armature.pose.bones.get(bone_name)
    if not data_bone or not pose_bone:
        return Quaternion((1, 0, 0, 0))

    rest = data_bone.tail_local - data_bone.head_local
    current = pose_bone.tail - pose_bone.head
    if rest.length < 1e-5 or current.length < 1e-5:
        return Quaternion((1, 0, 0, 0))
    return rest.normalized().rotation_difference(current.normalized())


def scaled_quaternion(quaternion: Quaternion, strength: float) -> Quaternion:
    identity = Quaternion((1, 0, 0, 0))
    return identity.slerp(quaternion, max(0.0, min(1.0, strength)))


def clear_toy_pose(armature: bpy.types.Object) -> None:
    for pose_bone in armature.pose.bones:
        pose_bone.rotation_mode = "QUATERNION"
        pose_bone.location = (0, 0, 0)
        pose_bone.rotation_quaternion = (1, 0, 0, 0)
        pose_bone.scale = (1, 1, 1)


def retarget_mixamo_action(
    toy_armature: bpy.types.Object,
    source_armature: bpy.types.Object,
    motion_name: str,
) -> bpy.types.Action:
    source_action = source_armature.animation_data.action if source_armature.animation_data else None
    if source_action is None:
        raise RuntimeError("Mixamo FBX has no armature action")

    frame_start, frame_end = action_range(source_action)
    toy_height = max((bbox_for(mesh_objects([*toy_armature.children_recursive]))[1] - bbox_for(mesh_objects([*toy_armature.children_recursive]))[0]).z, 1.0)
    scale = toy_height / source_height(source_armature)
    hips = source_armature.pose.bones.get("mixamorig:Hips")
    bpy.context.scene.frame_set(frame_start)
    bpy.context.view_layer.update()
    hips_start = hips.location.copy() if hips else Vector((0, 0, 0))

    toy_armature.animation_data_clear()
    toy_armature.animation_data_create()
    action = bpy.data.actions.new(motion_name)
    toy_armature.animation_data.action = action
    bpy.context.scene.frame_start = frame_start
    bpy.context.scene.frame_end = frame_end

    for frame in range(frame_start, frame_end + 1):
        bpy.context.scene.frame_set(frame)
        bpy.context.view_layer.update()
        clear_toy_pose(toy_armature)

        root = toy_armature.pose.bones.get("Root")
        if root and hips:
            delta = hips.location - hips_start
            root.location = (
                delta.x * scale * 0.08,
                delta.y * scale * 0.08,
                delta.z * scale * 0.22,
            )
            root.keyframe_insert("location", frame=frame)

        for toy_name, mixamo_name in MIXAMO_TO_TOYBOX.items():
            toy_bone = toy_armature.pose.bones.get(toy_name)
            if not toy_bone:
                continue
            swing = pose_bone_swing(source_armature, mixamo_name)
            toy_bone.rotation_quaternion = scaled_quaternion(swing, MOTION_STRENGTH.get(toy_name, 0.6))
            toy_bone.keyframe_insert("rotation_quaternion", frame=frame)

    bpy.context.scene.frame_set((frame_start + frame_end) // 2)
    return action


def set_animation_range() -> None:
    frame_start = 1
    frame_end = 72
    for action in bpy.data.actions:
        start, end = action.frame_range
        frame_start = min(frame_start, int(start))
        frame_end = max(frame_end, int(end))
    bpy.context.scene.frame_start = frame_start
    bpy.context.scene.frame_end = frame_end
    bpy.context.scene.frame_set(max(frame_start, min(frame_end, (frame_start + frame_end) // 2)))


def render_png(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.context.scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)


def export_glb(path: Path, objects: list[bpy.types.Object]) -> None:
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
        export_animations=True,
        export_frame_range=True,
        export_extras=True,
    )


def process_fbx(slug: str, path: Path) -> None:
    clear_scene()
    setup_render_scene(slug)
    base_path = RIGGED_BASE_ROOT / f"{slug}-base-rigged.glb"
    if not base_path.exists():
        raise FileNotFoundError(base_path)

    base_objects = imported_glb_objects(base_path)
    toy_armature = armature_object(base_objects)
    remove_actions()
    toy_armature.animation_data_clear()

    imported = imported_objects(path)
    if not imported:
        raise RuntimeError(f"No objects imported from {path}")
    source_armature = armature_object(imported)
    clean_materials(base_objects)

    motion_slug = slugify(path.stem)
    out_path = OUTPUT_ROOT / slug / f"{slug}-mixamo-{motion_slug}.glb"
    preview_path = PREVIEW_ROOT / f"{slug}-mixamo-{motion_slug}.png"
    retargeted_action = retarget_mixamo_action(toy_armature, source_armature, titleize(path.stem))
    remove_objects(imported)
    for action in list(bpy.data.actions):
        if action != retargeted_action:
            bpy.data.actions.remove(action)

    render_png(preview_path)
    export_glb(out_path, base_objects)
    print(f"{slug}: converted {path.name} -> {out_path.relative_to(ROOT)}")


def process_motion_pack(slug: str, paths: list[Path]) -> None:
    if not paths:
        return

    clear_scene()
    setup_render_scene(slug)
    base_path = RIGGED_BASE_ROOT / f"{slug}-base-rigged.glb"
    if not base_path.exists():
        raise FileNotFoundError(base_path)

    base_objects = imported_glb_objects(base_path)
    toy_armature = armature_object(base_objects)
    clean_materials(base_objects)
    source_actions: list[bpy.types.Action] = []

    for path in paths:
        before_actions = set(bpy.data.actions)
        imported = imported_objects(path)
        if not imported:
            raise RuntimeError(f"No objects imported from {path}")
        source_armature = armature_object(imported)
        source_action = source_armature.animation_data.action if source_armature.animation_data else None
        retarget_mixamo_action(toy_armature, source_armature, titleize(path.stem))
        if source_action and source_action not in before_actions:
            source_actions.append(source_action)
        remove_objects(imported)

    for action in source_actions:
        if action.name in bpy.data.actions:
            bpy.data.actions.remove(action)

    set_animation_range()
    out_path = OUTPUT_ROOT / slug / f"{slug}-mixamo-motion-pack.glb"
    preview_path = PREVIEW_ROOT / f"{slug}-mixamo-motion-pack.png"
    render_png(preview_path)
    export_glb(out_path, base_objects)
    print(f"{slug}: packed {len(paths)} Mixamo motions -> {out_path.relative_to(ROOT)}")


def iter_inputs() -> list[tuple[str, Path]]:
    items: list[tuple[str, Path]] = []
    for slug in CHARACTER_SLUGS:
        folder = INPUT_ROOT / slug
        if folder.exists():
            items.extend((slug, path) for path in sorted(folder.glob("*.fbx")))

    for path in sorted(INPUT_ROOT.glob("*.fbx")):
        name = path.stem.lower()
        slug = next((candidate for candidate in CHARACTER_SLUGS if candidate in name), "")
        if slug:
            items.append((slug, path))
    return items


def main() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    PREVIEW_ROOT.mkdir(parents=True, exist_ok=True)
    items = iter_inputs()
    if not items:
        print(f"No Mixamo FBX files found in {INPUT_ROOT}")
        return
    for slug, path in items:
        process_fbx(slug, path)
    by_slug: dict[str, list[Path]] = {}
    for slug, path in items:
        by_slug.setdefault(slug, []).append(path)
    for slug, paths in sorted(by_slug.items()):
        process_motion_pack(slug, paths)


if __name__ == "__main__":
    main()
