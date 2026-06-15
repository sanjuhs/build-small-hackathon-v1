# Fireboy Training Policy VLA

This folder is the dedicated planning space for turning Fire Boy into a
MiniCPM-V-driven vision-language-action pet.

## Current Verified Stack

The current source of truth for policy routing is:

```text
fireboy-vla-physics/policy_registry.json
```

## Next VLA Lane: Skill + Parameters

Direct MiniCPM-V low-level navigation has failed so far, so the next robust VLA
training lane predicts:

```text
image + language + robot state -> skill_id + skill parameters
```

The first generated skill-param manifest is:

```text
Fireboy-training-policy-vla/vla-rollouts/vla_skill_params/fireboy_vla_skill_params_allskill_3072.jsonl
Fireboy-training-policy-vla/vla-rollouts/vla_skill_params/fireboy_vla_skill_params_allskill_3072.summary.json
rows: 3072
skipped images: 0
skills:
  walk_to: 480
  run_around: 512
  pick_up: 1028
  find_and_eat_berry: 1052
```

The RunPod training launcher is:

```bash
bash fireboy-vla-physics/scripts/train_minicpm_vla_skill_param_head_runpod.sh
```

Latest RunPod output:

```text
fireboy-vla-physics/build/checkpoints/fireboy_minicpm_vla_skill_param_head/minicpm_vla_skill_param_head.pt
Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_minicpm_vla_skill_param_head/
Fireboy-training-policy-vla/runpod-artifacts/fireboy-minicpm-skill-param-artifacts.tgz
GPU: NVIDIA A40
device: cuda
model: openbmb/MiniCPM-V-4.6
policy_kind: minicpm_vla_frozen_encoder_skill_param_head_v1
eval rows: 512
eval skill_accuracy: 1.0
eval param_mae: 0.017043352127075195
target_x MAE: 0.032305024564266205
target_y MAE: 0.0478343665599823
target_z MAE: 0.006528750993311405
radius MAE: 0.0038746832869946957
speed_hint MAE: 0.004880381282418966
object_is_berry MAE: 0.006836902815848589
```

This lane is accepted as the current command router. It dispatches into the
existing registry policies for MP4-proven movement/manipulation.

## Modal Live Inference

The promoted frozen router is now deployed as a Modal GPU endpoint:

```text
Modal app: fireboy-vla-router
URL: https://sanjuhs123--fireboy-vla-router.modal.run
GPU: L40S
idle scaledown window: 60 seconds
checkpoint: Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_minicpm_vla_skill_param_head/minicpm_vla_skill_param_head.pt
```

Local Toy Room wiring:

```bash
TOYBOX_VLA_ROUTER_URL='https://sanjuhs123--fireboy-vla-router.modal.run' \
TOYBOX_VLA_ROUTER_ACTION=1 \
PORT=65373 PID_FILE=.toybox-65373.pid LOG_FILE=.toybox-65373.log ./start.sh
```

Verified through `http://127.0.0.1:65373/api/pet-action`:

```text
walk to the yellow marker -> vla skill walk_to -> MuJoCo success true
run around -> vla skill run_around -> MuJoCo success true
pick up the berry -> vla skill pick_up -> MuJoCo success true
go find berry and eat it -> vla skill find_and_eat_berry -> MuJoCo success true
```

Proof note:

```text
Fireboy-training-policy-vla/modal-inference-results-2026-06-15.md
Fireboy-training-policy-vla/proofs/modal-vla-router-policy-gallery.png
Fireboy-training-policy-vla/proofs/final-vla-demo-smoke.json
```

The live endpoint reports both `neural_skill` and served `skill`. For
blank-camera requests, explicit command/scene arbitration stabilizes the served
skill and target params while keeping raw MiniCPM-V head output visible.

Repeat the final website/VLA smoke gate with:

```bash
PYTHONPATH=fireboy-vla-physics/src \
fireboy-vla-physics/.venv/bin/python \
fireboy-vla-physics/src/final_vla_demo_smoke.py \
  --out Fireboy-training-policy-vla/proofs/final-vla-demo-smoke.json
```

Latest smoke result: `ok: true`.

## LoRA Router Lane

The first MiniCPM-V LoRA version of the skill-param router was also trained on
RunPod:

```text
GPU: NVIDIA A40
pod: xb6dv76ajw7tzq
status after artifact download: deleted
script: fireboy-vla-physics/scripts/train_minicpm_vla_lora_skill_param_head_runpod.sh
trainer: fireboy-vla-physics/src/train_minicpm_vla_lora_skill_param_head.py
seed: Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_minicpm_vla_skill_param_head/minicpm_vla_skill_param_head.pt
rows: 512
LoRA rank: 8
eval rows: 256
eval skill_accuracy: 1.0
eval param_mae: 0.06290113925933838
```

Artifacts:

```text
Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_minicpm_vla_lora_skill_param_head/minicpm_vla_lora_skill_param_head.pt
Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_minicpm_vla_lora_skill_param_head/lora_adapter/
Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_minicpm_vla_lora_skill_param_head/eval_minicpm_vla_lora_skill_param_head.json
Fireboy-training-policy-vla/runpod-artifacts/fireboy-minicpm-lora-skill-param-artifacts.tgz
```

