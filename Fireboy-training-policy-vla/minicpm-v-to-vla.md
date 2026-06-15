# How MiniCPM-V Becomes A Fire Boy VLA

## The Target

The true VLA target is:

```text
image + language + robot state -> action
```

For Fire Boy:

```text
what Fire Boy sees
+ what the user says
+ how Fire Boy's body is currently posed
-> what Fire Boy's body should do next
```

This is different from a normal chatbot. A chatbot outputs text. A VLA outputs
physical actions.

## What MiniCPM-V Already Gives Us

MiniCPM-V is useful because it can already process:

```text
image + text
```

For example:

```text
image: Toy Room camera frame
text: "Fire Boy, pick up the yellow ball"
```

MiniCPM-V can help understand:

```text
there is a yellow ball in front of Fire Boy
the user wants Fire Boy to pick it up
the ball is the target object
```

But MiniCPM-V does not naturally output MuJoCo joint commands.

So we do not only ask it to write a sentence. We attach a new action-producing
part to it.

## The VLA Architecture

The Fire Boy VLA model should look like this:

```text
                 camera image
                      |
                      v
              MiniCPM-V vision encoder

                 user command
                      |
                      v
             MiniCPM-V language encoder

              Fire Boy robot state
                      |
                      v
               robot state encoder

                      |
                      v
        fused vision-language-state features

                      |
                      v
              continuous action head

                      |
                      v
          joint targets / action chunk
```

In compact form:

```text
MiniCPM-V(image, text) + RobotStateEncoder(state) -> ActionHead -> action
```

## What Is Robot State?

Robot state is the body information the model needs so it knows what action is
physically possible right now.

For Fire Boy in MuJoCo/Newton, robot state should include:

```text
root position
root rotation
joint angles
joint velocities
hand positions
foot contacts
body orientation
held object state
nearby object positions
previous action
```

Example:

```json
{
  "root_position": [0.1, 0.0, 0.6],
  "root_rotation": [0.0, 0.0, 0.1],
  "joint_angles": [0.03, -0.12, 0.44],
  "joint_velocities": [0.1, 0.0, -0.2],
  "left_hand_position": [0.35, 0.18, 0.52],
  "right_hand_position": [0.34, -0.18, 0.52],
  "target_object": "yellow_ball",
  "target_position": [0.8, 0.0, 0.2],
  "is_holding_object": false
}
```

The image tells the model what the room looks like. The language tells it what
the user wants. The robot state tells it what Fire Boy's body is currently
doing.

## What Is The Action?

The action is not text like:

```text
"I will pick up the ball"
```

The action is numeric control output.

Possible action formats:

```text
joint target positions
joint target deltas
joint torques
end-effector target deltas
short action chunks
```

For Fire Boy, the safest first version is usually:

```text
joint target deltas or joint target positions
```

Example output:

```json
{
  "next_10_steps": [
    {
      "shoulder_L_pitch": 0.12,
      "elbow_L": 0.18,
      "wrist_L_pitch": -0.04,
      "shoulder_R_pitch": 0.11,
      "elbow_R": 0.17,
      "wrist_R_pitch": -0.05,
      "hip_L_pitch": 0.03,
      "hip_R_pitch": -0.03
    }
  ]
}
```

This is why we call it:

```text
continuous action
```

The output numbers are continuous values, not words or categories.

## What Is An Action Head?

The action head is a small neural network attached after the MiniCPM-V features.

MiniCPM-V produces an internal feature vector that represents the image and
language. The robot state encoder produces another feature vector. We combine
them, then the action head maps that combined vector to actions.

Mathematically:

```text
z_vl = MiniCPM_V(image, text)
z_state = StateEncoder(robot_state)
z = concat(z_vl, z_state)
action = ActionHead(z)
```

Where:

```text
z_vl      = vision/language features
z_state   = body/proprioception features
z         = combined features
action    = joint commands or action chunk
```

The action head can be a simple MLP at first:

```text
Linear -> activation -> Linear -> activation -> Linear -> action vector
```

Later it can be a diffusion action head or transformer action head, similar in
spirit to modern VLA systems.

## What Does "Action Chunk" Mean?

Instead of predicting only one tiny action for the next physics timestep, the
model predicts a short sequence:

```text
next 0.5 seconds of actions
```

For example, if control runs at 20 Hz:

```text
10 future actions = 0.5 seconds
```

This is useful because body motion is continuous. Fire Boy should not decide
from scratch every millisecond. He should produce a smooth short movement:

```text
reach toward ball
close hands
lift slightly
stabilize
```

Then the model replans again from the new image and body state.

## How Training Works

To train the VLA, we need examples like:

```text
input:
  image
  command
  robot state

target:
  action that worked
```

This is supervised learning over successful behavior.

The dataset row looks like:

```json
{
  "image": "frame_000123.png",
  "language": "Fire Boy, pick up the yellow ball",
  "robot_state": {
    "joint_angles": "...",
    "joint_velocities": "...",
    "contacts": "..."
  },
  "action": {
    "joint_target_delta_chunk": "..."
  }
}
```

The model predicts an action. We compare it to the correct action from the
dataset.

Loss:

```text
loss = predicted_action - successful_action
```

Usually this is an L1 or L2 loss:

```text
L2 loss = mean((predicted_action - target_action)^2)
```

Then backpropagation changes the action head, state encoder, and optionally part
of MiniCPM-V so the next prediction is closer.

## Do We Train All Of MiniCPM-V?

Not at first.

The practical staged approach:

```text
1. Freeze most of MiniCPM-V.
2. Train the robot state encoder and action head.
3. Add LoRA adapters to MiniCPM-V if needed.
4. Fine-tune only small parts of MiniCPM-V.
5. Keep full-model fine-tuning as a later expensive option.
```

This is better because MiniCPM-V already understands images and text. We mainly
need to teach it how those features connect to Fire Boy's body actions.

## Why We Must Fix Fire Boy Physics First

The VLA needs action labels. Those labels must control the actual Fire Boy body.

If the physics body is wrong, the dataset is wrong.

Bad pipeline:

```text
wrong MuJoCo body
-> wrong actions
-> VLA learns wrong body behavior
-> Toy Room Fire Boy still looks broken
```

Correct pipeline:

```text
Fire Boy GLB-matched physics body
-> successful physics rollouts
-> image/state/action dataset
-> MiniCPM-V action fine-tuning
-> Toy Room Fire Boy performs grounded actions
```

So the first real implementation milestone is not VLA training. It is:

```text
make Fire Boy's physics body match fire-boy-rig/fire-boy-rigged-full.glb
```

## Final Mental Model

MiniCPM-V gives Fire Boy perception and language understanding.

The robot state encoder gives Fire Boy body awareness.

The action head gives Fire Boy physical control.

Together:

```text
MiniCPM-V + robot state encoder + action head = Fire Boy VLA
```

But the model can only learn good physical action after the physics body is
correct.
