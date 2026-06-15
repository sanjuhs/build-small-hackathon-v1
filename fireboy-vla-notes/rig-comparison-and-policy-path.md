# Fire Boy Rig Comparison And Policy Path

## Captured Screenshots

All comparison images are stored in:

```text
fireboy-vla-notes/screenshots/
```

Key files:

```text
browser-fireboy-rigged-viewer.png
browser-toyroom-v3-fireboy.png
toyroom-v3-glb-fullrig-rest-preview.png
toyroom-v3-glb-fullrig-bones-preview.png
current-mujoco-articulated-body.png
current-mujoco-skeleton-rest.png
current-mujoco-vs-rig-skeleton-overlay.png
```

## Target Visual Rig

The Toy Room v3 Fire Boy target remains:

```text
fire-boy-rig/fire-boy-rigged-full.glb
```

Parsed GLB facts:

```text
nodes: 23
meshes: 1
skins: 1
skeleton joints: 21
animations: 10
```

Animation clips:

```text
Idle, Walk, Run, Jump, Wave, Cheer, Dance, Spin, Throw, Sit
```

Skeleton joints:

```text
Root
Hips
Spine
Chest
Neck
Head
Crown
Shoulder.L
UpperArm.L
LowerArm.L
Hand.L
Shoulder.R
UpperArm.R
LowerArm.R
Hand.R
UpperLeg.L
LowerLeg.L
Foot.L
UpperLeg.R
LowerLeg.R
Foot.R
```

## Current MuJoCo Body

The current MuJoCo body is generated from hand-written MJCF primitives. It does
not load `fire-boy-rigged-full.glb`.

Current MuJoCo files:

```text
fireboy-vla-physics/src/fireboy_articulated_mjcf.py
fireboy-vla-physics/build/fireboy_articulated.xml
```

The body has useful articulation, grippers, and task sites, but it is not yet
proportion-matched to the Toy Room v3 GLB.

## Measured Mismatch

The existing inspection report compares the real GLB rig with the current
MuJoCo skeleton:

```text
fireboy-vla-physics/build/inspection/fireboy_skeleton_alignment.json
```

Summary:

```text
common points: 22
max normalized point error: 0.1668
right elbow error: 0.1280
left elbow error: 0.1272
right arm length ratio, MuJoCo / GLB: 0.9314
left arm length ratio, MuJoCo / GLB: 0.9537
```

Largest visible mismatch:

```text
hands, wrists, elbows, feet, hips, and head/crown proportions
```

The overlay proves the current physics body is only a rough humanoid, not a
faithful Fire Boy physics body.

## How To Make The Physics Body Resemble Fire Boy

The correct next body-building step is:

```text
1. Parse the GLB skeleton joint positions.
2. Normalize the GLB to a consistent physics height.
3. Create MJCF bodies at those joint positions.
4. Fit collision capsules/ellipsoids from the GLB mesh bounds.
5. Assign masses by body volume and Fire Boy's toy-like proportions.
6. Add motors and joint limits that match the GLB rest pose.
7. Attach the GLB as visual mesh or render it in Three.js over the physics body.
8. Run a skeleton overlay test until GLB vs MuJoCo point error is small.
```

Suggested mass distribution for a toy-scale Fire Boy:

```text
total mass: start with 7.5 kg if matching Toy Room v3 debug readout
head + flame: 30-40%
torso/hips: 35-45%
both legs/feet: 12-18%
both arms/hands: 8-12%
```

This does not need to be perfect on the first pass. The important part is
physically stable inertia and visually faithful proportions.

## Pretrained Policy Options

We should avoid training everything from scratch if possible.

Best pretrained route:

```text
Kimodo text-to-motion
-> retarget motion to Fire Boy-like skeleton
-> ProtoMotions Mimic / MaskedMimic / GTP-style policy
-> sim-to-sim validation in Newton and/or MuJoCo
-> Fire Boy visual mesh attached in Toy Room
```

What can transfer:

```text
walk
run
turn
idle
wave
jump
sit
whole-body balance priors
```

What still needs Fire Boy/task-specific training:

```text
pick up ball
grasp with both hands
find berry
bring berry to mouth
eat berry
Toy Room object interaction
```

Reason: pretrained humanoid policies usually match a robot such as Unitree G1,
H1, SMPL, or SOMA. Fire Boy is a chibi character with different body ratios and
hand geometry. We can reuse the locomotion and motion-tracking priors, but we
still need retargeting and fine-tuning.

## Newton Recommendation

NVIDIA Newton is a good fit for cloud training because it is GPU-accelerated and
intended for robot learning. For this project:

```text
Newton / Isaac / ProtoMotions on RunPod GPU for fast parallel training
MuJoCo locally for inspection, debugging, and browser-viewable proof
Toy Room v3 for final pet demo
```

Newton is not a magic replacement for correct robot modeling. We still need the
Fire Boy physics body to be correctly proportioned first.

## True VLA Direction

The user's desired final model is:

```text
image + language + robot state -> action
```

The practical MiniCPM-based version:

```text
MiniCPM-V image/language encoder
+ robot state encoder
+ action head
-> action chunk
```

Inputs:

```text
camera image
user command text
qpos / qvel
contacts
held object state
target/object positions
previous actions
```

Outputs:

```text
joint target deltas
or end-effector deltas
or short action chunks over the next 0.5-2 seconds
```

Training data should come from successful simulation rollouts:

```text
observation image + command + robot state -> successful action
```

This means the VLA is trained after we can generate good data from physics
policies, demonstrations, IK, and/or ProtoMotions. MiniCPM can be modified with
a continuous action head, but it still needs action-labeled data.
