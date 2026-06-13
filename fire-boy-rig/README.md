# Rigged Characters — Full Rigs for the Unclothed Base Bodies

Complete humanoid rigs + motion clips for all four toybox characters, built
on the standing unclothed SAM base bodies:

    assets/generated/part-models/raw/<slug>/<slug>-base-body-sam.glb

## Output

- `<slug>-rigged-full.glb` for **squeaky, electraica, fire-boy, shark-girl** —
  mesh, 20-deform-bone skeleton, and ten clips each:
  **Idle, Walk, Run, Jump, Wave, Cheer, Dance, Spin, Throw, Sit**
  (24 fps, in-place loops; Throw doubles as a fireball cast).
- `previews/` — Blender check renders (rest pose, bone overlay, per-clip frames).
- `working/` — pipeline scripts, per-character blend files, reports.

View them live at `/fireboy-rigged` (page: `frontend/fireboy-rigged.html`) —
character switcher, clip crossfading, and a rig inspector (skeleton x-ray
with per-bone labels you can tick on/off). The clips are standard glTF animations,
so the same GLBs can be driven from the toy room with a three.js
`AnimationMixer` for environment interaction.

## Rig

Root → Hips → Spine → Chest → Neck → Head → Crown (flame tip / fin / trunk
tip), plus per side Shoulder → UpperArm → LowerArm → Hand and
UpperLeg → LowerLeg → Foot. Bone placement is derived from vertex-cloud
analysis of the limb blobs, so the same script fits all four bodies.

## Pipeline (run from project root)

```bash
# Stage A: build skeletons, auto-skin, smooth + repair weights (all characters)
blender --background --python fire-boy-rig/working/build_rig.py

# Stage B: author the six clips, push to NLA tracks, export GLBs
blender --background --python fire-boy-rig/working/animate_and_export.py
```

### Notes from the trenches

- Bone-heat auto weights fail on raw SAM meshes until you `remove_doubles`;
  recalc normals outside while you're at it (three.js renders them dark
  otherwise).
- Multi-shell SAM meshes (like the clothed extractions) tear thin shells
  that straddle fast bones. `fix_stretch()` poses test extremes, measures
  per-edge stretch, and glues runaway shells (>2.5x) to a torso-weighted
  neighbor. The main body shell is never rigidified — it gets extra weight
  smoothing instead.
- Animations are authored as world-space axis rotations (converted to
  bone-local in `animate_and_export.py`), so clip definitions read as plain
  "swing legs ±30° about X" regardless of rest-pose bone orientation.
