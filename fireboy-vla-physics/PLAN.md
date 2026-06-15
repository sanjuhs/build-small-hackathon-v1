# Fire Boy VLA Physics Plan

## Objective

Build the first true physics/VLA training slice for Fire Boy:

```text
"pick up the ball"
  -> camera + language + proprioception
  -> learned continuous actions
  -> articulated Fire Boy moves hand/gripper in physics
  -> ball is lifted
```

This plan intentionally avoids ToyV3's current scripted pickup path. The expert generator may use IK to create demonstrations, but the trained policy should output low-level targets rather than `interaction.verb = pickup`.

## 8-Hour Success Definition

The honest 8-hour target is:

- A MuJoCo XML/MJCF Fire Boy body with root, torso, head, arms, legs, right-hand end effector, and simple gripper.
- A headless `PickBall` environment that resets randomized scenes.
- An IK expert that produces successful demonstrations.
- A dataset of at least 500-2000 episodes, depending on cloud speed.
- A minimal policy training run that predicts action chunks from image/language/proprio state.
- A local or cloud inference smoke test showing the policy can move toward and lift the ball in at least one seeded scene.

If time is tighter, the fallback success is:

- Articulated body plus IK expert plus dataset generation, with training queued on cloud.

## What We Should Not Try In 8 Hours

- Full generalist humanoid locomotion.
- Multi-character Toy Room conversion.
- Perfect mesh-to-collider automatic conversion.
- End-to-end MiniCPM-V full fine-tuning.
- Real-world robot transfer.
- Replacing the entire ToyV3 frontend.

Those are follow-on steps once the vertical slice is alive.

## Simulator Choice

Use MuJoCo first.

Reasons:

- Fast to author articulated bodies and contacts.
- Good Python APIs for headless stepping and rendering.
- Easy to run on Modal or RunPod.
- Easier than Isaac Lab for a fast custom-body proof.
- Easier than ProtoMotions for manipulation-first work.

Use ProtoMotions later if Fire Boy must walk, recover balance, or imitate generated humanoid motions. Use Kimodo later to generate motion references that ProtoMotions can track.

## Architecture

```text
assets/fire-boy-rigged-full.glb
        |
        v
extract skeleton proportions
        |
        v
fireboy.mjcf.xml
        |
        v
PickBallEnv
  obs:
    - RGB camera
    - optional depth
    - qpos/qvel
    - gripper state
    - language instruction
  action:
    - root planar velocity or target
    - torso/head/arm joint target deltas
    - gripper open/close
        |
        v
IK expert demonstrations
        |
        v
VLA dataset
        |
        v
MiniCPM-V 4.6 backbone + action head
        |
        v
policy inference in MuJoCo
```

## Milestones

### Hour 0-1: Skeleton and MJCF Body

Deliverables:

- Extract bone names and approximate rest-pose transforms from the GLB.
- Create `fireboy.mjcf.xml` with simplified colliders.
- Add cameras: world camera and head/agent camera.

Go/no-go:

- MuJoCo loads the model.
- `mj_step` runs without exploding.
- A rendered frame shows a recognizable body layout.

### Hour 1-2: Actuators and Gripper

Deliverables:

- Add joint limits and position actuators.
- Add a right-hand end-effector site.
- Add a tiny invisible/visible gripper attached to the right hand.

Important:

Fire Boy has no fingers in the current skeleton. For real pickup, we need either:

- a small two-finger pinch gripper attached to `Hand.R`, or
- a suction/palm tool with an actuator and contact constraint.

The first 8-hour version should use a simple pinch gripper. It is still direct physical control because the policy commands the gripper and contacts lift the ball.

Go/no-go:

- Directly setting joint targets moves the hand.
- Gripper can physically contact and lift a ball in a hand-coded test.

### Hour 2-3: PickBall Environment

Deliverables:

- `reset(seed)` randomizes ball position, Fire Boy root pose, camera light, colors.
- `step(action)` applies targets and returns obs/reward/done/info.
- Success metric: ball height above threshold and near hand.

Reward sketch:

```text
+ reach hand toward ball
+ close gripper near ball
+ lift ball above table/floor
- drop ball
- joint limit abuse
- excessive instability
```

Go/no-go:

- Environment can run 100 episodes headless.
- Expert can query privileged ball position.

### Hour 3-4: IK Expert

Deliverables:

- IK targets:
  1. pregrasp above ball
  2. descend
  3. close gripper
  4. lift
  5. hold
- Record every frame:
  - RGB
  - instruction
  - qpos/qvel
  - action
  - reward
  - success
  - metadata

Go/no-go:

- At least 70 percent expert success over randomized starts.

### Hour 4-5: Cloud Dataset Generation

Deliverables:

- Modal job or RunPod pod command to generate many episodes.
- Dataset written as compressed chunks.
- A small local validation script loads one chunk and replays actions.

Go/no-go:

- 500+ successful episodes saved.

### Hour 5-7: Minimal VLA Training

Fast training target:

- Freeze vision-language backbone at first.
- Train an action head / policy adapter.
- Use action chunking, for example predict next 8-16 action steps.

Inputs:

- image embedding
- language embedding
- qpos/qvel/proprio vector

Output:

- normalized action chunk

Loss:

- behavior cloning MSE or discretized action token cross entropy.

Go/no-go:

- Training loss drops.
- One seeded rollout reaches toward the ball.

### Hour 7-8: Smoke Test and Integration Plan

Deliverables:

- Rendered rollout video or frame sequence.
- Metrics:
  - expert success rate
  - policy success rate on small seed set
  - avg final ball height
  - avg hand-ball distance
- Next integration target:
  - ToyV3 calls policy server for actions.
  - ToyV3 displays the MuJoCo rollout, or mirrors qpos onto the Fire Boy GLB.

## What I Need From You

Required:

- Confirm we should use MuJoCo first.
- Confirm cloud priority: Modal first, RunPod backup, or RunPod first.
- Give permission to spend GPU time on dataset generation and short training.
- If using RunPod from this machine, install/configure `runpodctl` or provide the PATH where it lives.

Helpful:

- Preferred GPU budget or max spend.
- Whether MiniCPM-V 4.6 must be used in the first training run, or whether a smaller frozen vision encoder is acceptable for the first smoke test.
- Whether the gripper can be an invisible training attachment on Fire Boy's right hand.

## Biggest Risks

1. Mesh-to-physics mismatch.
   - Mitigation: use simplified capsules/spheres, not mesh collision.

2. Fire Boy has no hand/finger skeleton.
   - Mitigation: add a simple training gripper under the right hand.

3. Full MiniCPM-V fine-tuning may be too slow for 8 hours.
   - Mitigation: freeze MiniCPM-V or use image embeddings first, then train the action head.

4. Humanoid balance and walking can consume the whole schedule.
   - Mitigation: make root motion controlled/assisted for the first pick task, then replace with learned locomotion later.

5. Policy may imitate poorly with too few demos.
   - Mitigation: use privileged IK expert to generate many simple successful demonstrations with domain randomization.

## Final Answer To "Can We Actually Do Phase 5?"

Yes, if Phase 5 means "make Fire Boy physically articulated and train/direct-control a first pick-ball policy."

No, if Phase 5 means "in 8 hours, produce a robust general humanoid VLA that walks around, manipulates arbitrary objects, and replaces the whole ToyV3 action system."

The right move is a narrow but real VLA slice, then expand.
