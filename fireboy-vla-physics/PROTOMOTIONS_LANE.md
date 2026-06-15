# ProtoMotions Locomotion Lane

## Why Use This Lane

We should not train walk/run from scratch inside the hackathon window. ProtoMotions is the right source of a physics locomotion prior because it is built for simulated humanoids and humanoid robots.

The practical approach is:

```text
supported humanoid robot/controller
  -> walk/run/turn/sit/wave/dance/recover
  -> Fire Boy visual mesh attached/retargeted as costume
  -> pet skill policy chooses which motion/controller to invoke
```

This keeps walking/running realistic without making our custom Fire Boy skeleton solve all humanoid dynamics on day one.

## What ProtoMotions Gives Us

From the official README:

- GPU-accelerated simulated humanoid learning.
- Motion learning from large motion datasets.
- Retargeting via PyRoki.
- G1/H1-style robot examples and sim-to-sim testing.
- Kimodo text-to-motion data preparation path.
- Custom robot path using MuJoCo XML, robot config, and factory registration.

## What We Should Do First

1. Run a supported ProtoMotions quick start on RunPod.
2. Export or render a supported humanoid walking/running.
3. Attach Fire Boy as visual costume:
   - torso shell follows pelvis/chest
   - head/flame follows head
   - arms/legs follow corresponding humanoid links
4. Use the supported controller for:
   - walk around
   - run around
   - come here
   - turn to object
   - recover balance

## What We Should Not Do First

Do not immediately make a custom Fire Boy ProtoMotions robot and train it from scratch.

That path requires:

- robust Fire Boy MJCF body
- physical joint ranges
- mass/inertia tuning
- retargeted motion dataset
- reward/controller tuning
- training time

We can do it later, but it is too risky before a deadline.

## How It Connects To The Pet Brain

The pet brain should output:

```json
{
  "skill": "walk_around",
  "params": {
    "radius": 1.1,
    "speed": 0.9,
    "style": "happy"
  }
}
```

The locomotion lane executes the skill and logs:

```text
qpos, qvel, target motion, action, camera frame, success
```

The manipulation lane handles:

```text
reach
pick
carry
drop
inspect
```

## Later Custom Fire Boy Robot

Once the supported humanoid pet works:

1. Add `fireboy.xml` to ProtoMotions robot assets.
2. Write `fireboy.py` robot config.
3. Register it in the factory.
4. Retarget G1/SMPL motions to Fire Boy.
5. Train a tracking policy.
6. Replace supported humanoid body with native Fire Boy physics.

## Decision For This Project

Use ProtoMotions for locomotion, not object manipulation.

Use MuJoCo/IK/manipulation policy for pick/carry/drop.

Use MiniCPM-V/skill policy for command understanding and skill selection.
