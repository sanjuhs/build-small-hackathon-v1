# Physics Body Fix Results

## Status

The Fire Boy MuJoCo articulated body has been rebuilt to match the Toy Room v3
GLB skeleton:

```text
fire-boy-rig/fire-boy-rigged-full.glb
```

## What Was Fixed

The MuJoCo body tree now uses GLB-derived joint/body points for:

```text
pelvis
spine
chest
neck
head
crown
shoulders
elbows
wrists
hands
hips
knees
ankles
feet
```

The body mass was tuned to match the Toy Room v3 debug readout:

```text
total MuJoCo body mass: 7.498 kg
```

## Proof Artifacts

Screenshots and media:

```text
Fireboy-training-policy-vla/screenshots/fixed-glb-vs-mujoco-skeleton-overlay.png
Fireboy-training-policy-vla/screenshots/fixed-mujoco-fireboy-body.png
Fireboy-training-policy-vla/screenshots/fixed-mujoco-fireboy-body.gif
Fireboy-training-policy-vla/screenshots/fixed-mujoco-fireboy-body.mp4
Fireboy-training-policy-vla/screenshots/fixed-mujoco-fireboy-pick-up.gif
Fireboy-training-policy-vla/screenshots/fixed-mujoco-fireboy-pick-up.mp4
```

Alignment report:

```text
Fireboy-training-policy-vla/screenshots/fixed-glb-vs-mujoco-skeleton-alignment.json
```

Key alignment numbers:

```text
common points: 22
max normalized point error: 0.0
right elbow normalized error: 0.0
left elbow normalized error: 0.0
right arm length ratio, MuJoCo / GLB: 1.0
left arm length ratio, MuJoCo / GLB: 1.0
```

Interaction proof:

```text
pick_up success: true
grasped: true
final berry height: 0.5204 m
```

This is only a controller/IK proof that the corrected articulated body can
reach and grip. It is not yet a trained policy and not yet a VLA.

## Important Caveat

The physics skeleton is now matched.

The visual MuJoCo render is still a primitive proxy made from spheres,
ellipsoids, capsules, and boxes. It is not yet the original cute GLB mesh.

That means:

```text
physics proportions: fixed
mass distribution: fixed enough for next-stage work
MuJoCo primitive visual: acceptable for physics proof
final Toy Room visual: should still use/attach the original GLB mesh
```

For the final demo, the right approach is:

```text
corrected MuJoCo/Newton physics body
-> joint state stream
-> fire-boy-rigged-full.glb rendered in Toy Room v3
```

So the viewer sees the real Fire Boy, while physics uses the corrected body.

## Next Gate

Do not train the MiniCPM-V VLA yet.

Next, verify this corrected body can support:

```text
standing / reset stability
hand site control
object reachability
basic contact behavior
```

Only then move to:

```text
motion priors
rollout generation
MiniCPM-V + LoRA + action head
```
