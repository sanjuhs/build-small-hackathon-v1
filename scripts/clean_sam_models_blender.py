"""Clean fal/SAM GLB extractions and render brighter inspection previews.

Run from the project root:

    blender --background --python scripts/clean_sam_models_blender.py

Outputs:
    assets/generated/sam-cleaned/*-sam-cleaned.glb
    assets/generated/previews/*-sam-cleaned.png
"""

from __future__ import annotations

import math
import re
from pathlib import Path

import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "potential-char-images" / "extracted-from-sam"
OUT_DIR = ROOT / "assets" / "generated"
CLEAN_DIR = OUT_DIR / "sam-cleaned"
RIGGED_DIR = OUT_DIR / "sam-standing-rigged"
PREVIEW_DIR = OUT_DIR / "previews"

KNOWN_SLUGS = ("squeaky", "electraica", "fire-boy", "shark-girl")


def clear_scene() -> None:
    bpy.ops.object.mode_set(mode="OBJECT") if bpy.ops.object.mode_set.poll() else None
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def infer_slug(path: Path, index: int) -> str:
    name = path.stem.lower()
    candidates = {
        "squeaky": "squeaky",
        "electraica": "electraica",
        "fire": "fire-boy",
        "shark": "shark-girl",
    }
    for needle, slug in candidates.items():
        if needle in name:
            return slug
    if "combined_scene" in name and index == 1:
        return "fire-boy"
    cleaned = re.sub(r"[^a-z0-9]+", "-", name).strip("-")
    return cleaned or f"sam-model-{index}"


def collect_raw_glbs() -> list[tuple[str, Path]]:
    selected: dict[str, Path] = {}
    for slug in KNOWN_SLUGS:
        named = RAW_DIR / f"{slug}-sam.glb"
        if named.exists():
            selected[slug] = named

    for index, path in enumerate(sorted(RAW_DIR.glob("*.glb")), start=1):
        slug = infer_slug(path, index)
        if slug in selected:
            continue
        if path.name.startswith("combined_scene") and "fire-boy" in selected:
            continue
        selected[slug] = path

    order = {slug: index for index, slug in enumerate(KNOWN_SLUGS)}
    return sorted(selected.items(), key=lambda item: (order.get(item[0], 99), item[0]))


def material(name: str, color: tuple[float, float, float, float], roughness: float = 0.86) -> bpy.types.Material:
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
    world.color = (1.0, 0.97, 0.90)
    bpy.context.scene.render.resolution_x = 1200
    bpy.context.scene.render.resolution_y = 1200
    bpy.context.scene.eevee.taa_render_samples = 96
    try:
        bpy.context.scene.render.engine = "BLENDER_EEVEE_NEXT"
    except TypeError:
        bpy.context.scene.render.engine = "BLENDER_EEVEE"

    floor_mat = material(f"{slug}_sam_cleanup_floor", (0.98, 0.93, 0.82, 1), 0.88)
    bpy.ops.mesh.primitive_cylinder_add(vertices=96, radius=1.75, depth=0.05, location=(0, 0.16, -0.30))
    floor = bpy.context.object
    floor.name = f"{slug}_sam_cleanup_plinth"
    floor.scale.x = 1.14
    floor.scale.y = 0.90
    floor.data.materials.append(floor_mat)

    bpy.ops.object.light_add(type="AREA", location=(0.0, -3.9, 4.6))
    key = bpy.context.object
    key.name = f"{slug}_large_front_softbox"
    key.data.energy = 760
    key.data.size = 5.2

    bpy.ops.object.light_add(type="AREA", location=(-2.9, -2.4, 2.7))
    fill = bpy.context.object
    fill.name = f"{slug}_warm_face_fill"
    fill.data.energy = 250
    fill.data.size = 3.2
    fill.data.color = (1.0, 0.88, 0.72)

    bpy.ops.object.light_add(type="POINT", location=(2.5, -2.0, 2.6))
    sparkle = bpy.context.object
    sparkle.name = f"{slug}_tiny_eye_light"
    sparkle.data.energy = 95
    sparkle.data.color = (0.82, 0.96, 1.0)

    bpy.ops.object.camera_add(location=(0, -5.9, 1.42))
    camera = bpy.context.object
    camera.name = f"{slug}_sam_cleanup_camera"
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
    for obj in mesh_objects(objects):
        for corner in obj.bound_box:
            world_corner = obj.matrix_world @ Vector(corner)
            min_v.x = min(min_v.x, world_corner.x)
            min_v.y = min(min_v.y, world_corner.y)
            min_v.z = min(min_v.z, world_corner.z)
            max_v.x = max(max_v.x, world_corner.x)
            max_v.y = max(max_v.y, world_corner.y)
            max_v.z = max(max_v.z, world_corner.z)
    return min_v, max_v


