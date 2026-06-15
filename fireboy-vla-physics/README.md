# Fire Boy VLA Physics Track

This folder is the execution plan for turning Fire Boy from a rendered toy-room character into a physically articulated robot body that can be trained as a vision-language-action policy.

## Current Working Demo

The current local smoke slice is a learned MuJoCo berry-eating controller on the legacy bimanual harness:

```bash
bash fireboy-vla-physics/scripts/run_local_demo.sh
```

It routes pet commands locally and renders a learned-policy rollout to:

```text
fireboy-vla-physics/build/submission/learned_berry_eat.gif
```

The standalone MuJoCo viewer route is:

```text
http://127.0.0.1:65372/mujoco-policy
```

It shows the legacy MuJoCo rest body, the IK expert rollout, and the learned rollout.

The newer articulated proof is also exposed from that page through `Run Articulated Fireboy Proof`. It now uses Fireboy-like proportions measured from the real GLB: huge round head, short rounded body, short arms, tiny legs/feet, and small paw/gripper helpers. It generates:

```text
fireboy-vla-physics/build/articulated/fireboy_articulated_body.mp4
fireboy-vla-physics/build/articulated/fireboy_articulated_run_around.mp4
fireboy-vla-physics/build/articulated/fireboy_articulated_pick_up.mp4
fireboy-vla-physics/build/articulated/fireboy_articulated_go_eat_berry.mp4
```

That body is a connected MuJoCo character with root, spine, chest, neck/head, shoulder/elbow/wrist, gripper finger, hip/knee/ankle joints. It proves the faithful body shape and controller lanes, but it is not yet a trained general VLA policy or a ProtoMotions locomotion policy.

Do not train new serious policies on the older `fireboy_two_hand_pick_ball.xml` harness or the first stretched articulated body. Use `fireboy_articulated.xml` after regenerating it from `fireboy_articulated_mjcf.py`.

The new faithful-body retraining entrypoint is:

```bash
bash fireboy-vla-physics/scripts/train_faithful_articulated_runpod.sh
```

That script generates command-conditioned demonstrations for `pick_up`, `go_eat_berry`, and `run_around`, trains `faithful_articulated_policy.pt`, evaluates all three commands, and exports `faithful_articulated_policy.npz`.

Latest A6000 run status:

```text
faithful expert demos: pick 600/600, eat 599/600, run 600/600
mixed learned policy:  pick 20/20, eat 0/20, run 0/20
skill learned policies: pick 15/20, eat 0/20, run 18/20
phase eat BC: 0/30
phase/clock eat BC: 0/30
```

So the body and expert data are ready, and learned pick/run have real signal. Learned eat is not solved by plain behavior cloning yet; use the expert/controller proof for eat until we add DAgger, recovery rollouts, or RL fine-tuning.
The phase and clocked action-chunk attempts did not fix eat; they mostly fail to establish a stable grasp under closed-loop rollout. The next serious learned-eat step is recovery/DAgger data or RL fine-tuning around the grasp-to-mouth transition, not more plain one-shot BC.

The downloaded checkpoints can be previewed locally without torch via:

```bash
MUJOCO_GL=glfw fireboy-vla-physics/.venv/bin/python \
  fireboy-vla-physics/src/rollout_articulated_numpy_policy.py --task run_around
```

The latest failed phase-clock eat preview is:

```text
fireboy-vla-physics/build/articulated_policy_phase_clock/faithful_learned_go_eat_berry.mp4
```

For submission and retraining details, start here:

```text
fireboy-vla-physics/SUBMISSION_README.md
```

The included local checkpoint is:

```text
fireboy-vla-physics/checkpoints/berry_eat_wide/state_policy.npz
```

This is a learned state-action MuJoCo policy plus a pet skill router. It is not yet a fully generalized MiniCPM-V end-to-end VLA, but the data/action loop is set up for that next stage.

The current Toy Room v3 is a strong front-end and asset source, but it is not yet a VLA training environment. It sends scene/camera state to a model, receives high-level PET action JSON, and then renderer code performs commands such as pickup, carry, run, and fireball. The Fire Boy GLB is a rigged visual asset with a useful humanoid skeleton and clips, while the live physics body is currently a simplified balance body.

The target for this track is different:

```text
camera image + language command + Fire Boy joint/proprio state
        -> learned action policy
        -> joint targets / root targets / gripper command
        -> physics simulator step
        -> next observation
```

## Short Verdict

Yes, this is buildable. The practical 8-hour target is a narrow true-VLA vertical slice:

1. Build a first Fire Boy articulated body in MuJoCo, using the existing skeleton proportions.
2. Add a right-hand gripper or invisible pinch tool to make ball pickup physically trainable.
3. Create a `PickBall` task with randomized ball positions and camera views.
4. Generate expert demonstrations with IK and a state machine.
5. Save image, language, proprioception, action, reward, and success data.
6. Train a tiny action policy or action head as a smoke test.

The 8-hour target is not a fully general humanoid VLA. It is the smallest honest version of the real thing: direct continuous actions in a physics simulator, no scripted renderer pickup.

## Why MuJoCo First

MuJoCo is the fastest route for this specific goal because it gives us articulated bodies, joints, contacts, actuators, cameras, and headless data generation without moving the whole web app into a heavy robotics stack.

ProtoMotions and Kimodo are still useful, but for a different layer:

- MuJoCo: best first target for articulated body plus manipulation.
- ProtoMotions: useful once we need stable learned humanoid locomotion or motion imitation.
- Kimodo: useful for generating/reference humanoid motions, then retargeting them into a physics controller.
- ToyV3/Three.js: useful for display, UX, and later playback/inference integration.

## Current Local Checks

- Modal CLI is installed: `modal client version: 1.5.0`.
- `runpod` / `runpodctl` is not on PATH in this shell.
- Fire Boy rig asset exists at `fire-boy-rig/fire-boy-rigged-full.glb`.
- Fire Boy GLB contains a 21-bone humanoid skeleton and 10 animation clips.

## Main Files In This Folder

- `PLAN.md`: 8-hour execution plan and go/no-go milestones.
- `ARTICULATION_SPEC.md`: exact body, joints, sensors, action space, and dataset shape.
- `CLOUD_RUNBOOK.md`: Modal-first and RunPod-backup cloud workflow.

## Sources Checked

- Modal GPU docs: https://modal.com/docs/guide/gpu
- Modal Volumes docs: https://modal.com/docs/guide/volumes
- RunPod CLI docs: https://docs.runpod.io/runpodctl/overview
- RunPod Pod management docs: https://docs.runpod.io/pods/manage-pods
- RunPod file transfer docs: https://docs.runpod.io/pods/storage/transfer-files
- MuJoCo: https://mujoco.org/
- ProtoMotions: https://github.com/NVlabs/ProtoMotions
- Kimodo: https://github.com/nv-tlabs/kimodo
- MiniCPM-V 4.6: https://huggingface.co/openbmb/MiniCPM-V-4.6
