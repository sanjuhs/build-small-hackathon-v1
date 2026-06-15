# Where We Left Off

## 2026-06-15 Modal VLA Inference Update

The promoted frozen MiniCPM-V router is deployed and wired into the local Toy
Room app:

```text
Modal app: fireboy-vla-router
URL: https://YOUR-MODAL-WORKSPACE--fireboy-vla-router.modal.run
local app: http://127.0.0.1:65373
policy gallery: http://127.0.0.1:65373/fireboy-policy-gallery
checkpoint: Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_minicpm_vla_skill_param_head/minicpm_vla_skill_param_head.pt
```

Current local start command:

```bash
TOYBOX_VLA_ROUTER_URL='https://YOUR-MODAL-WORKSPACE--fireboy-vla-router.modal.run' \
TOYBOX_VLA_ROUTER_ACTION=1 \
PORT=65373 PID_FILE=.toybox-65373.pid LOG_FILE=.toybox-65373.log ./start.sh
```

Verified `/api/pet-action` commands:

```text
VLA router: walk to the yellow marker -> walk_to, cuda, MuJoCo success true
VLA router: run around -> run_around, cuda, MuJoCo success true
VLA router: pick up the berry -> pick_up, cuda, MuJoCo success true
VLA router: go find berry and eat it -> find_and_eat_berry, cuda, MuJoCo success true
```

Proof files:

```text
Fireboy-training-policy-vla/modal-inference-results-2026-06-15.md
Fireboy-training-policy-vla/proofs/modal-vla-router-policy-gallery.png
Fireboy-training-policy-vla/proofs/final-vla-demo-smoke.json
```

Repeat the final smoke gate with:

```bash
PYTHONPATH=fireboy-vla-physics/src \
fireboy-vla-physics/.venv/bin/python \
fireboy-vla-physics/src/final_vla_demo_smoke.py \
  --out Fireboy-training-policy-vla/proofs/final-vla-demo-smoke.json
```

Latest smoke result: `ok: true`.

Latest proof bundle:

```text
fireboy-vla-physics/build/fireboy-policy-proof-bundle.tgz
copied_count: 35
checkpoint_reference_count: 21
```

Important: the live endpoint exposes raw `neural_skill` plus stabilized served
`skill`. With blank/no camera frames, explicit command/scene intent stabilizes
the served route; with full camera frames, use `force_neural_skill: true` to
inspect the raw neural policy.

Paused because the user had to leave and internet may go offline.

## Current State

We created a new isolated planning and prototype folder:

```text
fireboy-vla-physics/
```

It now contains:

- `README.md` - summary of the Fire Boy VLA physics track.
- `PLAN.md` - 8-hour execution plan.
- `ARTICULATION_SPEC.md` - body/joint/action/observation/dataset spec.
- `CLOUD_RUNBOOK.md` - Modal-first and RunPod-backup cloud workflow.
- `requirements.txt` - robotics/prototype Python dependencies.
- `modal_jobs.py` - Modal job entrypoints.
- `src/fireboy_mjcf.py` - generates first MuJoCo/MJCF Fire Boy body.
- `src/pick_ball_env.py` - first MuJoCo environment wrapper.
- `src/ik_expert.py` - privileged IK expert demonstrator.
- `src/generate_dataset.py` - demo dataset generator.
- `src/smoke_test_env.py` - local smoke test and GIF render.
- `src/train_policy.py` - state-only behavior-cloning smoke trainer.
- `src/eval_policy.py` - state-only policy evaluator.

There were pre-existing modified files outside this folder:

```text
frontend/toybox/config.js
src/pet_actions.py
src/pet_profiles.py
```

Those were not touched by this Fire Boy VLA work.

## Local Environment

Created a separate local virtualenv:

```text
fireboy-vla-physics/.venv
```

Installed only the local smoke-test dependencies into it:

```bash
uv pip install --python fireboy-vla-physics/.venv/bin/python mujoco numpy pillow imageio scipy
```

The main project `.venv` was left alone.

## Cloud Status