Decision:

```text
LoRA router training works and skill routing remains perfect.
Do not promote this checkpoint over the frozen router yet because its target
parameter MAE is worse: 0.0629 vs 0.0170.
```

Validate it with:

```bash
PYTHONPATH=fireboy-vla-physics/src fireboy-vla-physics/.venv/bin/python fireboy-vla-physics/src/validate_policy_registry.py
```

Latest validation:

```text
checked_paths: 31
checked_paths after router/LoRA-router registration: 49
missing_count: 0
ok: true
```

Visual proof page:

```text
http://127.0.0.1:65373/fireboy-policy-gallery
```

Saved screenshots:

```text
fireboy-vla-physics/build/proof-gallery-screenshots/fireboy-policy-gallery-desktop.png
fireboy-vla-physics/build/proof-gallery-screenshots/fireboy-policy-gallery-mobile-viewport.png
fireboy-vla-physics/build/proof-gallery-screenshots/fireboy-policy-gallery-vla-router.png
```

Build a portable proof bundle with:

```bash
PYTHONPATH=fireboy-vla-physics/src fireboy-vla-physics/.venv/bin/python fireboy-vla-physics/src/build_policy_proof_bundle.py
```

Latest bundle:

```text
fireboy-vla-physics/build/fireboy-policy-proof-bundle/
fireboy-vla-physics/build/fireboy-policy-proof-bundle.tgz
copied proof/training files: 25
copied proof/training files after router/LoRA-router registration: 33
copied proof/training files after final smoke proof registration: 35
checkpoint/archive references after router/LoRA-router registration: 21
```

Verified command paths:

```text
walk_to / run_to:
  lane: mujoco_articulated_policy
  checkpoint: Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_articulated_go_to_point_clock/faithful_articulated_policy.npz
  eval: 20/20

walk_around / run_around:
  lane: mujoco_articulated_policy
  checkpoint: Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_articulated_run_around/faithful_articulated_policy.npz
  eval: 20/20

pick_up:
  lane: minicpm_vla_lora_manipulation
  checkpoint: Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_minicpm_vla_lora_residual_512/minicpm_vla_lora_action_head.pt
  eval: 3/3

find_and_eat_berry:
  lane: minicpm_vla_lora_manipulation for GPU VLA proof
  local demo fallback: fireboy-vla-physics/checkpoints/berry_eat_wide/state_policy.npz
  eval: 3/3 MiniCPM LoRA proof, local fallback command test passes

MiniCPM-V skill-param router:
  lane: minicpm_vla_skill_param_router
  checkpoint: Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_minicpm_vla_skill_param_head/minicpm_vla_skill_param_head.pt
  eval: 512/512 skill choices correct, param MAE 0.0170
  dispatches to: walk_to, run_around, pick_up, find_and_eat_berry

MiniCPM-V LoRA skill-param router:
  lane: minicpm_vla_lora_skill_param_router
  checkpoint: Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_minicpm_vla_lora_skill_param_head/minicpm_vla_lora_skill_param_head.pt
  adapter: Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_minicpm_vla_lora_skill_param_head/lora_adapter/
  eval: 256/256 skill choices correct, param MAE 0.0629
  status: preserved, not promoted over frozen router
```

Toy V3 bridge verification:

```text
"walk to the yellow marker with mujoco policy" -> success true, animation walk
"run around with mujoco policy" -> success true, animation run
"pick up the berry with mujoco policy" -> success true, grasped true
"go find berry and eat it with mujoco policy" -> success true, local fallback eaten true
```

Generated local bridge MP4s:

```text
fireboy-vla-physics/build/toy-v3-policy/articulated/faithful_learned_go_to_point.mp4
fireboy-vla-physics/build/toy-v3-policy/articulated/faithful_learned_run_around.mp4
```

## Source Visual Rig

The current Toy Room v3 Fire Boy rig we should preserve and match is:

```text
fire-boy-rig/fire-boy-rigged-full.glb
```

This is the visual identity of Fire Boy. The physics body should be rebuilt to
match this rig first.

## Immediate Priority

Do this first:

```text
fix Fire Boy physics body first
```

That means:

```text
real Fire Boy GLB skeleton/proportions
-> matching MuJoCo/Newton articulated body
-> correct joints, link lengths, masses, collisions, contact sites
-> visual proof that physics Fire Boy resembles Toy Room v3 Fire Boy
```

We are intentionally leaving these for later:

```text
use pretrained motion priors
generate successful rollouts
fine-tune MiniCPM-style VLA action model
```

## Core Goal

The desired final model is:

```text
image + language + robot state -> action
```

More specifically:

```text
Toy Room camera image
+ user command
+ Fire Boy body state
-> Fire Boy action chunk
```

See:

```text
minicpm-v-to-vla.md
physics-body-first.md
physics-body-fix-results.md
```
