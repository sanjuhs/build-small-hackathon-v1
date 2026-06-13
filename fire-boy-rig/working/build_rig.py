"""Stage A: build complete humanoid rigs for the unclothed SAM base bodies.

Covers all four toybox characters using the standing "base body" meshes:

    assets/generated/part-models/raw/<slug>/<slug>-base-body-sam.glb

Run from the project root:

    blender --background --python fire-boy-rig/working/build_rig.py

Outputs (per character):
    fire-boy-rig/working/<slug>-rig.blend       (rigged scene, no animations yet)
    fire-boy-rig/working/<slug>-rig-report.json (bone placement + skin stats)
    fire-boy-rig/previews/<slug>-fullrig-rest.png
    fire-boy-rig/previews/<slug>-fullrig-bones.png
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import bpy
from mathutils import Matrix, Vector, kdtree

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "fire-boy-rig"
WORK_DIR = OUT_DIR / "working"
PREVIEW_DIR = OUT_DIR / "previews"

SLUGS = ("squeaky", "electraica", "fire-boy", "shark-girl")


def source_for(slug: str) -> Path:
    return ROOT / "assets" / "generated" / "part-models" / "raw" / slug / f"{slug}-base-body-sam.glb"


def ident(slug: str) -> str:
    return slug.replace("-", "_")


def clear_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)


def material(name: str, color: tuple[float, float, float, float], roughness: float = 0.86):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = color
        bsdf.inputs["Roughness"].default_value = roughness
        if "Metallic" in bsdf.inputs:
            bsdf.inputs["Metallic"].default_value = 0
    return mat


def look_at(obj, target) -> None:
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def setup_render_scene(slug: str) -> None:
    world = bpy.context.scene.world or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.color = (1.0, 0.97, 0.90)
    bpy.context.scene.render.resolution_x = 1100
    bpy.context.scene.render.resolution_y = 1100
    try:
        bpy.context.scene.render.engine = "BLENDER_EEVEE_NEXT"
    except TypeError:
        bpy.context.scene.render.engine = "BLENDER_EEVEE"
    bpy.context.scene.eevee.taa_render_samples = 64

    floor_mat = material(f"{slug}_rig_floor", (0.98, 0.93, 0.82, 1), 0.88)
    bpy.ops.mesh.primitive_cylinder_add(vertices=96, radius=1.45, depth=0.05, location=(0, 0.1, -0.028))
    floor = bpy.context.object
    floor.name = f"{slug}_rig_plinth"
    floor.data.materials.append(floor_mat)

    bpy.ops.object.light_add(type="AREA", location=(0.0, -3.9, 4.6))
    key = bpy.context.object
    key.data.energy = 760
    key.data.size = 5.2

    bpy.ops.object.light_add(type="AREA", location=(-2.9, -2.4, 2.7))
    fill = bpy.context.object
    fill.data.energy = 250
    fill.data.size = 3.2
    fill.data.color = (1.0, 0.88, 0.72)

    bpy.ops.object.camera_add(location=(0, -4.4, 0.96))
    camera = bpy.context.object
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = 1.7
    look_at(camera, (0, 0, 0.52))
    bpy.context.scene.camera = camera


def render_png(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.context.scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)


def import_mesh(slug: str) -> bpy.types.Object:
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(source_for(slug)))
    imported = [o for o in bpy.data.objects if o not in before]
    meshes = [o for o in imported if o.type == "MESH"]
    mesh = max(meshes, key=lambda m: len(m.data.vertices))
    mesh.name = f"{ident(slug)}_Body"
    mesh.data.validate()
    bpy.ops.object.select_all(action="DESELECT")
    mesh.select_set(True)
    bpy.context.view_layer.objects.active = mesh
    if mesh.parent:
        bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    for obj in imported:
        if obj is not mesh and obj.name in bpy.data.objects:
            bpy.data.objects.remove(obj, do_unlink=True)
    # Rest the character on the ground plane, centered on x/y of its bbox.
    min_v, max_v = mesh_bbox(mesh)
    offset = Vector(((min_v.x + max_v.x) / 2, (min_v.y + max_v.y) / 2, min_v.z))
    for v in mesh.data.vertices:
        v.co -= offset
    return mesh


def mesh_bbox(mesh) -> tuple[Vector, Vector]:
    xs = [v.co.x for v in mesh.data.vertices]
    ys = [v.co.y for v in mesh.data.vertices]
    zs = [v.co.z for v in mesh.data.vertices]
    return Vector((min(xs), min(ys), min(zs))), Vector((max(xs), max(ys), max(zs)))


def analyze(mesh) -> dict:
    """Locate limb blobs of a standing chibi body in the vertex cloud."""
    min_v, max_v = mesh_bbox(mesh)
    size = max_v - min_v
    height = size.z
    half_w = size.x / 2
    half_d = size.y / 2
    cx = (min_v.x + max_v.x) / 2
    cy = (min_v.y + max_v.y) / 2
    z0 = min_v.z

    def norm(co):
        return ((co.x - cx) / half_w, (co.y - cy) / half_d, (co.z - z0) / height)

    arm_pts = {"L": [], "R": []}
    leg_pts = {"L": [], "R": []}
    for v in mesh.data.vertices:
        xf, yf, zf = norm(v.co)
        if abs(xf) > 0.52 and 0.24 < zf < 0.58:
            arm_pts["L" if xf < 0 else "R"].append(v.co.copy())
        if zf < 0.16 and abs(xf) > 0.04:
            leg_pts["L" if xf < 0 else "R"].append(v.co.copy())

    def centroid(points):
        acc = Vector((0, 0, 0))
        for p in points:
            acc += p
        return acc / max(len(points), 1)

    report = {
        "bbox_min": list(min_v),
        "bbox_max": list(max_v),
        "height": height,
    }
    out = {"height": height, "cx": cx, "cy": cy, "z0": z0, "half_w": half_w, "half_d": half_d}
    for side, pts in arm_pts.items():
        sign = -1 if side == "L" else 1
        if pts:
            c = centroid(pts)
            tip = max(pts, key=lambda p: sign * p.x - p.z * 0.6).copy()
            out[f"arm_{side}"] = {"centroid": c, "tip": tip, "count": len(pts)}
            report[f"arm_{side}"] = {"centroid": list(c), "tip": list(tip), "count": len(pts)}
    for side, pts in leg_pts.items():
        if pts:
            c = centroid(pts)
            toe = max(pts, key=lambda p: -p.y - p.z * 1.5).copy()
            out[f"leg_{side}"] = {"centroid": c, "toe": toe, "count": len(pts)}
            report[f"leg_{side}"] = {"centroid": list(c), "toe": list(toe), "count": len(pts)}
    out["report"] = report
    return out


def build_armature(slug: str, info: dict) -> bpy.types.Object:
    h = info["height"]
    cy = info["cy"]

    def spine_pt(zf: float, yf: float = 0.0) -> Vector:
        return Vector((0.0, cy + yf * info["half_d"], zf * h))

    bones: list[tuple[str, Vector, Vector, str | None, bool]] = [
        ("Root", spine_pt(0.0), spine_pt(0.10), None, False),
        ("Hips", spine_pt(0.16, 0.04), spine_pt(0.28, 0.02), "Root", True),
        ("Spine", spine_pt(0.28, 0.02), spine_pt(0.40, 0.01), "Hips", True),
        ("Chest", spine_pt(0.40, 0.01), spine_pt(0.50), "Spine", True),
        ("Neck", spine_pt(0.50), spine_pt(0.56), "Chest", True),
        ("Head", spine_pt(0.56), spine_pt(0.86), "Neck", True),
        ("Crown", spine_pt(0.86), spine_pt(1.0), "Head", True),
    ]

    for side in ("L", "R"):
        arm = info.get(f"arm_{side}")
        leg = info.get(f"leg_{side}")
        if arm:
            c, tip = arm["centroid"], arm["tip"]
            shoulder_root = Vector((c.x * 0.30, c.y, c.z + 0.08 * h))
            shoulder_end = Vector((c.x * 0.70, c.y, c.z + 0.04 * h))
            elbow = shoulder_end.lerp(tip, 0.5)
            bones.append((f"Shoulder.{side}", shoulder_root, shoulder_end, "Chest", True))
            bones.append((f"UpperArm.{side}", shoulder_end, elbow, f"Shoulder.{side}", True))
            bones.append((f"LowerArm.{side}", elbow, elbow.lerp(tip, 0.85), f"UpperArm.{side}", True))
            bones.append((f"Hand.{side}", elbow.lerp(tip, 0.85), tip, f"LowerArm.{side}", True))
        if leg:
            c, toe = leg["centroid"], leg["toe"]
            hip = Vector((c.x, c.y, 0.26 * h))
            ankle = Vector((c.x, c.y, max(0.055 * h, toe.z + 0.02 * h)))
            knee = hip.lerp(ankle, 0.5) + Vector((0, -0.015 * h, 0))
            bones.append((f"UpperLeg.{side}", hip, knee, "Hips", True))
            bones.append((f"LowerLeg.{side}", knee, ankle, f"UpperLeg.{side}", True))
            bones.append((f"Foot.{side}", ankle, Vector((toe.x, toe.y, toe.z)), f"LowerLeg.{side}", True))

    arm_data = bpy.data.armatures.new(f"{ident(slug)}_FullRig")
    arm_obj = bpy.data.objects.new(f"{ident(slug)}_FullRig", arm_data)
    bpy.context.collection.objects.link(arm_obj)
    bpy.context.view_layer.objects.active = arm_obj
    arm_obj.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    edit_bones = {}
    for name, head, tail, parent, deform in bones:
        bone = arm_data.edit_bones.new(name)
        bone.head = head
        bone.tail = tail
        bone.roll = 0
        bone.use_deform = deform
        if parent:
            bone.parent = edit_bones[parent]
            bone.use_connect = False
        edit_bones[name] = bone
    bpy.ops.object.mode_set(mode="POSE")
    for pbone in arm_obj.pose.bones:
        pbone.rotation_mode = "XYZ"
    bpy.ops.object.mode_set(mode="OBJECT")
    arm_obj.show_in_front = True
    arm_obj.data.display_type = "OCTAHEDRAL"
    return arm_obj


def unweighted_count(mesh) -> int:
    count = 0
    for v in mesh.data.vertices:
        if sum(gw.weight for gw in v.groups) < 1e-5:
            count += 1
    return count


def proximity_weights(mesh, armature) -> None:
    """Fallback skinning: blend the 3 nearest bone segments per vertex.

    Used when Blender's bone-heat solve fails on a SAM mesh. Works well for
    blobby chibi bodies; the smoothing pass afterwards softens boundaries.
    """
    deform = [b for b in armature.data.bones if b.use_deform]
    segments = []
    for b in deform:
        head = armature.matrix_world @ b.head_local
        tail = armature.matrix_world @ b.tail_local
        segments.append((b.name, head, tail))

    def seg_dist(p, a, b) -> float:
        ab = b - a
        t = max(0.0, min(1.0, (p - a).dot(ab) / max(ab.length_squared, 1e-9)))
        return (p - a - ab * t).length

    for g in list(mesh.vertex_groups):
        mesh.vertex_groups.remove(g)
    groups = {name: mesh.vertex_groups.new(name=name) for name, _, _ in segments}
    for v in mesh.data.vertices:
        world = mesh.matrix_world @ v.co
        dists = sorted(((seg_dist(world, a, b), name) for name, a, b in segments))[:3]
        weights = [(name, 1.0 / (d * d + 1e-4)) for d, name in dists]
        total = sum(w for _, w in weights)
        for name, w in weights:
            groups[name].add([v.index], w / total, "REPLACE")

    mod = mesh.modifiers.new("Armature", "ARMATURE")
    mod.object = armature
    mesh.parent = armature


def skin(mesh, armature) -> dict:
    # Bone heat is picky about SAM geometry; merging doubles first helps.
    bpy.ops.object.select_all(action="DESELECT")
    mesh.select_set(True)
    bpy.context.view_layer.objects.active = mesh
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.remove_doubles(threshold=1e-5)
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode="OBJECT")

    bpy.ops.object.select_all(action="DESELECT")
    mesh.select_set(True)
    armature.select_set(True)
    bpy.context.view_layer.objects.active = armature
    try:
        bpy.ops.object.parent_set(type="ARMATURE_AUTO")
    except RuntimeError:
        pass

    used_fallback = False
    if unweighted_count(mesh) > 0.05 * len(mesh.data.vertices):
        proximity_weights(mesh, armature)
        used_fallback = True

    bpy.ops.object.select_all(action="DESELECT")
    mesh.select_set(True)
    bpy.context.view_layer.objects.active = mesh
    bpy.ops.object.mode_set(mode="WEIGHT_PAINT")
    bpy.ops.object.vertex_group_smooth(group_select_mode="ALL", factor=0.5, repeat=5, expand=0.0)
    bpy.ops.object.vertex_group_limit_total(group_select_mode="ALL", limit=4)
    bpy.ops.object.vertex_group_normalize_all(group_select_mode="ALL", lock_active=False)
    bpy.ops.object.mode_set(mode="OBJECT")

    stats: dict[str, float] = {}
    unweighted = 0
    deform_groups = {g.index: g.name for g in mesh.vertex_groups}
    totals = {name: 0.0 for name in deform_groups.values()}
    for v in mesh.data.vertices:
        total = 0.0
        for gw in v.groups:
            totals[deform_groups[gw.group]] += gw.weight
            total += gw.weight
        if total < 1e-5:
            unweighted += 1
    stats["unweighted_verts"] = unweighted
    stats["vert_count"] = len(mesh.data.vertices)
    stats["used_proximity_fallback"] = used_fallback
    stats["bone_weight_totals"] = {k: round(val, 1) for k, val in sorted(totals.items())}
    return stats


def world_rot_euler(pbone, rx: float, ry: float, rz: float):
    rot = (
        Matrix.Rotation(math.radians(rz), 4, "Z")
        @ Matrix.Rotation(math.radians(ry), 4, "Y")
        @ Matrix.Rotation(math.radians(rx), 4, "X")
    )
    rest = pbone.bone.matrix_local.to_3x3().to_4x4()
    return (rest.inverted() @ rot @ rest).to_euler("XYZ")


STRETCH_TEST_POSES = [
    {"UpperArm.L": (-100, 20, 0), "UpperArm.R": (-100, -20, 0), "LowerArm.L": (0, 20, 0), "LowerArm.R": (0, -20, 0)},
    {"UpperLeg.L": (-48, 0, 0), "UpperLeg.R": (48, 0, 0), "LowerLeg.L": (40, 0, 0), "LowerLeg.R": (40, 0, 0)},
    {"Spine": (16, 0, 0), "Head": (-12, 0, 8), "UpperArm.R": (-50, -65, 0), "Hand.R": (0, 0, 20)},
]


def mesh_components(mesh) -> list[list[int]]:
    parent = list(range(len(mesh.data.vertices)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for edge in mesh.data.edges:
        a, b = edge.vertices
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb
    groups: dict[int, list[int]] = {}
    for i in range(len(mesh.data.vertices)):
        groups.setdefault(find(i), []).append(i)
    return list(groups.values())


def vertex_weights(mesh, vi: int) -> list[tuple[str, float]]:
    group_names = {g.index: g.name for g in mesh.vertex_groups}
    weights = [(group_names[gw.group], gw.weight) for gw in mesh.data.vertices[vi].groups if gw.weight > 0]
    weights.sort(key=lambda kv: -kv[1])
    weights = weights[:4]
    total = sum(w for _, w in weights) or 1.0
    return [(name, w / total) for name, w in weights]


def glue_component(mesh, verts: list[int], weights: list[tuple[str, float]]) -> None:
    """Give every vertex in the component the same fixed weights."""
    by_name = {g.name: g for g in mesh.vertex_groups}
    for group in by_name.values():
        group.remove(verts)
    for name, weight in weights:
        by_name[name].add(verts, weight, "REPLACE")


def fix_stretch(mesh, armature, max_rounds: int = 3) -> dict:
    """Rigidify connected components that stretch badly under test poses.

    SAM meshes can carry disjoint shells; thin ones tear apart when their
    verts straddle bones that move very differently. Rigid per-shell weights
    keep them in one piece. Single-shell bodies pass untouched.
    """
    components = mesh_components(mesh)
    comp_of = {}
    for ci, verts in enumerate(components):
        for vi in verts:
            comp_of[vi] = ci
    # The main body must keep smooth deformation; local over-stretch there
    # is treated with extra weight smoothing instead of rigidifying.
    total_verts = len(mesh.data.vertices)
    exempt = {ci for ci, verts in enumerate(components) if len(verts) > 0.5 * total_verts}
    rest_lengths = {}
    for edge in mesh.data.edges:
        a, b = edge.vertices
        rest_lengths[(a, b)] = (mesh.data.vertices[a].co - mesh.data.vertices[b].co).length

    log = {"component_count": len(components), "rounds": [], "rigidified": 0}
    for round_no in range(max_rounds):
        bad: set[int] = set()
        for pose in STRETCH_TEST_POSES:
            for pbone in armature.pose.bones:
                pbone.rotation_euler = (0, 0, 0)
            for bone, rot in pose.items():
                pbone = armature.pose.bones[bone]
                pbone.rotation_euler = world_rot_euler(pbone, *rot)
            depsgraph = bpy.context.evaluated_depsgraph_get()
            depsgraph.update()
            eval_mesh = mesh.evaluated_get(depsgraph).to_mesh()
            for (a, b), rest_len in rest_lengths.items():
                if rest_len < 1e-6:
                    continue
                ratio = (eval_mesh.vertices[a].co - eval_mesh.vertices[b].co).length / rest_len
                if ratio > 2.5:
                    bad.add(comp_of[a])
            mesh.evaluated_get(depsgraph).to_mesh_clear()
        for pbone in armature.pose.bones:
            pbone.rotation_euler = (0, 0, 0)
        body_stretch = bool(bad & exempt)
        bad -= exempt
        log["rounds"].append(
            {"round": round_no, "bad_components": len(bad), "body_stretch": body_stretch}
        )
        if body_stretch:
            bpy.ops.object.select_all(action="DESELECT")
            mesh.select_set(True)
            bpy.context.view_layer.objects.active = mesh
            bpy.ops.object.mode_set(mode="WEIGHT_PAINT")
            bpy.ops.object.vertex_group_smooth(group_select_mode="ALL", factor=0.5, repeat=3, expand=0.0)
            bpy.ops.object.vertex_group_normalize_all(group_select_mode="ALL", lock_active=False)
            bpy.ops.object.mode_set(mode="OBJECT")
        if not bad:
            if not body_stretch:
                break
            continue
        # Glue each runaway shell rigidly to a stable neighbor, preferring a
        # torso-weighted anchor so the shell stays on the body.
        good_verts = [vi for ci, verts in enumerate(components) if ci not in bad for vi in verts]
        tree = kdtree.KDTree(len(good_verts))
        for idx, vi in enumerate(good_verts):
            tree.insert(mesh.data.vertices[vi].co, idx)
        tree.balance()
        core_bones = {"Root", "Hips", "Spine", "Chest", "Neck", "Head", "Crown"}
        for ci in bad:
            anchors = []
            for vi in components[ci]:
                _, idx, dist = tree.find(mesh.data.vertices[vi].co)
                anchors.append((good_verts[idx], dist))
            anchors.sort(key=lambda kv: kv[1])
            core_anchor = next(
                (a for a, _ in anchors if vertex_weights(mesh, a) and vertex_weights(mesh, a)[0][0] in core_bones),
                anchors[0][0],
            )
            glue_component(mesh, components[ci], vertex_weights(mesh, core_anchor))
        log["rigidified"] += len(bad)
    return log


def process(slug: str) -> dict:
    clear_scene()
    mesh = import_mesh(slug)
    info = analyze(mesh)
    armature = build_armature(slug, info)
    stats = skin(mesh, armature)
    stats["stretch_fix"] = fix_stretch(mesh, armature)

    WORK_DIR.mkdir(parents=True, exist_ok=True)
    report = {"slug": slug, "analysis": info["report"], "skin": stats}
    (WORK_DIR / f"{slug}-rig-report.json").write_text(json.dumps(report, indent=2))

    setup_render_scene(slug)
    render_png(PREVIEW_DIR / f"{slug}-fullrig-rest.png")

    stick_mat = material(f"{slug}_bone_stick", (0.1, 0.9, 1.0, 1), 0.3)
    for bone in armature.data.bones:
        head = armature.matrix_world @ bone.head_local
        tail = armature.matrix_world @ bone.tail_local
        mid = (head + tail) / 2
        length = (tail - head).length
        bpy.ops.mesh.primitive_cylinder_add(vertices=10, radius=0.008, depth=max(length, 0.02), location=mid)
        stick = bpy.context.object
        stick.rotation_euler = (tail - head).to_track_quat("Z", "Y").to_euler()
        stick.data.materials.append(stick_mat)
    render_png(PREVIEW_DIR / f"{slug}-fullrig-bones.png")

    for obj in list(bpy.data.objects):
        if obj not in (mesh, armature):
            bpy.data.objects.remove(obj, do_unlink=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(WORK_DIR / f"{slug}-rig.blend"))
    return report


def main() -> None:
    summary = {}
    for slug in SLUGS:
        if not source_for(slug).exists():
            summary[slug] = "missing source"
            continue
        report = process(slug)
        summary[slug] = {
            "unweighted": report["skin"]["unweighted_verts"],
            "fallback": report["skin"]["used_proximity_fallback"],
            "stretch_fix": report["skin"]["stretch_fix"]["rounds"],
        }
    print("BUILD_SUMMARY", json.dumps(summary))


main()