def normalize(objects: list[bpy.types.Object], slug: str) -> bpy.types.Object:
    min_v, max_v = bbox_for(objects)
    center = (min_v + max_v) / 2
    size = max_v - min_v
    max_dim = max(size.x, size.y, size.z) or 1.0
    scale = 2.35 / max_dim

    root = bpy.data.objects.new(f"{slug}_sam_cleanup_root", None)
    bpy.context.collection.objects.link(root)
    for obj in top_level_objects(objects):
        world = obj.matrix_world.copy()
        obj.parent = root
        obj.matrix_world = world
    root.scale = (scale, scale, scale)
    root.location = (-center.x * scale, -center.y * scale, -min_v.z * scale)
    return root


def bake_normalization(root: bpy.types.Object, objects: list[bpy.types.Object]) -> None:
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


def clean_meshes(objects: list[bpy.types.Object]) -> None:
    for obj in mesh_objects(objects):
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.ops.object.shade_smooth()
        obj.select_set(False)
        obj.data.validate(clean_customdata=False)
        obj.data.update()
        for poly in obj.data.polygons:
            poly.use_smooth = True

        normal = obj.modifiers.new("sam_cleanup_weighted_normals", "WEIGHTED_NORMAL")
        normal.keep_sharp = True
        normal.weight = 50

        for mat in obj.data.materials:
            if not mat:
                continue
            mat.use_nodes = True
            mat.diffuse_color = tuple(max(channel, 0.08) for channel in mat.diffuse_color)
            bsdf = mat.node_tree.nodes.get("Principled BSDF")
            if bsdf:
                if "Roughness" in bsdf.inputs:
                    bsdf.inputs["Roughness"].default_value = 0.78
                if "Metallic" in bsdf.inputs:
                    bsdf.inputs["Metallic"].default_value = 0


def render_png(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.context.scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)


def export_cleaned(slug: str, objects: list[bpy.types.Object]) -> Path:
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    output = CLEAN_DIR / f"{slug}-sam-cleaned.glb"
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = mesh_objects(objects)[0]
    bpy.ops.export_scene.gltf(
        filepath=str(output),
        export_format="GLB",
        use_selection=True,
        export_apply=True,
        export_animations=False,
    )
    return output


