"""Generate rigged Tiny Toybox character GLBs and Blender preview renders.

Run from the project root:

    /Applications/Blender.app/Contents/MacOS/Blender --background --python scripts/generate_character_models_blender.py

Outputs:
    assets/generated/rigged/*.glb
    assets/generated/previews/*-rig.png
    assets/generated/previews/*-objects.png
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "assets" / "generated"
RIGGED_DIR = OUT_DIR / "rigged"
PREVIEW_DIR = OUT_DIR / "previews"


@dataclass
class CharacterScene:
    slug: str
    prefix: str
    export_objects: list[bpy.types.Object] = field(default_factory=list)
    rig_visuals: list[bpy.types.Object] = field(default_factory=list)
    bone_groups: dict[str, list[bpy.types.Object]] = field(default_factory=dict)
    armature: bpy.types.Object | None = None

    def add(self, obj: bpy.types.Object, bone: str | None = None, export: bool = True) -> bpy.types.Object:
        if export:
            self.export_objects.append(obj)
        if bone:
            self.bone_groups.setdefault(bone, []).append(obj)
        return obj

    def extend(self, objs: list[bpy.types.Object], bone: str | None = None) -> list[bpy.types.Object]:
        for obj in objs:
            self.add(obj, bone)
        return objs


def material(name: str, color: tuple[float, float, float, float], roughness: float = 0.86, emission: float = 0.0) -> bpy.types.Material:
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Roughness"].default_value = roughness
    if emission:
        bsdf.inputs["Emission Color"].default_value = color
        bsdf.inputs["Emission Strength"].default_value = emission
    return mat


def clear_scene() -> None:
    bpy.ops.object.mode_set(mode="OBJECT") if bpy.ops.object.mode_set.poll() else None
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def smooth(obj: bpy.types.Object) -> bpy.types.Object:
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    try:
        bpy.ops.object.shade_smooth()
    finally:
        obj.select_set(False)
    return obj


def add_sphere(name: str, loc, scale, mat: bpy.types.Material, segments: int = 56) -> bpy.types.Object:
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=max(12, segments // 2), location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    obj.data.materials.append(mat)
    obj["toybox_part"] = name
    return smooth(obj)


def add_cube(name: str, loc, scale, mat: bpy.types.Material, rot=(0, 0, 0), bevel: float = 0.025) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=rot)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    obj.data.materials.append(mat)
    obj["toybox_part"] = name
    if bevel:
        mod = obj.modifiers.new("soft_plush_bevel", "BEVEL")
        mod.width = bevel
        mod.segments = 5
        obj.modifiers.new("soft_weighted_normals", "WEIGHTED_NORMAL")
    return obj


def add_cylinder(name: str, loc, radius: float, depth: float, mat: bpy.types.Material, rot=(0, 0, 0), vertices: int = 48) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=loc, rotation=rot)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(mat)
    obj["toybox_part"] = name
    return smooth(obj)


def add_cone(name: str, loc, radius: float, depth: float, mat: bpy.types.Material, rot=(0, 0, 0), vertices: int = 7) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cone_add(vertices=vertices, radius1=radius, radius2=0.02, depth=depth, location=loc, rotation=rot)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(mat)
    obj["toybox_part"] = name
    return smooth(obj)


def add_torus(name: str, loc, major: float, minor: float, mat: bpy.types.Material, rot=(0, 0, 0)) -> bpy.types.Object:
    bpy.ops.mesh.primitive_torus_add(major_segments=72, minor_segments=12, major_radius=major, minor_radius=minor, location=loc, rotation=rot)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(mat)
    obj["toybox_part"] = name
    return smooth(obj)


def add_curve(name: str, points: list[tuple[float, float, float]], mat: bpy.types.Material, bevel: float = 0.012) -> bpy.types.Object:
    curve = bpy.data.curves.new(name, "CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 3
    curve.bevel_depth = bevel
    curve.bevel_resolution = 4
    spline = curve.splines.new("POLY")
    spline.points.add(len(points) - 1)
    for point, co in zip(spline.points, points):
        point.co = (co[0], co[1], co[2], 1)
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mat)
    obj["toybox_part"] = name
    return obj


def add_arc(name: str, center, rx: float, rz: float, start: float, end: float, mat: bpy.types.Material, bevel: float = 0.014, steps: int = 18) -> bpy.types.Object:
    points = []
    for i in range(steps + 1):
        angle = start + (end - start) * i / steps
        points.append((center[0] + math.cos(angle) * rx, center[1], center[2] + math.sin(angle) * rz))
    return add_curve(name, points, mat, bevel)


def add_text(name: str, text: str, loc, size: float, mat: bpy.types.Material) -> bpy.types.Object:
    bpy.ops.object.text_add(location=loc, rotation=(math.radians(72), 0, 0))
    obj = bpy.context.object
    obj.name = name
    obj.data.body = text
    obj.data.align_x = "CENTER"
    obj.data.align_y = "CENTER"
    obj.data.size = size
    obj.data.materials.append(mat)
    return obj


def look_at(obj: bpy.types.Object, target: tuple[float, float, float]) -> None:
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def setup_render_scene(title: str, ortho_scale: float = 4.1, camera_loc=(0, -6.5, 2.2), target=(0, 0, 1.55)) -> None:
    world = bpy.context.scene.world or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.color = (1.0, 0.96, 0.88)
    bpy.context.scene.render.resolution_x = 1200
    bpy.context.scene.render.resolution_y = 1200
    bpy.context.scene.eevee.taa_render_samples = 64
    try:
        bpy.context.scene.render.engine = "BLENDER_EEVEE_NEXT"
    except TypeError:
        bpy.context.scene.render.engine = "BLENDER_EEVEE"

    floor_mat = material(f"{title}_warm_floor", (0.98, 0.91, 0.78, 1), 0.9)
    floor = add_cylinder(f"{title}_display_plinth", (0, 0, -0.05), 1.95, 0.08, floor_mat, vertices=96)
    floor.scale.x = 1.2
    floor.scale.y = 0.9

    bpy.ops.object.light_add(type="AREA", location=(0, -4.6, 5.4))
    key = bpy.context.object
    key.name = f"{title}_large_softbox"
    key.data.energy = 520
    key.data.size = 4.8

    bpy.ops.object.light_add(type="POINT", location=(-3.0, -2.2, 2.8))
    fill = bpy.context.object
    fill.name = f"{title}_cool_fill"
    fill.data.color = (0.62, 0.86, 0.92)
    fill.data.energy = 80

    bpy.ops.object.camera_add(location=camera_loc)
    camera = bpy.context.object
    camera.name = f"{title}_Camera"
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = ortho_scale
    look_at(camera, target)
    bpy.context.scene.camera = camera


def render_png(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.context.scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)


def base_materials(slug: str) -> dict[str, bpy.types.Material]:
    palettes = {
        "squeaky": {
            "body": (0.48, 0.66, 0.70, 1),
            "belly": (0.78, 0.88, 0.88, 1),
            "accent": (0.04, 0.18, 0.20, 1),
            "cheek": (1.0, 0.57, 0.38, 1),
            "cream": (0.96, 0.88, 0.72, 1),
            "wood": (0.58, 0.36, 0.18, 1),
        },
        "electraica": {
            "body": (1.0, 0.74, 0.12, 1),
            "belly": (1.0, 0.92, 0.72, 1),
            "accent": (0.52, 0.45, 0.32, 1),
            "cheek": (1.0, 0.50, 0.35, 1),
            "cream": (1.0, 0.96, 0.78, 1),
            "wood": (0.72, 0.43, 0.18, 1),
        },
        "fire_boy": {
            "body": (1.0, 0.25, 0.11, 1),
            "belly": (1.0, 0.90, 0.74, 1),
            "accent": (0.04, 0.035, 0.03, 1),
            "cheek": (1.0, 0.58, 0.42, 1),
            "cream": (1.0, 0.93, 0.82, 1),
            "wood": (0.92, 0.66, 0.28, 1),
        },
        "shark_girl": {
            "body": (0.52, 0.80, 0.87, 1),
            "belly": (1.0, 0.92, 0.78, 1),
            "accent": (0.95, 0.70, 0.44, 1),
            "cheek": (1.0, 0.58, 0.44, 1),
            "cream": (1.0, 0.93, 0.80, 1),
            "wood": (0.72, 0.42, 0.18, 1),
        },
    }[slug]
    mats = {name: material(f"{slug}_{name}", color) for name, color in palettes.items()}
    mats["ink"] = material(f"{slug}_embroidered_ink", (0.08, 0.06, 0.045, 1), 0.9)
    mats["eye_glint"] = material(f"{slug}_eye_glint", (1.0, 0.98, 0.88, 1), 0.5, 0.06)
    mats["seam"] = material(f"{slug}_raised_plush_seams", (0.34, 0.42, 0.42, 1), 0.94)
    mats["white"] = material(f"{slug}_shirt_white", (0.98, 0.97, 0.92, 1), 0.84)
    mats["metal"] = material(f"{slug}_soft_metal", (0.58, 0.52, 0.42, 1), 0.56)
    mats["glow"] = material(f"{slug}_warm_glow", (1.0, 0.88, 0.28, 1), 0.35, 0.7)
    mats["orange_glow"] = material(f"{slug}_orange_glow", (1.0, 0.42, 0.12, 1), 0.65, 0.32)
    return mats


def add_base_plush(scene: CharacterScene, mats: dict[str, bpy.types.Material]) -> None:
    scene.add(add_sphere(f"{scene.prefix}_Body", (0, 0, 1.00), (0.64, 0.52, 0.66), mats["body"]), "Spine")
    scene.add(add_sphere(f"{scene.prefix}_Head", (0, -0.03, 1.92), (0.86, 0.72, 0.76), mats["body"]), "Head")
    scene.add(add_sphere(f"{scene.prefix}_Belly", (0, -0.50, 0.98), (0.35, 0.064, 0.25), mats["belly"]), "Spine")
    scene.add(add_sphere(f"{scene.prefix}_Arm_L", (-0.50, -0.26, 0.96), (0.16, 0.16, 0.22), mats["body"]), "Arm.L")
    scene.add(add_sphere(f"{scene.prefix}_Arm_R", (0.50, -0.26, 0.96), (0.16, 0.16, 0.22), mats["body"]), "Arm.R")
    scene.add(add_sphere(f"{scene.prefix}_Foot_L", (-0.29, -0.24, 0.20), (0.27, 0.22, 0.13), mats["body"]), "Leg.L")
    scene.add(add_sphere(f"{scene.prefix}_Foot_R", (0.29, -0.24, 0.20), (0.27, 0.22, 0.13), mats["body"]), "Leg.R")
    add_plush_stitches(scene, mats)


def add_plush_stitches(scene: CharacterScene, mats: dict[str, bpy.types.Material]) -> None:
    for idx, z in enumerate([0.68, 0.80, 0.92, 1.04, 1.16]):
        scene.add(add_curve(
            f"{scene.prefix}_Body_Center_Stitch_{idx}",
            [(-0.033, -0.60, z), (0.033, -0.60, z + 0.012)],
            mats["seam"],
            0.006,
        ), "Spine")
    for side, x in [("L", -0.29), ("R", 0.29)]:
        scene.add(add_arc(f"{scene.prefix}_Foot_Toe_Seam_{side}", (x, -0.41, 0.25), 0.13, 0.042, 0.12 * math.pi, 0.88 * math.pi, mats["seam"], 0.006), f"Leg.{side}")
    for side, x in [("L", -0.50), ("R", 0.50)]:
        scene.add(add_arc(f"{scene.prefix}_Paw_Seam_{side}", (x, -0.42, 0.96), 0.065, 0.040, 0.15 * math.pi, 0.85 * math.pi, mats["seam"], 0.005), f"Arm.{side}")


def add_face(scene: CharacterScene, mats: dict[str, bpy.types.Material], z: float = 2.02, wide: float = 1.0) -> None:
    face_y = -0.79
    for side, x in [("L", -0.25 * wide), ("R", 0.25 * wide)]:
        scene.add(add_sphere(f"{scene.prefix}_Chibi_Eye_{side}", (x, face_y, z + 0.12), (0.085, 0.020, 0.135), mats["ink"], 40), "Head")
        scene.add(add_sphere(f"{scene.prefix}_Eye_Glint_{side}", (x - 0.025, face_y - 0.014, z + 0.17), (0.028, 0.006, 0.040), mats["eye_glint"], 20), "Head")
        scene.add(add_arc(f"{scene.prefix}_Soft_Lash_{side}", (x, face_y - 0.004, z + 0.25), 0.09, 0.035, 0.08 * math.pi, 0.92 * math.pi, mats["ink"], 0.006), "Head")
    scene.add(add_sphere(f"{scene.prefix}_Tiny_Nose", (0, face_y - 0.018, z + 0.015), (0.045, 0.012, 0.034), mats["ink"], 24), "Head")
    scene.add(add_sphere(f"{scene.prefix}_Cheek_L", (-0.40 * wide, face_y - 0.01, z - 0.04), (0.110, 0.018, 0.068), mats["cheek"], 32), "Head")
    scene.add(add_sphere(f"{scene.prefix}_Cheek_R", (0.40 * wide, face_y - 0.01, z - 0.04), (0.110, 0.018, 0.068), mats["cheek"], 32), "Head")
    scene.add(add_arc(f"{scene.prefix}_Smile", (0, face_y - 0.02, z - 0.08), 0.145, 0.075, 1.12 * math.pi, 1.88 * math.pi, mats["ink"], 0.011), "Head")


def add_bowler(scene: CharacterScene, mats: dict[str, bpy.types.Material], loc=(0, -0.03, 2.68), scale=1.06, bone="Hat") -> list[bpy.types.Object]:
    x, y, z = loc
    return scene.extend([
        add_cylinder(f"{scene.prefix}_Bowler_Brim", (x, y, z), 0.48 * scale, 0.09 * scale, mats["accent"], vertices=80),
        add_sphere(f"{scene.prefix}_Bowler_Dome", (x, y, z + 0.16 * scale), (0.36 * scale, 0.36 * scale, 0.25 * scale), mats["accent"]),
        add_torus(f"{scene.prefix}_Bowler_Band", (x, y, z + 0.04 * scale), 0.37 * scale, 0.012 * scale, mats["ink"]),
    ], bone)


def add_book_backpack(scene: CharacterScene, mats: dict[str, bpy.types.Material], loc=(-0.67, -0.08, 1.02), scale=1.08, bone="Backpack") -> list[bpy.types.Object]:
    x, y, z = loc
    objs = [
        add_cube(f"{scene.prefix}_Book_Backpack_Case", (x, y, z), (0.25 * scale, 0.16 * scale, 0.34 * scale), mats["wood"], (0, math.radians(5), 0), 0.045),
        add_cube(f"{scene.prefix}_Book_Backpack_Strap", (x + 0.25 * scale, y - 0.28 * scale, z + 0.02 * scale), (0.035 * scale, 0.02 * scale, 0.44 * scale), mats["ink"], (math.radians(8), 0, 0), 0.01),
    ]
    colors = [mats["cream"], mats["accent"], mats["white"]]
    for i, mat in enumerate(colors):
        objs.append(add_cube(f"{scene.prefix}_Book_{i+1}", (x - 0.08 * scale + i * 0.075 * scale, y - 0.08 * scale, z + 0.08 * scale), (0.035 * scale, 0.06 * scale, 0.27 * scale), mat, (0, 0, 0), 0.012))
        objs.append(add_cube(f"{scene.prefix}_Book_Page_Line_{i+1}", (x - 0.08 * scale + i * 0.075 * scale, y - 0.145 * scale, z + 0.08 * scale), (0.003 * scale, 0.004 * scale, 0.22 * scale), mats["ink"], (0, 0, 0), 0))
    objs.append(add_cube(f"{scene.prefix}_Backpack_Book_Band", (x + 0.01 * scale, y - 0.15 * scale, z + 0.08 * scale), (0.18 * scale, 0.012 * scale, 0.035 * scale), mats["wood"], (0, 0, 0), 0.006))
    return scene.extend(objs, bone)


def add_pocket_clock(scene: CharacterScene, mats: dict[str, bpy.types.Material], loc=(0.46, -0.62, 0.98), scale=1.12, bone="Prop.R") -> list[bpy.types.Object]:
    x, y, z = loc
    objs = [
        add_cylinder(f"{scene.prefix}_Pocket_Clock_Face", (x, y, z), 0.16 * scale, 0.035 * scale, mats["cream"], (math.radians(90), 0, 0), 64),
        add_torus(f"{scene.prefix}_Pocket_Clock_Rim", (x, y - 0.02 * scale, z), 0.16 * scale, 0.018 * scale, mats["body"], (math.radians(90), 0, 0)),
        add_cube(f"{scene.prefix}_Clock_Hand_Long", (x, y - 0.046 * scale, z + 0.02 * scale), (0.009 * scale, 0.006 * scale, 0.075 * scale), mats["ink"], (math.radians(90), 0, math.radians(-32))),
        add_cube(f"{scene.prefix}_Clock_Hand_Short", (x, y - 0.05 * scale, z + 0.01 * scale), (0.008 * scale, 0.006 * scale, 0.052 * scale), mats["ink"], (math.radians(90), 0, math.radians(50))),
    ]
    for i in range(12):
        angle = i / 12 * math.tau
        objs.append(add_cube(
            f"{scene.prefix}_Clock_Tick_{i}",
            (x + math.sin(angle) * 0.12 * scale, y - 0.055 * scale, z + math.cos(angle) * 0.12 * scale),
            (0.006 * scale, 0.004 * scale, (0.022 if i % 3 == 0 else 0.014) * scale),
            mats["ink"],
            (math.radians(90), 0, -angle),
            0,
        ))
    objs.append(add_curve(f"{scene.prefix}_Pocket_Clock_Chain", [(x - 0.10 * scale, y - 0.03 * scale, z + 0.12 * scale), (x - 0.22 * scale, y - 0.02 * scale, z + 0.28 * scale), (x - 0.36 * scale, y - 0.03 * scale, z + 0.30 * scale)], mats["seam"], 0.006 * scale))
    return scene.extend(objs, bone)


def add_bulb(scene: CharacterScene, mats: dict[str, bpy.types.Material], loc=(0, -0.03, 2.68), scale=1.06, bone="Hat") -> list[bpy.types.Object]:
    x, y, z = loc
    objs = [
        add_sphere(f"{scene.prefix}_Always_On_Bulb_Glass", (x, y, z + 0.12 * scale), (0.25 * scale, 0.25 * scale, 0.31 * scale), mats["glow"]),
        add_sphere(f"{scene.prefix}_Bulb_Core", (x, y - 0.02 * scale, z + 0.11 * scale), (0.11 * scale, 0.045 * scale, 0.08 * scale), mats["white"], 32),
        add_cylinder(f"{scene.prefix}_Bulb_Screw_Base", (x, y, z - 0.19 * scale), 0.12 * scale, 0.20 * scale, mats["metal"], vertices=48),
        add_torus(f"{scene.prefix}_Bulb_Glow_Halo", (x, y, z + 0.15 * scale), 0.33 * scale, 0.011 * scale, mats["glow"], (math.radians(90), 0, 0)),
    ]
    for i in range(3):
        objs.append(add_torus(f"{scene.prefix}_Bulb_Screw_Ridge_{i}", (x, y, z - 0.26 * scale + i * 0.07 * scale), 0.12 * scale, 0.006 * scale, mats["ink"]))
    return scene.extend(objs, bone)


def add_battery_pack(scene: CharacterScene, mats: dict[str, bpy.types.Material], loc=(-0.67, -0.08, 1.00), scale=1.08, bone="Backpack") -> list[bpy.types.Object]:
    x, y, z = loc
    objs = [
        add_cube(f"{scene.prefix}_Electric_Backup_Battery", (x, y, z), (0.24 * scale, 0.13 * scale, 0.36 * scale), mats["accent"], (0, math.radians(6), 0), 0.035),
        add_cube(f"{scene.prefix}_Battery_Top_Tab", (x, y - 0.04 * scale, z + 0.40 * scale), (0.10 * scale, 0.08 * scale, 0.04 * scale), mats["metal"], (0, 0, 0), 0.012),
        add_curve(f"{scene.prefix}_Battery_Cable", [(x + 0.14 * scale, y - 0.1 * scale, z + 0.20 * scale), (x + 0.27 * scale, y - 0.18 * scale, z + 0.34 * scale), (x + 0.18 * scale, y - 0.18 * scale, z + 0.50 * scale)], mats["ink"], 0.012),
    ]
    bolt = add_curve(f"{scene.prefix}_Battery_Lightning_Mark", [
        (x - 0.04 * scale, y - 0.14 * scale, z + 0.15 * scale),
        (x + 0.05 * scale, y - 0.15 * scale, z + 0.15 * scale),
        (x - 0.02 * scale, y - 0.15 * scale, z - 0.02 * scale),
        (x + 0.07 * scale, y - 0.15 * scale, z - 0.02 * scale),
        (x - 0.06 * scale, y - 0.15 * scale, z - 0.22 * scale),
    ], mats["glow"], 0.018)
    objs.append(bolt)
    return scene.extend(objs, bone)


def add_nut(scene: CharacterScene, mats: dict[str, bpy.types.Material], loc=(-0.51, -0.58, 0.98), scale=1.14, bone="Prop.L") -> list[bpy.types.Object]:
    x, y, z = loc
    return scene.extend([
        add_cylinder(f"{scene.prefix}_Left_Hand_Hex_Nut", (x, y, z), 0.20 * scale, 0.08 * scale, mats["metal"], (math.radians(90), 0, math.radians(30)), 6),
        add_cylinder(f"{scene.prefix}_Nut_Center_Hole", (x, y - 0.045 * scale, z), 0.075 * scale, 0.012 * scale, mats["ink"], (math.radians(90), 0, 0), 32),
    ], bone)


def add_bolt(scene: CharacterScene, mats: dict[str, bpy.types.Material], loc=(0.51, -0.58, 0.98), scale=1.14, bone="Prop.R") -> list[bpy.types.Object]:
    x, y, z = loc
    objs = [
        add_cylinder(f"{scene.prefix}_Right_Hand_Bolt_Shaft", (x, y, z - 0.04 * scale), 0.047 * scale, 0.40 * scale, mats["metal"], (0, 0, 0), 32),
        add_cylinder(f"{scene.prefix}_Right_Hand_Bolt_Head", (x, y, z + 0.18 * scale), 0.12 * scale, 0.08 * scale, mats["metal"], (0, 0, 0), 6),
    ]
    for i in range(4):
        objs.append(add_torus(f"{scene.prefix}_Bolt_Thread_{i}", (x, y, z - 0.18 * scale + i * 0.08 * scale), 0.046 * scale, 0.006 * scale, mats["ink"]))
    return scene.extend(objs, bone)


def add_tux(scene: CharacterScene, mats: dict[str, bpy.types.Material], z=0.98) -> list[bpy.types.Object]:
    return scene.extend([
        add_cube(f"{scene.prefix}_Tux_Left_Panel", (-0.17, -0.575, z), (0.16, 0.036, 0.29), mats["accent"], (0, 0, math.radians(-10)), 0.016),
        add_cube(f"{scene.prefix}_Tux_Right_Panel", (0.17, -0.575, z), (0.16, 0.036, 0.29), mats["accent"], (0, 0, math.radians(10)), 0.016),
        add_cube(f"{scene.prefix}_White_Shirt", (0, -0.605, z + 0.04), (0.15, 0.022, 0.28), mats["white"], (0, 0, 0), 0.012),
        add_cube(f"{scene.prefix}_Black_Tie", (0, -0.632, z + 0.02), (0.035, 0.014, 0.16), mats["ink"], (0, 0, 0), 0.006),
        add_cube(f"{scene.prefix}_Tux_Left_Lapel", (-0.075, -0.648, z + 0.17), (0.060, 0.012, 0.13), mats["accent"], (0, 0, math.radians(-28)), 0.006),
        add_cube(f"{scene.prefix}_Tux_Right_Lapel", (0.075, -0.648, z + 0.17), (0.060, 0.012, 0.13), mats["accent"], (0, 0, math.radians(28)), 0.006),
        add_sphere(f"{scene.prefix}_Tux_Button_1", (0.065, -0.658, z - 0.02), (0.020, 0.005, 0.020), mats["ink"], 20),
        add_sphere(f"{scene.prefix}_Tux_Button_2", (0.065, -0.658, z - 0.12), (0.018, 0.005, 0.018), mats["ink"], 20),
    ], "Spine")


def add_extinguisher(scene: CharacterScene, mats: dict[str, bpy.types.Material], loc=(-0.66, -0.08, 1.00), scale=1.04, bone="Backpack") -> list[bpy.types.Object]:
    x, y, z = loc
    objs = [
        add_cylinder(f"{scene.prefix}_Fire_Extinguisher_Backup", (x, y, z), 0.19 * scale, 0.72 * scale, mats["body"], (math.radians(90), 0, 0), 48),
        add_cylinder(f"{scene.prefix}_Extinguisher_Cap", (x, y - 0.37 * scale, z + 0.02 * scale), 0.11 * scale, 0.08 * scale, mats["ink"], (math.radians(90), 0, 0), 32),
        add_cube(f"{scene.prefix}_Extinguisher_Handle", (x, y - 0.43 * scale, z + 0.16 * scale), (0.20 * scale, 0.035 * scale, 0.055 * scale), mats["ink"], (0, 0, 0), 0.008),
        add_cube(f"{scene.prefix}_Extinguisher_Label", (x, y - 0.18 * scale, z), (0.13 * scale, 0.012 * scale, 0.18 * scale), mats["white"], (0, 0, 0), 0.006),
        add_curve(f"{scene.prefix}_Extinguisher_Hose", [(x + 0.12 * scale, y - 0.32 * scale, z + 0.10 * scale), (x + 0.48 * scale, y - 0.46 * scale, z + 0.28 * scale), (0.34 * scale, -0.70 * scale, 1.18 * scale)], mats["ink"], 0.015),
    ]
    return scene.extend(objs, bone)


def add_flute(scene: CharacterScene, mats: dict[str, bpy.types.Material], loc=(0.42, -0.61, 0.96), scale=0.98, bone="Prop.R") -> list[bpy.types.Object]:
    x, y, z = loc
    objs = [
        add_cylinder(f"{scene.prefix}_Flute", (x, y, z), 0.045 * scale, 0.78 * scale, mats["wood"], (math.radians(90), math.radians(18), math.radians(43)), 32),
    ]
    for i in range(5):
        objs.append(add_sphere(f"{scene.prefix}_Flute_Hole_{i}", (x - 0.17 * scale + i * 0.08 * scale, y - 0.04 * scale, z + 0.06 * scale), (0.018 * scale, 0.006 * scale, 0.018 * scale), mats["ink"], 20))
    return scene.extend(objs, bone)


def add_cream_butler_tie(scene: CharacterScene, mats: dict[str, bpy.types.Material], loc=(0, -0.58, 1.00), scale=1.12, bone="Spine") -> list[bpy.types.Object]:
    x, y, z = loc
    return scene.extend([
        add_sphere(f"{scene.prefix}_Cream_Tie_Knot", (x, y, z + 0.08 * scale), (0.07 * scale, 0.025 * scale, 0.06 * scale), mats["cream"], 32),
        add_cube(f"{scene.prefix}_Cream_Butler_Tie", (x, y, z - 0.08 * scale), (0.065 * scale, 0.016 * scale, 0.23 * scale), mats["cream"], (0, 0, 0), 0.012),
        add_sphere(f"{scene.prefix}_Tie_Flare_L", (x - 0.13 * scale, y, z + 0.07 * scale), (0.15 * scale, 0.024 * scale, 0.07 * scale), mats["cream"], 32),
        add_sphere(f"{scene.prefix}_Tie_Flare_R", (x + 0.13 * scale, y, z + 0.07 * scale), (0.15 * scale, 0.024 * scale, 0.07 * scale), mats["cream"], 32),
    ], bone)


def add_guitar(scene: CharacterScene, mats: dict[str, bpy.types.Material], loc=(0.56, -0.62, 0.92), scale=0.92, bone="Prop.R") -> list[bpy.types.Object]:
    x, y, z = loc
    objs = [
        add_sphere(f"{scene.prefix}_Guitar_Body_Lower", (x, y, z - 0.04 * scale), (0.21 * scale, 0.04 * scale, 0.24 * scale), mats["wood"], 48),
        add_sphere(f"{scene.prefix}_Guitar_Body_Upper", (x, y, z + 0.16 * scale), (0.15 * scale, 0.035 * scale, 0.16 * scale), mats["wood"], 40),
        add_cylinder(f"{scene.prefix}_Guitar_Sound_Hole", (x, y - 0.045 * scale, z + 0.05 * scale), 0.055 * scale, 0.012 * scale, mats["ink"], (math.radians(90), 0, 0), 32),
        add_cube(f"{scene.prefix}_Guitar_Neck", (x + 0.10 * scale, y, z + 0.47 * scale), (0.045 * scale, 0.018 * scale, 0.42 * scale), mats["wood"], (math.radians(9), 0, math.radians(-18)), 0.008),
        add_cube(f"{scene.prefix}_Guitar_Headstock", (x + 0.20 * scale, y, z + 0.82 * scale), (0.14 * scale, 0.024 * scale, 0.12 * scale), mats["wood"], (math.radians(9), 0, math.radians(-18)), 0.01),
        add_cube(f"{scene.prefix}_Guitar_Bridge", (x, y - 0.055 * scale, z - 0.17 * scale), (0.15 * scale, 0.014 * scale, 0.024 * scale), mats["ink"], (0, 0, 0), 0.002),
    ]
    for i in range(5):
        objs.append(add_cube(f"{scene.prefix}_Guitar_Fret_{i}", (x + 0.07 * scale + i * 0.028 * scale, y - 0.078 * scale, z + 0.31 * scale + i * 0.08 * scale), (0.095 * scale, 0.006 * scale, 0.006 * scale), mats["ink"], (math.radians(9), 0, math.radians(-18)), 0))
    for i, side in enumerate([-1, 1]):
        objs.append(add_sphere(f"{scene.prefix}_Guitar_Tuning_Peg_{i}", (x + 0.20 * scale + side * 0.08 * scale, y - 0.04 * scale, z + 0.86 * scale), (0.027 * scale, 0.012 * scale, 0.027 * scale), mats["ink"], 16))
    for i in range(4):
        offset = -0.045 * scale + i * 0.03 * scale
        objs.append(add_curve(f"{scene.prefix}_Guitar_String_{i}", [
            (x + offset, y - 0.075 * scale, z - 0.17 * scale),
            (x + 0.06 * scale + offset * 0.4, y - 0.078 * scale, z + 0.42 * scale),
            (x + 0.16 * scale + offset * 0.25, y - 0.078 * scale, z + 0.80 * scale),
        ], mats["ink"], 0.004))
    return scene.extend(objs, bone)


def add_shark_details(scene: CharacterScene, mats: dict[str, bpy.types.Material]) -> None:
    scene.add(add_sphere(f"{scene.prefix}_Cream_Face_Panel", (0, -0.70, 1.94), (0.52, 0.034, 0.33), mats["cream"], 48), "Head")
    scene.add(add_sphere(f"{scene.prefix}_Cream_Cheek_Patch_L", (-0.44, -0.74, 1.91), (0.17, 0.018, 0.19), mats["cream"], 32), "Head")
    scene.add(add_sphere(f"{scene.prefix}_Cream_Cheek_Patch_R", (0.44, -0.74, 1.91), (0.17, 0.018, 0.19), mats["cream"], 32), "Head")
    scene.add(add_cone(f"{scene.prefix}_Dorsal_Fin", (0, 0.04, 2.52), 0.23, 0.56, mats["body"], (math.radians(90), 0, math.radians(30)), 3), "Head")
    scene.add(add_cone(f"{scene.prefix}_Tail_Fin", (0, 0.62, 0.95), 0.25, 0.62, mats["body"], (math.radians(90), 0, 0), 3), "Tail")
    scene.add(add_sphere(f"{scene.prefix}_Side_Fin_L", (-0.63, -0.10, 1.20), (0.14, 0.052, 0.28), mats["body"], 32), "Arm.L")
    scene.add(add_sphere(f"{scene.prefix}_Side_Fin_R", (0.63, -0.10, 1.20), (0.14, 0.052, 0.28), mats["body"], 32), "Arm.R")
    scene.add(add_sphere(f"{scene.prefix}_Starfish_Clip", (-0.36, -0.73, 2.33), (0.17, 0.028, 0.17), mats["accent"], 32), "Head")


def add_squeaky(scene: CharacterScene) -> CharacterScene:
    mats = base_materials("squeaky")
    add_base_plush(scene, mats)
    scene.add(add_sphere(f"{scene.prefix}_Ear_L", (-0.84, -0.02, 1.98), (0.36, 0.11, 0.50), mats["body"]), "Head")
    scene.add(add_sphere(f"{scene.prefix}_Ear_R", (0.84, -0.02, 1.98), (0.36, 0.11, 0.50), mats["body"]), "Head")
    scene.add(add_sphere(f"{scene.prefix}_Inner_Ear_L", (-0.85, -0.10, 1.96), (0.25, 0.030, 0.36), mats["belly"], 32), "Head")
    scene.add(add_sphere(f"{scene.prefix}_Inner_Ear_R", (0.85, -0.10, 1.96), (0.25, 0.030, 0.36), mats["belly"], 32), "Head")
    scene.add(add_sphere(f"{scene.prefix}_Puffy_Muzzle", (0, -0.75, 1.76), (0.23, 0.045, 0.14), mats["belly"], 36), "Head")
    scene.add(add_cylinder(f"{scene.prefix}_Trunk", (0, -0.75, 1.88), 0.13, 0.48, mats["body"], (math.radians(80), 0, 0)), "Head")
    scene.add(add_sphere(f"{scene.prefix}_Trunk_Tip", (0, -0.95, 1.73), (0.18, 0.12, 0.115), mats["body"]), "Head")
    scene.add(add_cone(f"{scene.prefix}_Tiny_Tusk_L", (-0.13, -0.86, 1.73), 0.035, 0.18, mats["cream"], (math.radians(88), 0, math.radians(-12)), 18), "Head")
    scene.add(add_cone(f"{scene.prefix}_Tiny_Tusk_R", (0.13, -0.86, 1.73), 0.035, 0.18, mats["cream"], (math.radians(88), 0, math.radians(12)), 18), "Head")
    for i, z in enumerate([1.77, 1.88, 1.99]):
        scene.add(add_arc(f"{scene.prefix}_Trunk_Ring_{i}", (0, -0.84, z), 0.12 - i * 0.014, 0.033, 1.12 * math.pi, 1.88 * math.pi, mats["seam"], 0.006), "Head")
    add_face(scene, mats, 2.04)
    add_bowler(scene, mats)
    add_book_backpack(scene, mats)
    add_pocket_clock(scene, mats)
    return scene


def add_electraica(scene: CharacterScene) -> CharacterScene:
    mats = base_materials("electraica")
    add_base_plush(scene, mats)
    scene.add(add_sphere(f"{scene.prefix}_Cream_Face_Panel", (0, -0.70, 1.94), (0.54, 0.035, 0.32), mats["cream"], 48), "Head")
    add_face(scene, mats, 1.96, 0.94)
    scene.add(add_cylinder(f"{scene.prefix}_Ear_Coil_L", (-0.80, -0.04, 1.96), 0.22, 0.18, mats["accent"], (0, math.radians(90), 0)), "Head")
    scene.add(add_cylinder(f"{scene.prefix}_Ear_Coil_R", (0.80, -0.04, 1.96), 0.22, 0.18, mats["accent"], (0, math.radians(90), 0)), "Head")
    add_bulb(scene, mats)
    add_battery_pack(scene, mats)
    add_nut(scene, mats)
    add_bolt(scene, mats)
    scene.add(add_cube(f"{scene.prefix}_Chest_Plate", (0, -0.60, 0.98), (0.20, 0.014, 0.15), mats["cream"], (0, 0, 0), 0.01), "Spine")
    scene.add(add_curve(f"{scene.prefix}_Chest_Lightning", [(-0.04, -0.622, 1.04), (0.04, -0.622, 1.04), (-0.02, -0.622, 0.94), (0.05, -0.622, 0.94), (-0.05, -0.622, 0.82)], mats["glow"], 0.009), "Spine")
    return scene


def add_fire_boy(scene: CharacterScene) -> CharacterScene:
    mats = base_materials("fire_boy")
    add_base_plush(scene, mats)
    scene.add(add_sphere(f"{scene.prefix}_Cream_Face_Panel", (0, -0.70, 1.94), (0.52, 0.035, 0.33), mats["cream"], 48), "Head")
    add_face(scene, mats, 1.96, 0.94)
    scene.add(add_cone(f"{scene.prefix}_Outer_Flame_Hood", (0, -0.02, 2.58), 0.50, 0.84, mats["orange_glow"], (0, 0, 0), 8), "Head")
    scene.add(add_cone(f"{scene.prefix}_Inner_Flame", (0.08, -0.07, 2.52), 0.25, 0.58, mats["wood"], (0, 0, math.radians(-5)), 8), "Head")
    add_tux(scene, mats)
    add_extinguisher(scene, mats)
    add_flute(scene, mats)
    return scene


def add_shark_girl(scene: CharacterScene) -> CharacterScene:
    mats = base_materials("shark_girl")
    add_base_plush(scene, mats)
    add_shark_details(scene, mats)
    add_face(scene, mats, 1.96, 0.90)
    add_cream_butler_tie(scene, mats)
    add_guitar(scene, mats)
    return scene


BONES = [
    ("Root", (0, 0, 0.03), (0, 0, 0.50), None),
    ("Spine", (0, 0, 0.50), (0, 0, 1.36), "Root"),
    ("Head", (0, 0, 1.36), (0, 0, 2.42), "Spine"),
    ("Hat", (0, 0, 2.42), (0, 0, 3.03), "Head"),
    ("Arm.L", (-0.30, -0.04, 1.18), (-0.62, -0.34, 0.82), "Spine"),
    ("Arm.R", (0.30, -0.04, 1.18), (0.62, -0.34, 0.82), "Spine"),
    ("Prop.L", (-0.62, -0.34, 0.82), (-0.60, -0.62, 1.06), "Arm.L"),
    ("Prop.R", (0.62, -0.34, 0.82), (0.60, -0.62, 1.06), "Arm.R"),
    ("Leg.L", (-0.20, 0, 0.52), (-0.31, -0.23, 0.14), "Root"),
    ("Leg.R", (0.20, 0, 0.52), (0.31, -0.23, 0.14), "Root"),
    ("Backpack", (-0.22, 0.10, 1.20), (-0.72, -0.02, 0.98), "Spine"),
    ("Tail", (0, 0.18, 0.95), (0, 0.66, 0.82), "Spine"),
]


def create_armature(scene: CharacterScene) -> bpy.types.Object:
    arm_data = bpy.data.armatures.new(f"{scene.prefix}_Basic_Game_Rig")
    arm = bpy.data.objects.new(f"{scene.prefix}_Basic_Game_Rig", arm_data)
    bpy.context.collection.objects.link(arm)
    bpy.context.view_layer.objects.active = arm
    arm.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    edit_bones = {}
    for name, head, tail, parent in BONES:
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
    scene.armature = arm
    scene.export_objects.append(arm)
    return arm


def parent_to_bones(scene: CharacterScene) -> None:
    arm = create_armature(scene)
    for bone_name, objects in scene.bone_groups.items():
        for obj in objects:
            world = obj.matrix_world.copy()
            obj.parent = arm
            obj.parent_type = "BONE"
            obj.parent_bone = bone_name
            obj.matrix_world = world
            obj["rig_bone"] = bone_name


def animate_idle(scene: CharacterScene) -> None:
    if not scene.armature:
        return
    arm = scene.armature
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="POSE")
    frames = [1, 24, 48]
    poses = [
        {"Root": (0, 0, 0), "Head": (0.0, 0.0, -0.05), "Arm.L": (0.0, 0.0, 0.08), "Arm.R": (0.0, 0.0, -0.08), "Backpack": (0.0, 0.0, 0.0)},
        {"Root": (0, 0, 0.08), "Head": (0.04, 0.0, 0.10), "Arm.L": (0.10, 0.02, -0.16), "Arm.R": (-0.08, -0.02, 0.16), "Backpack": (0.03, 0.0, -0.04)},
        {"Root": (0, 0, 0), "Head": (0.0, 0.0, -0.05), "Arm.L": (0.0, 0.0, 0.08), "Arm.R": (0.0, 0.0, -0.08), "Backpack": (0.0, 0.0, 0.0)},
    ]
    for frame, pose in zip(frames, poses):
        bpy.context.scene.frame_set(frame)
        for bone_name, rot in pose.items():
            pbone = arm.pose.bones.get(bone_name)
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


def add_rig_visuals(scene: CharacterScene) -> None:
    rig_mat = material(f"{scene.prefix}_rig_overlay_cyan", (0.08, 0.75, 0.95, 1), 0.38, 0.12)
    joint_mat = material(f"{scene.prefix}_rig_joint_gold", (1.0, 0.78, 0.20, 1), 0.45, 0.08)
    for name, head, tail, _parent in BONES:
        head_v = Vector((head[0], -1.04, head[2]))
        tail_v = Vector((tail[0], -1.04, tail[2]))
        mid = (head_v + tail_v) / 2
        length = (tail_v - head_v).length
        cyl = add_cylinder(f"{scene.prefix}_RigLine_{name}", mid, 0.012, length, rig_mat)
        cyl.rotation_euler = (tail_v - head_v).to_track_quat("Z", "Y").to_euler()
        joint = add_sphere(f"{scene.prefix}_RigJoint_{name}", head_v, (0.035, 0.035, 0.035), joint_mat, 16)
        scene.rig_visuals.extend([cyl, joint])
    for obj in scene.rig_visuals:
        obj.hide_render = True
        obj.hide_viewport = True


def export_glb(scene: CharacterScene) -> None:
    RIGGED_DIR.mkdir(parents=True, exist_ok=True)
    for obj in bpy.context.scene.objects:
        obj.select_set(False)
    for obj in scene.export_objects:
        obj.hide_viewport = False
        obj.hide_render = False
        obj.select_set(True)
    bpy.context.view_layer.objects.active = scene.armature or scene.export_objects[0]
    bpy.ops.export_scene.gltf(
        filepath=str(RIGGED_DIR / f"{scene.slug}-rigged.glb"),
        export_format="GLB",
        use_selection=True,
        export_animations=True,
        export_frame_range=True,
    )


def render_rig_preview(scene: CharacterScene) -> None:
    for obj in scene.rig_visuals:
        obj.hide_render = False
        obj.hide_viewport = False
    render_png(PREVIEW_DIR / f"{scene.slug}-rig.png")
    for obj in scene.rig_visuals:
        obj.hide_render = True
        obj.hide_viewport = True


def render_beauty_preview(scene: CharacterScene) -> None:
    if scene.armature:
        scene.armature.hide_render = True
        scene.armature.hide_viewport = True
    render_png(PREVIEW_DIR / f"{scene.slug}-beauty.png")
    if scene.armature:
        scene.armature.hide_render = False
        scene.armature.hide_viewport = False


def setup_character_scene(title: str, slug: str, prefix: str) -> CharacterScene:
    clear_scene()
    setup_render_scene(title, ortho_scale=3.55, camera_loc=(0, -6.3, 2.15), target=(0, 0, 1.45))
    return CharacterScene(slug=slug, prefix=prefix)


def finalize_character(scene: CharacterScene) -> None:
    parent_to_bones(scene)
    animate_idle(scene)
    render_beauty_preview(scene)
    add_rig_visuals(scene)
    render_rig_preview(scene)
    export_glb(scene)


def add_prop_label(label: str, x: float, mats: dict[str, bpy.types.Material]) -> None:
    add_text(f"label_{label}", label, (x, -0.72, 0.02), 0.13, mats["ink"])


def render_squeaky_objects() -> None:
    clear_scene()
    setup_render_scene("squeaky_objects", ortho_scale=3.6, camera_loc=(0, -5.6, 2.2), target=(0, 0, 0.9))
    mats = base_materials("squeaky")
    scene = CharacterScene("squeaky", "Squeaky_Object")
    add_bowler(scene, mats, loc=(-1.15, -0.05, 0.84), scale=0.75, bone=None)
    add_book_backpack(scene, mats, loc=(0, -0.03, 0.76), scale=1.1, bone=None)
    add_pocket_clock(scene, mats, loc=(1.2, -0.18, 0.82), scale=1.35, bone=None)
    add_prop_label("bowler", -1.15, mats)
    add_prop_label("books", 0, mats)
    add_prop_label("clock", 1.2, mats)
    render_png(PREVIEW_DIR / "squeaky-objects.png")


def render_electraica_objects() -> None:
    clear_scene()
    setup_render_scene("electraica_objects", ortho_scale=3.6, camera_loc=(0, -5.6, 2.2), target=(0, 0, 0.9))
    mats = base_materials("electraica")
    scene = CharacterScene("electraica", "Electraica_Object")
    add_battery_pack(scene, mats, loc=(-1.15, -0.05, 0.82), scale=1.05, bone=None)
    add_bulb(scene, mats, loc=(0, -0.03, 0.84), scale=1.15, bone=None)
    add_nut(scene, mats, loc=(0.95, -0.24, 0.80), scale=1.35, bone=None)
    add_bolt(scene, mats, loc=(1.35, -0.22, 0.74), scale=1.35, bone=None)
    add_prop_label("battery", -1.15, mats)
    add_prop_label("bulb", 0, mats)
    add_prop_label("nut + bolt", 1.18, mats)
    render_png(PREVIEW_DIR / "electraica-objects.png")


def render_fire_objects() -> None:
    clear_scene()
    setup_render_scene("fire_boy_objects", ortho_scale=3.6, camera_loc=(0, -5.6, 2.2), target=(0, 0, 0.9))
    mats = base_materials("fire_boy")
    scene = CharacterScene("fire_boy", "Fire_Object")
    scene.extend([
        add_cylinder("Fire_Object_Extinguisher_Display_Tank", (-1.15, -0.12, 0.86), 0.18, 0.78, mats["body"], (0, 0, 0), 48),
        add_cylinder("Fire_Object_Extinguisher_Display_Cap", (-1.15, -0.12, 1.28), 0.11, 0.08, mats["ink"], (0, 0, 0), 32),
        add_cube("Fire_Object_Extinguisher_Display_Label", (-1.15, -0.31, 0.86), (0.13, 0.012, 0.18), mats["white"], (0, 0, 0), 0.006),
        add_curve("Fire_Object_Extinguisher_Display_Hose", [(-1.05, -0.12, 1.25), (-0.82, -0.22, 1.36), (-0.72, -0.30, 1.12)], mats["ink"], 0.015),
    ])
    add_tux(scene, mats, z=0.83)
    for obj in scene.export_objects:
        if obj.name.startswith("Fire_Object_Tux") or obj.name.startswith("Fire_Object_White") or obj.name.startswith("Fire_Object_Black"):
            obj.location.x += 0.0
    add_flute(scene, mats, loc=(1.18, -0.25, 0.82), scale=1.2, bone=None)
    add_prop_label("extinguisher", -1.15, mats)
    add_prop_label("tuxedo", 0, mats)
    add_prop_label("flute", 1.18, mats)
    render_png(PREVIEW_DIR / "fire-boy-objects.png")


def render_shark_objects() -> None:
    clear_scene()
    setup_render_scene("shark_girl_objects", ortho_scale=3.6, camera_loc=(0, -5.6, 2.2), target=(0, 0, 0.9))
    mats = base_materials("shark_girl")
    scene = CharacterScene("shark_girl", "Shark_Object")
    add_cream_butler_tie(scene, mats, loc=(-1.12, -0.18, 0.86), scale=1.35, bone=None)
    add_guitar(scene, mats, loc=(0.05, -0.22, 0.68), scale=1.25, bone=None)
    scene.add(add_cone("Shark_Object_Tail_Fin", (1.18, -0.04, 0.76), 0.32, 0.78, mats["body"], (math.radians(90), 0, 0), 3))
    scene.add(add_sphere("Shark_Object_Starfish", (1.33, -0.28, 1.05), (0.18, 0.032, 0.18), mats["accent"], 32))
    add_prop_label("cream tie", -1.12, mats)
    add_prop_label("guitar", 0.05, mats)
    add_prop_label("shark bits", 1.22, mats)
    render_png(PREVIEW_DIR / "shark-girl-objects.png")


def main() -> None:
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    RIGGED_DIR.mkdir(parents=True, exist_ok=True)

    squeaky = setup_character_scene("squeaky_rig", "squeaky", "Squeaky")
    finalize_character(add_squeaky(squeaky))
    render_squeaky_objects()

    electraica = setup_character_scene("electraica_rig", "electraica", "Electraica")
    finalize_character(add_electraica(electraica))
    render_electraica_objects()

    fire = setup_character_scene("fire_boy_rig", "fire-boy", "Fire_Boy")
    finalize_character(add_fire_boy(fire))
    render_fire_objects()

    shark = setup_character_scene("shark_girl_rig", "shark-girl", "Shark_Girl")
    finalize_character(add_shark_girl(shark))
    render_shark_objects()

    print(f"Generated rigged GLBs in {RIGGED_DIR}")
    print(f"Generated preview PNGs in {PREVIEW_DIR}")


if __name__ == "__main__":
    main()
