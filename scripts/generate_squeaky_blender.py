"""Generate a first-pass Squeaky GLB in Blender.

Run with:

    blender --background --python scripts/generate_squeaky_blender.py

The web app currently uses a procedural fallback model. This script is the
starting point for replacing it with a GLB that has real shape keys.
"""

from __future__ import annotations

import math
from pathlib import Path

import bpy


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "generated" / "squeaky-prototype.glb"


def mat(name: str, color: tuple[float, float, float, float]) -> bpy.types.Material:
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    bsdf = material.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Roughness"].default_value = 0.82
    return material


def add_uv_sphere(name: str, loc, scale, material):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    obj.data.materials.append(material)
    return obj


def add_cylinder(name: str, loc, radius: float, depth: float, material):
    bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=radius, depth=depth, location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(material)
    return obj


def main() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()

    plush = mat("plush blue gray", (0.43, 0.62, 0.66, 1))
    dark = mat("deep teal suit", (0.05, 0.17, 0.2, 1))
    black = mat("soft black", (0.02, 0.018, 0.014, 1))
    peach = mat("warm cheek", (1.0, 0.55, 0.36, 1))

    body = add_uv_sphere("Squeaky_Body", (0, 0, 1.2), (0.9, 0.72, 0.95), plush)
    head = add_uv_sphere("Squeaky_Head", (0, -0.02, 2.2), (0.78, 0.68, 0.72), plush)
    add_uv_sphere("Ear_L", (-0.72, 0, 2.22), (0.28, 0.12, 0.43), plush)
    add_uv_sphere("Ear_R", (0.72, 0, 2.22), (0.28, 0.12, 0.43), plush)
    trunk = add_cylinder("Trunk", (0, -0.62, 2.08), 0.14, 0.55, plush)
    trunk.rotation_euler[0] = math.radians(78)
    add_uv_sphere("Trunk_Tip", (0, -0.86, 1.9), (0.18, 0.13, 0.13), plush)

    hat = add_cylinder("Bowler_Hat", (0, -0.02, 2.92), 0.42, 0.18, dark)
    hat_top = add_uv_sphere("Bowler_Dome", (0, -0.02, 3.03), (0.34, 0.34, 0.24), dark)
    add_uv_sphere("Cheek_L", (-0.33, -0.6, 2.15), (0.08, 0.02, 0.08), peach)
    add_uv_sphere("Cheek_R", (0.33, -0.6, 2.15), (0.08, 0.02, 0.08), peach)
    add_uv_sphere("Eye_L", (-0.27, -0.63, 2.32), (0.04, 0.015, 0.04), black)
    add_uv_sphere("Eye_R", (0.27, -0.63, 2.32), (0.04, 0.015, 0.04), black)

    body.shape_key_add(name="Basis")
    squish = body.shape_key_add(name="happy_squish")
    for vert in squish.data:
        vert.co.z *= 0.93
        vert.co.x *= 1.04

    bounce_action = bpy.data.actions.new("squeaky_idle_bounce")
    body.animation_data_create()
    body.animation_data.action = bounce_action
    for frame, z in [(1, 1.2), (24, 1.28), (48, 1.2)]:
        body.location.z = z
        body.keyframe_insert("location", frame=frame)

    bpy.ops.object.light_add(type="AREA", location=(0, -3, 5))
    bpy.context.object.name = "Softbox"
    bpy.context.object.data.energy = 420
    bpy.context.object.data.size = 5

    OUT.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=str(OUT), export_format="GLB", export_morph=True, export_animations=True)


if __name__ == "__main__":
    main()