RunPod CLI is available and authenticated as `runpodctl`.

Created and used a RunPod pod:

```text
pod id: vojlusilehlbpg
name: fireboy-vla-rtx6000
gpu: NVIDIA RTX 6000 Ada Generation
rate: $0.77/hr
status at handoff: stopped
```

The pod was stopped after setup/proof work to avoid idle credit burn.

Modal CLI is also installed and authenticated from this shell, but we did not need to fall back to Modal yet.

Important: local files changed after the first RunPod upload. Before the next cloud run, repack and upload again:

```bash
bash fireboy-vla-physics/scripts/pack_for_runpod.sh
```

## Last Smoke Tests

### ProtoMotions / G1

On RunPod we cloned NVlabs ProtoMotions, installed its dependencies, pulled the required Git LFS assets, and ran the official G1 pretrained MuJoCo inference path.

Result:

```text
MuJoCo simulator initialized: 39 bodies, 71 qpos, 65 qvel, 29 actuators
Evaluating policy... [Step 1] OK
```

The process was capped by a timeout so it would not run forever, but this proves the supported-humanoid locomotion/controller path works on the RTX 6000 Ada pod.

### Fire Boy MuJoCo Pickup

Initial MJCF generation works:

```bash
python3 fireboy-vla-physics/src/fireboy_mjcf.py
```

Local MuJoCo loads and renders the generated model.

Current pickup smoke result:

```text
success: True
grasped: True
final_ball_z: ~0.921
```

Meaning:

- The articulated MuJoCo body loads and runs.
- The current working prototype uses two actuated hand end-effectors and high-friction MuJoCo contact pads.
- A grip latch activates only after both hands enclose the ball; this makes pick/carry/drop reliable for dataset generation.
- This is a pragmatic simulator grasp constraint, not yet a pure contact-only learned grasp.
- The pure contact gripper still needs a better cup/cage mesh before we remove the latch.

The smoke GIF path is:

```text
fireboy-vla-physics/build/smoke/expert_smoke.gif
```

`build/` is ignored by git.

## Immediate Next Steps

When resuming, run:

```bash
fireboy-vla-physics/.venv/bin/python fireboy-vla-physics/src/smoke_test_env.py
```

Then inspect:

```text
fireboy-vla-physics/build/smoke/expert_smoke.gif
```

The next debugging targets are:

1. Replace the latch-assisted hand with a better pure-contact end effector:
   - shallow scoop/cup
   - three-finger cage
   - or MuJoCo-compliant contact pads with better vertical support
2. Keep root/base controls out of manipulation; locomotion belongs to ProtoMotions/G1.
3. Generate demos:

```bash
fireboy-vla-physics/.venv/bin/python fireboy-vla-physics/src/generate_dataset.py --num-episodes 20
```

4. Train a tiny state-only smoke policy:

```bash
uv pip install --python fireboy-vla-physics/.venv/bin/python torch torchvision
fireboy-vla-physics/.venv/bin/python fireboy-vla-physics/src/train_policy.py --max-steps 1000
```

5. Then move dataset generation/training to RunPod or Modal:

```bash
modal volume create fireboy-vla-data
modal volume create fireboy-vla-checkpoints
modal run fireboy-vla-physics/modal_jobs.py::smoke_test_env
modal run fireboy-vla-physics/modal_jobs.py::generate_dataset --num-episodes 200 --seed 1
modal run fireboy-vla-physics/modal_jobs.py::train_policy --max-steps 5000
modal run fireboy-vla-physics/modal_jobs.py::eval_policy --num-episodes 25
```

## Latest RunPod Results

RunPod RTX 6000 Ada was verified:

```text
torch 2.4.1+cu124
cuda_available True
device NVIDIA RTX 6000 Ada Generation
matmul_device cuda:0
```

Remote no-render MuJoCo skill smoke:

```text
walk/run/turn/wave/sit/dance/pick/drop routing: success
pick_ball expert smoke: success True, grasped True, ball_z ~0.921
```

Remote dataset generation:

```text
500 episodes
500 successes
success_rate 1.0
```

