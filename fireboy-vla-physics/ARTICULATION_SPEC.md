# Fire Boy Articulation Spec

## Current Asset

Source visual asset:

```text
fire-boy-rig/fire-boy-rigged-full.glb
```

Observed skeleton:

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

The current GLB animation clips are useful as references, but the true VLA body must be driven by simulator joints/actuators.

## First Physics Body

Use a simplified MJCF body tree:

```text
world
  fireboy_root freejoint
    pelvis / hips collider
      spine joint
        chest joint
          neck joint
            head joint
            crown/flame collider
          left shoulder
            left upper arm
              left elbow
                left hand
          right shoulder
            right upper arm
              right elbow
                right hand
                  gripper palm
                  left finger
                  right finger
      left hip
        left knee
          left foot
      right hip
        right knee
          right foot
```

Use capsules and spheres first:

- torso: capsule or box
- head: sphere
- flame/crown: small capsule/sphere, low collision priority
- upper/lower arms: capsules
- hands: small spheres or boxes
- legs/feet: capsules/boxes
- gripper: small palm body plus two fingers

Do not use raw mesh collision for training. It is too fragile for the first pass.

## Joint Set

The first task only needs upper-body manipulation. Keep legs stable or weakly actuated.

Recommended first DOF:

```text
root: freejoint or assisted planar root
spine_pitch
chest_yaw
neck_yaw
head_pitch
shoulder_R_yaw
shoulder_R_pitch
shoulder_R_roll
elbow_R
hand_R_pitch
hand_R_roll
gripper_open
```

Optional after the first pass:

```text
left arm mirror joints
hips/knees/feet for locomotion
torso roll
flame/crown secondary motion
```

## Action Space

For the first VLA policy:

```text
action = [
  root_dx,
  root_dz,
  root_dyaw,
  spine_pitch_delta,
  chest_yaw_delta,
  shoulder_R_yaw_delta,
  shoulder_R_pitch_delta,
  shoulder_R_roll_delta,
  elbow_R_delta,
  hand_R_pitch_delta,
  hand_R_roll_delta,
  gripper_delta
]
```

All actions normalized to `[-1, 1]`.

Alternative action space:

```text
action = [
  right_hand_dx,
  right_hand_dy,
  right_hand_dz,
  right_hand_droll,
  right_hand_dpitch,
  right_hand_dyaw,
  gripper_open
]
```

The alternative is easier for learning but requires an IK controller inside the environment. It is acceptable as a first VLA if the policy directly outputs hand deltas and the environment converts them to joint targets. The key is that pickup is not a scripted verb; it emerges from repeated low-level control steps.

## Observation Space

Policy observation:

```json
{
  "image": "RGB frame from head or room camera",
  "instruction": "pick up the ball",
  "qpos": "joint positions",
  "qvel": "joint velocities",
  "gripper": "open/close scalar",
  "previous_action": "last normalized action"
}
```

Expert-only privileged state:

```json
{
  "ball_position": [x, y, z],
  "ball_velocity": [x, y, z],
  "right_hand_site": [x, y, z],
  "contact_state": "optional"
}
```

The policy should not require privileged ball coordinates at inference if the goal is a real VLA. The expert may use them to produce labels.

## PickBall Task

Scene:

- flat floor or table
- one ball
- Fire Boy body
- optional colored blocks as distractors
- camera mounted near head, plus external camera for debugging

Instruction set:

```text
pick up the ball
grab the yellow ball
lift the ball
hold the ball up
```

Success:

```text
ball_z > start_ball_z + 0.35
and distance(ball, right_hand_site) < 0.25
for at least N consecutive steps
```

Episode length:

```text
100-180 simulation steps for first task
```

## IK Expert

The IK expert should use privileged state and generate action labels.

Stages:

1. Move right hand above the ball.
2. Descend to ball centerline.
3. Close gripper.
4. Lift hand upward.
5. Hold ball.

The expert records every control step:

```json
{
  "episode_id": "000123",
  "step": 42,
  "instruction": "pick up the ball",
  "image_path": "images/000123/000042.jpg",
  "qpos": [],
  "qvel": [],
  "action": [],
  "reward": 0.73,
  "done": false,
  "success": false,
  "metadata": {
    "seed": 123,
    "ball_color": "yellow",
    "camera": "head"
  }
}
```

## Dataset Format

Start with simple local shards:

```text
datasets/fireboy_pick_ball/
  meta.json
  episodes/
    000000.jsonl
    000001.jsonl
  images/
    000000/
      000000.jpg
      000001.jpg
```

Then convert to a LeRobot-style or Hugging Face dataset once stable.

Minimum metadata:

```json
{
  "task": "fireboy_pick_ball",
  "simulator": "mujoco",
  "action_type": "normalized_joint_delta_or_ee_delta",
  "fps": 20,
  "camera_keys": ["head_rgb"],
  "state_keys": ["qpos", "qvel", "gripper"],
  "language_templates": [
    "pick up the ball",
    "grab the yellow ball",
    "lift the ball"
  ]
}
```

## Training Model

Minimal true VLA:

```text
image encoder + language encoder + proprio MLP
        -> transformer or MLP fusion
        -> action chunk head
```

MiniCPM-V 4.6 path:

- Use MiniCPM-V 4.6 as frozen image-language encoder first.
- Add trainable proprio encoder.
- Add trainable action head.
- Predict action chunks of 8-16 future steps.

Emergency 8-hour path:

- Use a smaller frozen vision encoder for the first smoke test.
- Keep the dataset and environment compatible with MiniCPM-V 4.6.
- Swap in MiniCPM-V once the simulator/data loop works.

## Integration Back To ToyV3

There are two integration options:

1. Mirror MuJoCo qpos onto the existing Fire Boy GLB in Three.js.
2. Run the policy in Python and stream high-level pose/action state to ToyV3 for display.

The first is more impressive. The second is faster.

ToyV3 should keep its current demo route until the physics body is stable.
