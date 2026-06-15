# Milestone 1: Fix Fire Boy Physics Body First

## Why This Comes First

The VLA needs real action data:

```text
image + language + robot state -> action
```

Those actions must come from a physics body that actually resembles Fire Boy.
If the body is wrong, the training data will teach the VLA the wrong movement
geometry.

## Target

Build the physics body from:

```text
fire-boy-rig/fire-boy-rigged-full.glb
```

The current MuJoCo body should be treated as a temporary prototype, not the final
Fire Boy body.

## What "Fixed" Means

The corrected physics body should have:

```text
matching skeleton proportions
matching joint positions
matching limb lengths
stable mass and inertia
reasonable collision shapes
hand/contact sites for grasping
mouth site for berry/eating tasks
foot contacts for walking/running
visual overlay proof against the GLB rig
```

## Not Doing Yet

These are later milestones:

```text
ProtoMotions / Kimodo motion priors
successful rollout generation
MiniCPM-V action fine-tuning
true VLA training
```