Remote CUDA state-only behavior cloning:

```text
rows: 7000
device: cuda
checkpoint copied locally to fireboy-vla-physics/build/checkpoints/state_policy.pt
closed-loop eval: 66/100 after richer state features
```

Interpretation: the expert/skill stack works. The learned low-level state-only BC policy is a smoke checkpoint, not final; to make the learned policy robust we need DAgger/RL or train the VLA/skill-selector above stable controllers.

## Important Design Decision

The fastest honest route is now:

```text
ProtoMotions-supported humanoid body for walking/running
Fire Boy mesh retargeted/skinned as costume
separate MuJoCo manipulation/gripper lane for pick/carry/drop
VLA/vision-language layer chooses skills and parameters
```

## Latest Overnight State - June 15, 2026

RunPod pod state:

```text
runpodctl pod list --all => []
```

No cloud pods are intentionally left running.

Best working movement policies:

```text
go_to_point:
  Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_articulated_go_to_point_clock/faithful_articulated_policy.npz
  RunPod eval: 20/20
  local runtime command test: success true
  MP4: fireboy-vla-physics/build/toy-v3-policy/articulated/faithful_learned_go_to_point.mp4

run_around:
  Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_articulated_run_around/faithful_articulated_policy.npz
  RunPod eval: 20/20
  local runtime command test: success true
  MP4: fireboy-vla-physics/build/toy-v3-policy/articulated/faithful_learned_run_around.mp4
```

Toy V3 bridge/runtime update:

```text
fireboy-vla-physics/src/pet_runtime.py routes walk/run commands to articulated policies.
src/mujoco_policy_bridge.py returns articulated policy GIF/MP4 URLs for movement commands.
```

Current local app:

```text
http://127.0.0.1:65373
policy proof gallery: http://127.0.0.1:65373/fireboy-policy-gallery
```

## Latest MiniCPM-V Router State - June 15, 2026

RunPod pod state:

```text
runpodctl pod list --all => []
```

No cloud pods are intentionally left running.

Latest successful GPU run:

```text
pod: hkk9skw9d38h5t
gpu: NVIDIA A40
status: artifacts downloaded, pod deleted
torch: 2.4.1+cu124
transformers: 5.12.0
cuda: true
device: NVIDIA A40
```

Trained model:

```text
model: openbmb/MiniCPM-V-4.6
policy: frozen MiniCPM-V encoder + skill/parameter head
input: image + language command + Fire Boy robot state
output: walk_to/run_around/pick_up/find_and_eat_berry + target parameters
checkpoint: Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_minicpm_vla_skill_param_head/minicpm_vla_skill_param_head.pt
local copy: fireboy-vla-physics/build/checkpoints/fireboy_minicpm_vla_skill_param_head/minicpm_vla_skill_param_head.pt
```

Eval:

```text
rows: 512
skill_accuracy: 1.0
param_mae: 0.017043352127075195
confusion: perfect 128/128 per skill
```

Registry/proof bundle:

```text
fireboy-vla-physics/policy_registry.json includes vla_models.minicpm_vla_skill_param_router
validate_policy_registry.py: checked_paths 40, missing_count 0, ok true
proof bundle after frozen router registration: copied_count 30, checkpoint_reference_count 15
proof bundle after LoRA router registration: copied_count 33, checkpoint_reference_count 21
focused router screenshot: fireboy-vla-physics/build/proof-gallery-screenshots/fireboy-policy-gallery-vla-router.png
```

Important interpretation:

```text
This is not yet a raw low-level all-command VLA.
It is the reliable command router layer: MiniCPM-V predicts the skill and
parameters, then the existing MuJoCo policies execute the body action.
The next expensive step should be a LoRA version of this router, not another
blind retry of the failed direct root-action go_to_point head.
```

## Latest MiniCPM-V LoRA Router State - June 15, 2026

RunPod pod state:

```text
runpodctl pod list --all => []
```

Latest successful LoRA-router GPU run:

