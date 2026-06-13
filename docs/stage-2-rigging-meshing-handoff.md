# Stage 2 Rigging + Meshing Handoff

Generated: June 11, 2026

Workspace root:

```text
/Users/sanju/Desktop/coding/hackathons/build-small-hackathon-v1
```

Main local viewer:

```text
http://127.0.0.1:65372/blender-models
```

Current focused asset:

```text
http://127.0.0.1:65372/blender-models?asset=mixamo-electraica-motion-pack&v=motion-pack-v1
```

## Short Answer: Can An LLM Teach Motion?

Yes, but the smart role for an LLM is not "magically fix animation." The useful setup is:

1. A clean rig-ready mesh with sensible topology and weights.
2. A named chibi armature with stable bones and sockets.
3. Motion recipes that an LLM can write or adjust.
4. Blender Python that bakes those recipes into actions.
5. Viewer QA with rig labels, screenshots, and animation playback.

An LLM can generate and revise motion specs like "24-frame cute walk, small root bob, arms counter-swing, head stays stable." It can also write Blender scripts that create actions, tweak curves, and export GLBs. It cannot overcome bad deformation topology by itself. The current SAM meshes are cute, but they are not production animation meshes: they are dense, uneven triangle surfaces without proper shoulder, hip, elbow, knee, or belly loops. That is why Mixamo motion clips and even mapped local bones can clip or collapse.

Best next strategy: use the SAM meshes as visual reference, then make either a clean retopologized plush mesh or a low-poly deformation proxy. Rig that clean mesh, weight paint it, then author custom chibi animation cycles.

## Current State

The project has four characters:

- Squeaky: simple elephant-like toy with book backpack, clock, bowler hat.
- Electraica: yellow electric character with battery backpack, bulb, nut, bolt, chest plate.
- Fire Boy: flame character with tuxedo, fire extinguisher backpack, shoulder strap, flute.
- Shark Girl: shark character with cream bowtie, guitar, guitar strap, starfish clip.

Already built:

- 2D source images and individual part images.
- SAM 3D raw GLBs for base bodies and individual objects.
- Cleaned/standing/base-rigged GLBs.
- Socketed assembly GLBs with accessories.
- Blender `.blend` assembly scenes.
- FBX exports for Mixamo testing.
- Electraica Mixamo retarget tests and one combined motion pack.
- Viewer UI with asset list, stats, wireframe, rig lines, rig labels, and animation dropdown.

Main issue:

- Mixamo is not a good final answer for these plush/chibi toys. It assumes human limb proportions and a human skeleton. These characters have huge heads, round bodies, stubby limbs, and accessory sockets, so human mocap creates clipping and odd deformation.

## Viewer And Frontend Files

Main viewer page:

```text
frontend/blender-models.html
```

Main viewer logic:

```text
frontend/toybox/blender_models.js
```

Server manifest and asset registration:

```text
app.py
```

Parts lab page:

```text
frontend/parts-lab.html
```

Useful URLs:

```text
http://127.0.0.1:65372/blender-models
http://127.0.0.1:65372/parts-lab
http://127.0.0.1:65372/blender-models?asset=sam-base-rigged-electraica&v=aligned-v4
http://127.0.0.1:65372/blender-models?asset=mixamo-electraica-motion-pack&v=motion-pack-v1
```

Viewer features already added:

- GLB model viewing.
- Polygon/vertex/mesh/material/animation stats.
- Wireframe toggle.
- Auto-rotate.
- Rig line overlay.
- Rig label checkbox.
- Animation dropdown.
- Mixamo motion-test asset group.

## Source Character Images

Original 2D character images:

```text
potential-char-images/squeaky.png
potential-char-images/electraica-(her).png
potential-char-images/fire-boy.png
potential-char-images/shark-girl.png
```

Original SAM extraction outputs:

```text
potential-char-images/extracted-from-sam/squeaky-sam.glb
potential-char-images/extracted-from-sam/electraica-sam.glb
potential-char-images/extracted-from-sam/fire-boy-sam.glb
potential-char-images/extracted-from-sam/shark-girl-sam.glb
potential-char-images/extracted-from-sam/combined_scene (2).glb
potential-char-images/extracted-from-sam/electraica-sam-result.json
potential-char-images/extracted-from-sam/shark-girl-sam-result.json
```

## 2D Part Images

Part manifest:

```text
assets/generated/part-concepts/parts-manifest.json
```

Individual v2 part images:

```text
assets/generated/part-concepts/individual-v2/squeaky/base-body.png
assets/generated/part-concepts/individual-v2/squeaky/book-backpack.png
assets/generated/part-concepts/individual-v2/squeaky/bowler-hat.png
assets/generated/part-concepts/individual-v2/squeaky/pocket-clock.png

assets/generated/part-concepts/individual-v2/electraica/base-body.png
assets/generated/part-concepts/individual-v2/electraica/battery-backpack.png
assets/generated/part-concepts/individual-v2/electraica/bolt.png
assets/generated/part-concepts/individual-v2/electraica/bulb-head.png
assets/generated/part-concepts/individual-v2/electraica/chest-plate.png
assets/generated/part-concepts/individual-v2/electraica/hex-nut.png

assets/generated/part-concepts/individual-v2/fire-boy/base-body.png
assets/generated/part-concepts/individual-v2/fire-boy/extinguisher-backpack.png
assets/generated/part-concepts/individual-v2/fire-boy/flute.png
assets/generated/part-concepts/individual-v2/fire-boy/shoulder-strap.png
assets/generated/part-concepts/individual-v2/fire-boy/tuxedo.png

assets/generated/part-concepts/individual-v2/shark-girl/base-body.png
assets/generated/part-concepts/individual-v2/shark-girl/cream-bowtie.png
assets/generated/part-concepts/individual-v2/shark-girl/guitar.png
assets/generated/part-concepts/individual-v2/shark-girl/guitar-strap.png
assets/generated/part-concepts/individual-v2/shark-girl/starfish-clip.png
```

Contact sheets:

```text
assets/generated/part-concepts/parts-individual-v2-contact.png
assets/generated/part-concepts/parts-sheets-contact.png
assets/generated/part-concepts/squeaky-individual-v2-contact.png
assets/generated/part-concepts/electraica-individual-v2-contact.png
assets/generated/part-concepts/fire-boy-individual-v2-contact.png
assets/generated/part-concepts/shark-girl-individual-v2-contact.png
assets/generated/part-concepts/squeaky-parts-sheet.png
assets/generated/part-concepts/electraica-parts-sheet.png
assets/generated/part-concepts/fire-boy-parts-sheet.png
assets/generated/part-concepts/shark-girl-parts-sheet.png
```

Older individual part images also exist under:

```text
assets/generated/part-concepts/individual/
```

Prefer `individual-v2/` for the next pass.

## Raw SAM 3D Part GLBs

Squeaky:

```text
assets/generated/part-models/raw/squeaky/squeaky-base-body-sam.glb
assets/generated/part-models/raw/squeaky/squeaky-book-backpack-sam.glb
assets/generated/part-models/raw/squeaky/squeaky-bowler-hat-sam.glb
assets/generated/part-models/raw/squeaky/squeaky-pocket-clock-sam.glb
```

Electraica:

```text
assets/generated/part-models/raw/electraica/electraica-base-body-sam.glb
assets/generated/part-models/raw/electraica/electraica-battery-backpack-sam.glb
assets/generated/part-models/raw/electraica/electraica-bolt-sam.glb
assets/generated/part-models/raw/electraica/electraica-bulb-head-sam.glb
assets/generated/part-models/raw/electraica/electraica-chest-plate-sam.glb
assets/generated/part-models/raw/electraica/electraica-hex-nut-sam.glb
```

Fire Boy:

```text
assets/generated/part-models/raw/fire-boy/fire-boy-base-body-sam.glb
assets/generated/part-models/raw/fire-boy/fire-boy-extinguisher-backpack-sam.glb
assets/generated/part-models/raw/fire-boy/fire-boy-flute-sam.glb
assets/generated/part-models/raw/fire-boy/fire-boy-shoulder-strap-sam.glb
assets/generated/part-models/raw/fire-boy/fire-boy-tuxedo-sam.glb
```

Shark Girl:

```text
assets/generated/part-models/raw/shark-girl/shark-girl-base-body-sam.glb
assets/generated/part-models/raw/shark-girl/shark-girl-cream-bowtie-sam.glb
assets/generated/part-models/raw/shark-girl/shark-girl-guitar-sam.glb
assets/generated/part-models/raw/shark-girl/shark-girl-guitar-strap-sam.glb
assets/generated/part-models/raw/shark-girl/shark-girl-starfish-clip-sam.glb
```