def create_standing_armature(slug: str, objects: list[bpy.types.Object]) -> tuple[bpy.types.Object, list[tuple[str, Vector, Vector]]]:
    min_v, max_v = bbox_for(objects)
    size = max_v - min_v
    height = max(size.z, 1.0)
    width = max(size.x, 1.0)
    depth = max(size.y, 0.55)
    center_x = (min_v.x + max_v.x) / 2
    center_y = (min_v.y + max_v.y) / 2
    z0 = min_v.z

    def p(x: float, y: float, z: float) -> Vector:
        return Vector((center_x + x * width, center_y + y * depth, z0 + z * height))

    bones = [
        ("Root", p(0, 0, 0.02), p(0, 0, 0.20), None),
        ("Spine", p(0, 0, 0.20), p(0, 0, 0.58), "Root"),
        ("Head", p(0, 0, 0.58), p(0, 0, 0.92), "Spine"),
        ("Arm.L", p(-0.20, -0.03, 0.55), p(-0.48, -0.16, 0.34), "Spine"),
        ("Arm.R", p(0.20, -0.03, 0.55), p(0.48, -0.16, 0.34), "Spine"),
        ("Leg.L", p(-0.16, 0.00, 0.22), p(-0.27, -0.06, 0.03), "Root"),
        ("Leg.R", p(0.16, 0.00, 0.22), p(0.27, -0.06, 0.03), "Root"),
        ("Backpack", p(-0.10, 0.18, 0.54), p(-0.34, 0.30, 0.34), "Spine"),
    ]

    arm_data = bpy.data.armatures.new(f"{slug}_SAM_Standing_Rig")
    arm = bpy.data.objects.new(f"{slug}_SAM_Standing_Rig", arm_data)
    bpy.context.collection.objects.link(arm)
    bpy.context.view_layer.objects.active = arm
    arm.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    edit_bones = {}
    for name, head, tail, parent in bones:
        bone = arm_data.edit_bones.new(name)
        bone.head = head
        bone.tail = tail
        bone.roll = 0
        if parent:
            bone.parent = edit_bones[parent]
            bone.use_connect = False
        edit_bones[name] = bone
    bpy.ops.object.mode_set(mode="POSE")
    for pbone in arm.pose.bones:
        pbone.rotation_mode = "XYZ"
    bpy.ops.object.mode_set(mode="OBJECT")
    arm.show_in_front = True
    arm.data.display_type = "STICK"
    return arm, [(name, head, tail) for name, head, tail, _ in bones]


def clear_vertex_groups(obj: bpy.types.Object) -> None:
    while obj.vertex_groups:
        obj.vertex_groups.remove(obj.vertex_groups[0])


def assign_skin_weights(objects: list[bpy.types.Object], armature: bpy.types.Object) -> None:
    min_v, max_v = bbox_for(objects)
    size = max_v - min_v
    height = max(size.z, 1.0)
    width = max(size.x, 1.0)
    depth = max(size.y, 0.55)
    cx = (min_v.x + max_v.x) / 2
    cy = (min_v.y + max_v.y) / 2
    z0 = min_v.z

    bone_names = [bone.name for bone in armature.data.bones]
    for obj in mesh_objects(objects):
        clear_vertex_groups(obj)
        groups = {name: obj.vertex_groups.new(name=name) for name in bone_names}
        for vertex in obj.data.vertices:
            world = obj.matrix_world @ vertex.co
            xf = (world.x - cx) / width
            yf = (world.y - cy) / depth
            zf = (world.z - z0) / height

            if zf > 0.62:
                target = "Head"
            elif zf < 0.20:
                target = "Leg.L" if xf < 0 else "Leg.R"
            elif abs(xf) > 0.25 and zf < 0.62:
                target = "Arm.L" if xf < 0 else "Arm.R"
            elif yf > 0.22 and zf > 0.28:
                target = "Backpack"
            elif zf < 0.30:
                target = "Root"
            else:
                target = "Spine"
            groups[target].add([vertex.index], 1.0, "ADD")

        mod = obj.modifiers.new("sam_standing_armature", "ARMATURE")
        mod.object = armature
        obj.parent = armature


def animate_standing_idle(armature: bpy.types.Object) -> None:
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode="POSE")
    poses = [
        (1, {"Root": (0, 0, 0), "Head": (0, 0, -0.035), "Arm.L": (0.03, 0.0, 0.055), "Arm.R": (-0.03, 0.0, -0.055)}),
        (24, {"Root": (0, 0, 0.035), "Head": (0.025, 0, 0.060), "Arm.L": (0.07, 0.0, -0.10), "Arm.R": (-0.07, 0.0, 0.10)}),
        (48, {"Root": (0, 0, 0), "Head": (0, 0, -0.035), "Arm.L": (0.03, 0.0, 0.055), "Arm.R": (-0.03, 0.0, -0.055)}),
    ]
    for frame, pose in poses:
        bpy.context.scene.frame_set(frame)
        for bone_name, rot in pose.items():
            pbone = armature.pose.bones.get(bone_name)
            if not pbone:
                continue
            if bone_name == "Root":
                pbone.location = rot
                pbone.keyframe_insert("location", frame=frame)
            else:
                pbone.rotation_euler = rot
                pbone.keyframe_insert("rotation_euler", frame=frame)
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end = 48
    bpy.context.scene.frame_set(24)