```text
pod: xb6dv76ajw7tzq
gpu: NVIDIA A40
status: artifacts downloaded, pod deleted
torch: 2.4.1+cu124
transformers: 5.12.0
peft: 0.19.1
cuda: true
device: NVIDIA A40
```

Trained model:

```text
model: openbmb/MiniCPM-V-4.6
policy: MiniCPM-V LoRA adapter + skill/parameter head
seed: Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_minicpm_vla_skill_param_head/minicpm_vla_skill_param_head.pt
checkpoint: Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_minicpm_vla_lora_skill_param_head/minicpm_vla_lora_skill_param_head.pt
adapter: Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_minicpm_vla_lora_skill_param_head/lora_adapter/
local copy: fireboy-vla-physics/build/checkpoints/fireboy_minicpm_vla_lora_skill_param_head/minicpm_vla_lora_skill_param_head.pt
```

Eval:

```text
rows: 256
skill_accuracy: 1.0
param_mae: 0.06290113925933838
confusion: perfect 64/64 per skill
```

Important interpretation:

```text
The LoRA router training/eval path works on RunPod.
It is not promoted over the frozen router because the frozen router is more
precise on target parameters: 0.0170 MAE vs 0.0629 MAE.
Current registry validation after adding this checkpoint: checked_paths 49,
missing_count 0, ok true.
```

Policy gallery verification:

```text
registry: fireboy-vla-physics/policy_registry.json
registry validation: checked_paths 31, missing_count 0, ok true
body cards: 2
active skill cards: 4
failed direct-VLA cards: 3
videos ready: 7/7
mobile overflow: false
screenshots:
  fireboy-vla-physics/build/proof-gallery-screenshots/fireboy-policy-gallery-desktop.png
  fireboy-vla-physics/build/proof-gallery-screenshots/fireboy-policy-gallery-mobile-viewport.png
proof bundle:
  fireboy-vla-physics/build/fireboy-policy-proof-bundle/
  fireboy-vla-physics/build/fireboy-policy-proof-bundle.tgz
  copied files 25, checkpoint references 10
```

Live bridge verification:

```text
walk to the yellow marker with mujoco policy:
  success true, skill walk_to, lane mujoco_articulated_policy, registry success_rate 1.0

run around with mujoco policy:
  success true, skill run_around, lane mujoco_articulated_policy, registry success_rate 1.0

pick up the berry with mujoco policy:
  success true, skill pick_up, grasped true, intent mujoco_learned_pick_up

go find berry and eat it with mujoco policy:
  success true, skill find_and_eat_berry, eaten true
  registry status gpu_vla_checkpoint_ready_local_fallback_used
```

Next prepared VLA lane:

```text
image + language + robot state -> skill_id + skill parameters
```

Manifest:

```text
Fireboy-training-policy-vla/vla-rollouts/vla_skill_params/fireboy_vla_skill_params_allskill_3072.jsonl
rows: 3072
skills:
  walk_to: 480
  run_around: 512
  pick_up: 1028
  find_and_eat_berry: 1052
```

RunPod launcher:

```bash
bash fireboy-vla-physics/scripts/train_minicpm_vla_skill_param_head_runpod.sh
```

Promote this lane only after `eval_minicpm_vla_skill_param_head.json` shows
strong held-out skill accuracy and small target-parameter MAE. Its output should
dispatch into the already verified registry policies rather than replacing them
with unstable direct root-joint navigation.

MiniCPM-V status:

```text
MiniCPM-V LoRA manipulation checkpoint passes pick_up/go_eat_berry at 3/3 eval each.
Direct MiniCPM-V go_to_point action heads were tested more and still fail:
  absolute 1-step: 0/5
  root_velocity_v1: 0/5
  recovery root_velocity_v1: 0/5
```

Do not use the direct MiniCPM root-action navigation head for demo/submission.
Use the proven movement policies for navigation and keep MiniCPM as the
manipulation/VLA-router lane until the navigation objective is redesigned.

Do not train Fire Boy locomotion from scratch. Use G1/SMPL/ProtoMotions-compatible physics for walk/run/turn, then attach Fire Boy visually.