Each raw SAM output usually has a matching `*-sam-result.json` beside it.

## Rigged Base Bodies

These are the current aligned v4 chibi rigs:

```text
assets/generated/part-models/rigged-bases/squeaky-base-rigged.glb
assets/generated/part-models/rigged-bases/electraica-base-rigged.glb
assets/generated/part-models/rigged-bases/fire-boy-base-rigged.glb
assets/generated/part-models/rigged-bases/shark-girl-base-rigged.glb
```

Current rig notes:

- One skinned mesh per character.
- 16-ish named joints depending on export.
- Local custom actions are included.
- Rig labels work in the viewer.
- Electraica hip/root and hand socket were manually improved in the latest pass.
- This rig is good for visualization and rough prototyping.
- This rig is not yet a production-quality deformation rig.

Known deformation limits:

- No real IK controls.
- No foot locking.
- No collision solving between limbs/body.
- No clean quad edge loops around shoulders, hips, knees, or elbows.
- SAM surface is cute but not animation-friendly.
- Accessories are better as socketed rigid objects, not as deforming mesh.

## Socketed Assemblies

These combine the base bodies with the separate objects:

```text
assets/generated/part-models/assemblies/squeaky-assembled.glb
assets/generated/part-models/assemblies/electraica-assembled.glb
assets/generated/part-models/assemblies/fire-boy-assembled.glb
assets/generated/part-models/assemblies/shark-girl-assembled.glb
```

Blender source scenes:

```text
assets/generated/part-models/blend-scenes/squeaky-assembly.blend
assets/generated/part-models/blend-scenes/electraica-assembly.blend
assets/generated/part-models/blend-scenes/fire-boy-assembly.blend
assets/generated/part-models/blend-scenes/shark-girl-assembly.blend
```

These `.blend` files are the best place to continue object attachment, sockets, pivots, and physics experiments.

## FBX Exports For Mixamo

Unrigged base mesh FBXs:

```text
assets/generated/part-models/mixamo-fbx/squeaky-base-mesh.fbx
assets/generated/part-models/mixamo-fbx/electraica-base-mesh.fbx
assets/generated/part-models/mixamo-fbx/fire-boy-base-mesh.fbx
assets/generated/part-models/mixamo-fbx/shark-girl-base-mesh.fbx
```

Local Blender-rigged FBXs:

```text
assets/generated/part-models/mixamo-fbx/squeaky-base-rigged.fbx
assets/generated/part-models/mixamo-fbx/electraica-base-rigged.fbx
assets/generated/part-models/mixamo-fbx/fire-boy-base-rigged.fbx
assets/generated/part-models/mixamo-fbx/shark-girl-base-rigged.fbx
```

Mixamo can be useful as a rough reference, but it should not be treated as the final animation source for these characters.

## Downloaded Mixamo Motions

Source FBX files found in Downloads and copied into the project:

```text
/Users/sanju/Downloads/Dancing Twerk.fbx
/Users/sanju/Downloads/Jumping Down.fbx
/Users/sanju/Downloads/Unarmed Walk Forward.fbx
```

Project copy:

```text
assets/generated/part-models/mixamo-downloads/electraica/Dancing Twerk.fbx
assets/generated/part-models/mixamo-downloads/electraica/Jumping Down.fbx
assets/generated/part-models/mixamo-downloads/electraica/Unarmed Walk Forward.fbx
```

Converted Electraica outputs:

```text
assets/generated/part-models/mixamo-motion-tests/electraica/electraica-mixamo-dancing-twerk.glb
assets/generated/part-models/mixamo-motion-tests/electraica/electraica-mixamo-jumping-down.glb
assets/generated/part-models/mixamo-motion-tests/electraica/electraica-mixamo-unarmed-walk-forward.glb
assets/generated/part-models/mixamo-motion-tests/electraica/electraica-mixamo-motion-pack.glb
```

The Electraica motion pack currently contains seven actions:

```text
Dancing Twerk
Friendly wave
Happy hop
Idle bounce
Jumping Down
Tiny waddle
Unarmed Walk Forward
```

The viewer animation dropdown sorts these into a usable order.

## Preview Images

General previews:

