# Fire Boy VLA / Physics Notes

## Source Of Truth

The Toy Room v3 Fire Boy visual rig is:

```text
fire-boy-rig/fire-boy-rigged-full.glb
```

This is the current target model for VLA/physics work. It is the later proper
rigged Fire Boy used by Toy Room v3, not the older socketed assembly model.

Toy Room v3 references it from:

```text
frontend/toybox/v2_main.js
```

Relevant runtime mapping:

```js
fire_boy: IS_V3_MODE ? "/fire-boy-rig/fire-boy-rigged-full.glb" : "/toy-assets/generated/rigged/fire-boy-rigged.glb"
```

## Important Related Assets

```text
fire-boy-rig/fire-boy-rigged-full.glb
```

- Current Toy Room v3 Fire Boy rig.
- Better target for physics-body matching.
- Mesh + skeleton + animation clips.

```text
assets/generated/part-models/assemblies/fire-boy-assembled.glb
```

- Older socketed kit assembly.
- Matches the model-gallery screenshot with 53,253 triangles and 8 animations.
- Useful visual reference for costume/accessories, but not the Toy Room v3
  runtime rig.

## Current MuJoCo Mismatch

The current MuJoCo Fire Boy is not loaded from the Toy Room v3 GLB. It is a
hand-written primitive body made from capsules, spheres, boxes, and simple
joints in:

```text
fireboy-vla-physics/src/fireboy_mjcf.py
fireboy-vla-physics/src/fireboy_articulated_mjcf.py
```

That is why the MuJoCo body does not resemble the actual Fire Boy. The next
physics milestone is to rebuild the MuJoCo articulated body so its link lengths,
joint locations, collision capsules, mass distribution, and visual alignment are
derived from `fire-boy-rig/fire-boy-rigged-full.glb`.

## Local App

The local Gradio/FastAPI app was observed on:

```text
http://127.0.0.1:65372
```

## Target Architecture

The desired long-term model is:

```text
image + language + robot state -> action
```

For Fire Boy this means:

```text
camera image
+ user command
+ proprioception / simulated body state
-> joint targets or low-level action deltas
```

The practical training path should still use physics skills and imitation data
as scaffolding, then distill or fine-tune a VLA-style policy on successful
rollouts.