def export_rigged(slug: str, objects: list[bpy.types.Object], armature: bpy.types.Object) -> Path:
    RIGGED_DIR.mkdir(parents=True, exist_ok=True)
    output = RIGGED_DIR / f"{slug}-sam-standing-rigged.glb"
    bpy.ops.object.select_all(action="DESELECT")
    armature.select_set(True)
    for obj in mesh_objects(objects):
        obj.select_set(True)
    bpy.context.view_layer.objects.active = armature
    bpy.ops.export_scene.gltf(
        filepath=str(output),
        export_format="GLB",
        use_selection=True,
        export_animations=True,
        export_frame_range=True,
    )
    return output


def add_rig_preview_visuals(slug: str, bones: list[tuple[str, Vector, Vector]]) -> list[bpy.types.Object]:
    rig_mat = material(f"{slug}_sam_rig_cyan", (0.08, 0.75, 0.95, 1), 0.38)
    joint_mat = material(f"{slug}_sam_rig_gold", (1.0, 0.78, 0.20, 1), 0.45)
    visuals: list[bpy.types.Object] = []
    for name, head, tail in bones:
        head_v = Vector((head.x, head.y - 0.85, head.z))
        tail_v = Vector((tail.x, tail.y - 0.85, tail.z))
        mid = (head_v + tail_v) / 2
        length = (tail_v - head_v).length
        bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.010, depth=length, location=mid)
        line = bpy.context.object
        line.name = f"{slug}_SAM_RigLine_{name}"
        line.rotation_euler = (tail_v - head_v).to_track_quat("Z", "Y").to_euler()
        line.data.materials.append(rig_mat)
        bpy.ops.object.shade_smooth()
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, location=head_v)
        joint = bpy.context.object
        joint.name = f"{slug}_SAM_RigJoint_{name}"
        joint.scale = (0.026, 0.026, 0.026)
        joint.data.materials.append(joint_mat)
        bpy.ops.object.shade_smooth()
        visuals.extend([line, joint])
    return visuals


def process(path: Path, index: int) -> None:
    slug = infer_slug(path, index)
    clear_scene()
    setup_render_scene(slug)
    imported = imported_objects(path)
    clean_meshes(imported)
    root = normalize(imported, slug)
    bake_normalization(root, imported)
    for obj in imported:
        obj["toybox_source"] = "fal-sam-3"
        obj["toybox_cleanup"] = "smooth-normals-centered-lit-upright"
    render_png(PREVIEW_DIR / f"{slug}-sam-cleaned.png")
    output = export_cleaned(slug, imported)
    print(f"Cleaned {path} -> {output}")

    armature, bones = create_standing_armature(slug, imported)
    assign_skin_weights(imported, armature)
    animate_standing_idle(armature)
    render_png(PREVIEW_DIR / f"{slug}-sam-standing-rigged.png")
    visuals = add_rig_preview_visuals(slug, bones)
    render_png(PREVIEW_DIR / f"{slug}-sam-standing-rig.png")
    for visual in visuals:
        bpy.data.objects.remove(visual, do_unlink=True)
    rigged = export_rigged(slug, imported, armature)
    print(f"Rigged {path} -> {rigged}")


def main() -> None:
    if not RAW_DIR.exists():
        print(f"No SAM extraction directory found at {RAW_DIR}")
        return
    glbs = collect_raw_glbs()
    if not glbs:
        print(f"No raw SAM GLBs found in {RAW_DIR}")
        return
    for index, (_slug, path) in enumerate(glbs, start=1):
        process(path, index)


if __name__ == "__main__":
    main()