```text
assets/generated/previews/contact-sheet.png
assets/generated/previews/sam-contact-sheet.png
assets/generated/previews/part-base-rigs-contact.png
assets/generated/previews/part-assemblies-contact.png
```

Per-character preview pattern:

```text
assets/generated/previews/<character>-beauty.png
assets/generated/previews/<character>-objects.png
assets/generated/previews/<character>-rig.png
assets/generated/previews/<character>-sam-cleaned.png
assets/generated/previews/<character>-sam-standing-rig.png
assets/generated/previews/<character>-sam-standing-rigged.png
assets/generated/previews/<character>-part-base-rigged.png
assets/generated/previews/<character>-part-assembly.png
```

Electraica Mixamo previews:

```text
assets/generated/previews/electraica-mixamo-dancing-twerk.png
assets/generated/previews/electraica-mixamo-jumping-down.png
assets/generated/previews/electraica-mixamo-unarmed-walk-forward.png
assets/generated/previews/electraica-mixamo-motion-pack.png
```

## Main Scripts

Generate aligned rigged base bodies, assemblies, FBX exports, Blender scenes, and previews:

```text
scripts/rig_part_base_models_blender.py
scripts/rig_part_base_models.sh
```

Import downloaded Mixamo FBXs, retarget them onto the Toybox rig, and export motion-test GLBs:

```text
scripts/import_mixamo_motions_blender.py
scripts/import_mixamo_motions.sh
```

Generate SAM part models:

```text
scripts/generate_sam_part_models.py
```

Generate original SAM 3D models:

```text
scripts/generate_sam_3d_models.py
```

Clean SAM models:

```text
scripts/clean_sam_models_blender.py
scripts/clean_sam_models.sh
```

Other older/procedural character scripts:

```text
scripts/generate_character_models_blender.py
scripts/generate_squeaky_blender.py
```

## Useful Commands

Start the local app:

```bash
PORT=65372 .venv/bin/python app.py
```

Rebuild the current rigged base bodies and assemblies:

```bash
./scripts/rig_part_base_models.sh
```

Retarget any FBXs dropped into the Mixamo download folders:

```bash
./scripts/import_mixamo_motions.sh
```

Expected Mixamo download folders:

```text
assets/generated/part-models/mixamo-downloads/squeaky/*.fbx
assets/generated/part-models/mixamo-downloads/electraica/*.fbx
assets/generated/part-models/mixamo-downloads/fire-boy/*.fbx
assets/generated/part-models/mixamo-downloads/shark-girl/*.fbx
```

Recommended Mixamo download settings:

```text
Format: FBX Binary
Skin: With Skin
Frames per second: 30
Keyframe reduction: None
```

## Why Mixamo Looks Bad Here

Mixamo failed mostly for expected reasons:

- Human animation assumes human proportions.
- Chibi bodies have short legs, wide heads, big bellies, and stubby arms.
- SAM output topology is not animation topology.
- The mesh does not have deformation loops where bending needs them.
- The retargeter maps rotations, but it does not solve self-intersection.
- The accessories need rigid sockets or constraints, not full-body skin deformation.

Conclusion: keep Mixamo as a reference library only. Use it to study timing, not as the final runtime motion.

## Better Stage 2 Pipeline

Recommended next stage:

1. Choose Electraica as the pilot character.
2. Use the SAM Electraica body as visual reference, not final topology.
3. Build a clean plush proxy mesh in Blender:
   - round head/body capsules,
   - separate stubby limbs,
   - enough loops around shoulders, hips, knees, and elbows,
   - applied scale and centered origin.
4. Add a production chibi armature:
   - `Root`,
   - `Hip`,
   - `Spine`,
   - `Head`,
   - `Arm.L`, `Hand.L`,
   - `Arm.R`, `Hand.R`,
   - `Leg.L`, `Foot.L`,
   - `Leg.R`, `Foot.R`,
   - non-deforming sockets such as `Socket.Back`, `Socket.Head`, `Socket.Hand.L`, `Socket.Hand.R`.
5. Parent mesh to armature with automatic weights as a starting point.
6. Manually weight paint:
   - hips,
   - belly,
   - shoulders,
   - hands,
   - upper legs,
   - feet.
7. Add simple IK controls:
   - foot controls,
   - hand controls if the character will hold objects.
8. Author custom chibi cycles:
   - idle bounce,
   - walk,
   - happy hop,
   - wave,
   - pickup/put-on accessory.
9. Export GLB.
10. QA in the viewer with rig labels and animation dropdown.
11. Repeat for the other three characters after Electraica works.

## LLM-Assisted Motion Recipe Idea

Instead of trying random animations, define motion in a small JSON-like recipe and let Blender bake it.

Example:

```json
{
  "name": "cute_walk",
  "fps": 24,
  "frames": 24,
  "loop": true,
  "style": {
    "root_bob": 0.045,
    "side_sway": 0.035,
    "head_counter_sway": 0.015,
    "arm_swing_degrees": 16,
    "leg_swing_degrees": 13,
    "foot_lift": 0.035
  },
  "key_poses": [
    { "frame": 1, "phase": "left_contact" },
    { "frame": 7, "phase": "down" },
    { "frame": 13, "phase": "right_contact" },
    { "frame": 19, "phase": "up" },
    { "frame": 25, "phase": "left_contact" }
  ]
}
```

Then a Blender script can:

- read the recipe,
- set bone rotations and root offsets,
- insert keyframes,
- set interpolation,
- make the action cyclic,
- export the GLB.

This is the best use of an LLM: ask it to adjust the recipe after looking at screenshots or viewer playback. For example:

```text
The hips are too low, arms clip into the belly, and the left foot slides. Reduce arm swing by 40%, raise root by 0.04, increase foot lift, and keep the head more upright.
```

The LLM can revise the recipe and Blender script quickly, but the mesh still needs good weights.

## Runtime "Live" Motion Plan

For the web app, use Three.js `AnimationMixer` as the base:

- idle action always available,
- walk action blended in when speed increases,
- hop/wave/pickup actions as one-shot clips,
- blend time around `0.12` to `0.25` seconds,
- speed parameter controls walk playback speed,
- expression/accessory state handled separately from locomotion.

For real interactive control:

- Keyboard/joystick sets `speed`, `turn`, and `action`.
- The character model plays blended animation clips.
- Socketed objects follow named bones or sockets.
- Heavy objects can be simulated in Blender and baked, or simulated in the browser with a physics engine later.

Do not start with full ragdoll or full procedural physics. Get one clean hand-authored walk cycle first.

## Blender Learning Checklist

The most important Blender skills for this exact project:

- Apply transforms: `Ctrl+A -> Rotation & Scale`.
- Set origin and align mesh to world floor.
- Create an armature in front/side view.
- Understand Edit Mode bones vs Pose Mode bones.
- Name bones consistently.
- Fix bone roll.
- Parent mesh with armature deform.
- Inspect vertex groups.
- Weight paint with normalize enabled.
- Test deformation in Pose Mode.
- Add IK constraints for feet and hands.
- Insert keyframes with `I`.
- Use Dope Sheet and Graph Editor.
- Make cyclic animation with NLA or F-curves cycles modifier.
- Export GLB with animations.

Best practice exercise:

1. Make one simple capsule plush body.
2. Add two arms and two legs.
3. Rig with 10 bones.
4. Weight paint manually.
5. Make a 24-frame walk loop.
6. Export to GLB.
7. Check it in the viewer.

That exercise teaches more than downloading 30 Mixamo clips.

## Stage 2 Definition Of Done

For Electraica first:

- Clean mesh or deformation proxy exists in Blender.
- Bones are visually aligned in the viewer.
- Rig labels land on the expected body areas.
- Hip/root is above the floor and inside the lower belly, not below the feet.
- Hands and sockets are at the real ends of the arms.
- Idle and walk have no major clipping.
- Feet contact the floor cleanly.
- Accessories can attach/detach from sockets.
- GLB plays correctly in `/blender-models`.

After that, port the same rigging pattern to Squeaky, Fire Boy, and Shark Girl.

## Recommended Next Chat Prompt

Use this markdown file as context and ask:

```text
We are moving into Stage 2 rigging and meshing. Start with Electraica. Use docs/stage-2-rigging-meshing-handoff.md as the source of truth. Build or retopologize a clean plush deformation mesh, create a proper chibi armature with sockets, hand-author a simple 24-frame walk cycle and idle, export to GLB, and verify in the model viewer with rig labels.
```

## One Strong Recommendation

Stop treating the current SAM mesh as the final animation mesh. It is good visual reference and good for static objects. For believable motion, build a clean rigged plush mesh first, then layer the SAM/detail objects and accessories on top through sockets.
