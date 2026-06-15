# RunPod Results: Fire Boy Movement And VLA Gates

Date: 2026-06-15

## RunPod Status

All RunPod pods have been stopped/deleted after artifact download.

```text
runpodctl pod list --all -> []
```

Old exited pods deleted:

```text
9obtpq0emwxfrp
1w1hzvr8kf9dwc
borvhykzelprh8
46v22g62dytxww
6pqr6nf9vvqbmt
tdseqidwwxj154
kc8hitul9nsx23
vojlusilehlbpg
csm0fvp9ox47a9
```

## Main Artifact Folder

```text
Fireboy-training-policy-vla/runpod-artifacts
```

## Local Proof Gallery

The latest registry-backed visual proof page is:

```text
http://127.0.0.1:65373/fireboy-policy-gallery
```

The page reads:

```text
fireboy-vla-physics/policy_registry.json
```

Validation:

```text
checked_paths: 40
checked_paths after LoRA-router registration: 49
missing_count: 0
ok: true
```

Browser verification:

```text
body proof cards: 2
VLA router cards: 1
VLA router cards after LoRA-router registration: 2
active skill cards: 4
failed direct-VLA experiment cards: 3
videos ready: 7/7
mobile horizontal overflow: false
```

Screenshots:

```text
fireboy-vla-physics/build/proof-gallery-screenshots/fireboy-policy-gallery-desktop.png
fireboy-vla-physics/build/proof-gallery-screenshots/fireboy-policy-gallery-mobile-viewport.png
fireboy-vla-physics/build/proof-gallery-screenshots/fireboy-policy-gallery-vla-router.png
```

## Skill-Param VLA Lane Prepared

Why this exists:

```text
Direct MiniCPM-V low-level go_to_point heads failed closed-loop.
The next robust VLA lane predicts a stable pet skill plus parameters, then
dispatches into the verified MuJoCo policies/controllers.
```

Model target:

```text
image + language + robot state -> skill_id + target parameters
```

Generated manifest:

```text
Fireboy-training-policy-vla/vla-rollouts/vla_skill_params/fireboy_vla_skill_params_allskill_3072.jsonl
Fireboy-training-policy-vla/vla-rollouts/vla_skill_params/fireboy_vla_skill_params_allskill_3072.summary.json
rows: 3072
skipped images: 0
action_type: skill_parameters_v1
```

Skill distribution:

```text
pick_up: 1028
find_and_eat_berry: 1052
run_around: 512
walk_to: 480
```

Added scripts:

```text
fireboy-vla-physics/src/build_vla_skill_param_manifest.py
fireboy-vla-physics/src/train_minicpm_vla_skill_param_head.py
fireboy-vla-physics/src/eval_minicpm_vla_skill_param_head.py
fireboy-vla-physics/scripts/train_minicpm_vla_skill_param_head_runpod.sh
```

RunPod command:

```bash
bash fireboy-vla-physics/scripts/train_minicpm_vla_skill_param_head_runpod.sh
```

Verification done locally:

```text
Python compile: pass
RunPod shell syntax: pass
RunPod pods: []
```

## MiniCPM-V Skill-Param Router Trained On RunPod

Successful RunPod GPU run:

```text
pod: hkk9skw9d38h5t
gpu: NVIDIA A40
status after artifact download: deleted
torch: 2.4.1+cu124
transformers: 5.12.0
cuda_available: true
device: NVIDIA A40
model: openbmb/MiniCPM-V-4.6
policy kind: minicpm_vla_frozen_encoder_skill_param_head_v1
```

This is the current reliable VLA router:

```text
image + language + Fire Boy robot state -> skill_id + target parameters
```

Training manifest:

```text
rows: 3072
skipped: 0
skills:
  pick_up: 1028
  find_and_eat_berry: 1052
  run_around: 512
  walk_to: 480
```

Training result:

```text
rows used: 768
train rows: 645
validation rows: 123
val skill_accuracy: 0.9999999403953552
val param_mae: 0.06423188000917435
```

Separate eval result:

```text
eval rows: 512
cache hits: 512
skill_accuracy: 1.0
param_mae: 0.017043352127075195
target_x MAE: 0.032305024564266205
target_y MAE: 0.0478343665599823
target_z MAE: 0.006528750993311405
radius MAE: 0.0038746832869946957
speed_hint MAE: 0.004880381282418966
object_is_berry MAE: 0.006836902815848589
confusion matrix: perfect 128/128 for each of walk_to, run_around, pick_up, find_and_eat_berry
```

Artifacts:

```text
Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_minicpm_vla_skill_param_head/minicpm_vla_skill_param_head.pt
fireboy-vla-physics/build/checkpoints/fireboy_minicpm_vla_skill_param_head/minicpm_vla_skill_param_head.pt
Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_minicpm_vla_skill_param_head/train_minicpm_vla_skill_param_head.json
Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_minicpm_vla_skill_param_head/eval_minicpm_vla_skill_param_head.json
Fireboy-training-policy-vla/runpod-artifacts/fireboy-minicpm-skill-param-artifacts.tgz
```

Registry/proof bundle update:

```text
fireboy-vla-physics/policy_registry.json now has vla_models.minicpm_vla_skill_param_router
validate_policy_registry.py -> checked_paths 40, missing_count 0, ok true
build_policy_proof_bundle.py -> copied_count 30, checkpoint_reference_count 15
after LoRA-router registration -> copied_count 33, checkpoint_reference_count 21
```

## MiniCPM-V LoRA Skill-Param Router Trained On RunPod

Successful RunPod GPU run:

```text
pod: xb6dv76ajw7tzq
gpu: NVIDIA A40
status after artifact download: deleted
torch: 2.4.1+cu124
transformers: 5.12.0
peft: 0.19.1
cuda_available: true
device: NVIDIA A40
model: openbmb/MiniCPM-V-4.6
policy kind: minicpm_vla_lora_skill_param_head_v1
seed checkpoint: fireboy_minicpm_vla_skill_param_head
```

Training result:

```text
rows used: 512
train rows: 430
validation rows: 82
LoRA rank: 8
train-val skill_accuracy: 0.9999999403953552
train-val param_mae: 0.05892230197787285
```

Separate eval result:

```text
eval rows: 256
skill_accuracy: 1.0
param_mae: 0.06290113925933838
target_x MAE: 0.10424776375293732
target_y MAE: 0.21497729420661926
target_z MAE: 0.018535444512963295
radius MAE: 0.009284647181630135
speed_hint MAE: 0.014032401144504547
object_is_berry MAE: 0.01632928103208542
confusion matrix: perfect 64/64 for each of walk_to, run_around, pick_up, find_and_eat_berry
```

Artifacts:

```text
Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_minicpm_vla_lora_skill_param_head/minicpm_vla_lora_skill_param_head.pt
Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_minicpm_vla_lora_skill_param_head/lora_adapter/
Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_minicpm_vla_lora_skill_param_head/train_minicpm_vla_lora_skill_param_head.json
Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_minicpm_vla_lora_skill_param_head/eval_minicpm_vla_lora_skill_param_head.json
Fireboy-training-policy-vla/runpod-artifacts/fireboy-minicpm-lora-skill-param-artifacts.tgz
```

Decision:

```text
This proves the MiniCPM-V LoRA router training/eval path works on RunPod.
It is not promoted over the frozen router because its parameter MAE is worse
than the frozen router eval: 0.0629 vs 0.0170.
```

## Image-Rich VLA Rollout Manifest

First RunPod-built VLA manifest:

```text
pod: tja5pqp6w3h8tz
gpu: NVIDIA RTX 6000 Ada Generation
status after run: deleted
run_id: 20260615-021838
episodes: 64 total, 16 per task
images: 2368
manifest rows: 2368
image stride: 5
manifest stride: 5
action chunk steps: 10
```

Files:

```text
Fireboy-training-policy-vla/vla-rollouts/fireboy-vla-rollouts-20260615-021838.tgz
Fireboy-training-policy-vla/vla-rollouts/datasets/fireboy_vla_images_20260615-021838
Fireboy-training-policy-vla/vla-rollouts/vla_manifests/fireboy_vla_action_chunks_20260615-021838.jsonl
Fireboy-training-policy-vla/vla-rollouts/vla_manifests/fireboy_vla_action_chunks_20260615-021838.summary.json
```

Validation:

```text
local image paths rewritten from RunPod paths: yes
first manifest image exists locally: yes
manifest row shape: image_path + instruction + robot_state + action_chunk
```

## VLA Manifest Action-Head Baseline

RunPod baseline:

```text
pod: t0029e9cahpr20
gpu: NVIDIA GeForce RTX 4090
status after run: deleted
training rows: 2368
checkpoint: fireboy-vla-physics/build/checkpoints/fireboy_vla_manifest_action_head/vla_manifest_action_head.pt
```

This model trains from the VLA JSONL manifest shape, but it does not encode
pixels yet. It is the baseline that proves the action-head training path before
MiniCPM-V LoRA.

Eval:

```text
pick_up:       2/8
go_eat_berry: 2/8
run_around:   8/8
go_to_point:  7/8
```

Files:

```text
Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_vla_manifest_action_head/vla_manifest_action_head.pt
Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_vla_manifest_action_head/eval_pick_up_manifest_head.json
Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_vla_manifest_action_head/eval_go_eat_berry_manifest_head.json
Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_vla_manifest_action_head/eval_run_around_manifest_head.json
Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_vla_manifest_action_head/eval_go_to_point_manifest_head.json

Fireboy-training-policy-vla/runpod-artifacts/runpod_artifacts/vla_manifest_head/faithful_chunk_pick_up_policy_ep000.mp4
Fireboy-training-policy-vla/runpod-artifacts/runpod_artifacts/vla_manifest_head/faithful_chunk_go_eat_berry_policy_ep000.mp4
Fireboy-training-policy-vla/runpod-artifacts/runpod_artifacts/vla_manifest_head/faithful_chunk_run_around_policy_ep000.mp4
Fireboy-training-policy-vla/runpod-artifacts/runpod_artifacts/vla_manifest_head/faithful_chunk_go_to_point_policy_ep000.mp4
```

Interpretation:

- The VLA manifest/action-head training path works.
- The tiny mixed image manifest is enough for locomotion/navigation rehearsal.
- It is too sparse for reliable manipulation.
- For MiniCPM-V LoRA, pickup/eat need either a larger manipulation-heavy image
  manifest or distillation from the dense 20/20 action-chunk policies.

## Manipulation-Heavy VLA Manifest And Head

Focused RunPod image manifest:

```text
pod: 6yxsueuiebl28k
gpu: NVIDIA GeForce RTX 4090
status after run: deleted
run_id: manip-20260615-025016
tasks: pick_up, go_eat_berry
episodes: 144 total, 72 per task
images: 6192
manifest rows: 6192
pick_up rows: 2664
go_eat_berry rows: 3528
missing local images: 0
```

Files:

```text
Fireboy-training-policy-vla/vla-rollouts/fireboy-vla-rollouts-manip-20260615-025016.tgz
Fireboy-training-policy-vla/vla-rollouts/datasets/fireboy_vla_images_manip-20260615-025016
Fireboy-training-policy-vla/vla-rollouts/vla_manifests/fireboy_vla_action_chunks_manip-20260615-025016.jsonl
Fireboy-training-policy-vla/vla-rollouts/vla_manifests/fireboy_vla_action_chunks_manip-20260615-025016.summary.json
```

Focused manifest-head RunPod eval:

```text
pod: vromw5jt46cjew
gpu: NVIDIA GeForce RTX 4090
status after run: deleted
training rows: 6192
task filter: pick_up, go_eat_berry
pick_up:       12/12
go_eat_berry: 12/12
```

Files:

```text
Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_vla_manifest_action_head_manip/vla_manifest_action_head.pt
Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_vla_manifest_action_head_manip/eval_pick_up_manifest_head.json
Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_vla_manifest_action_head_manip/eval_go_eat_berry_manifest_head.json

Fireboy-training-policy-vla/runpod-artifacts/runpod_artifacts/fireboy_vla_manifest_action_head_manip/faithful_chunk_pick_up_policy_ep000.mp4
Fireboy-training-policy-vla/runpod-artifacts/runpod_artifacts/fireboy_vla_manifest_action_head_manip/faithful_chunk_go_eat_berry_policy_ep000.mp4
```

Interpretation:

- The weak `2/8` manipulation result was a data problem, not a fundamental
  action-head problem.
- A manipulation-heavy VLA manifest restored reliable learned pickup/eat
  behavior.
- This is the right dataset shape to feed into the MiniCPM-V 4.6
  LoRA/action-head stage.

## MiniCPM-V 4.6 Frozen-Encoder Action Head

First real MiniCPM-V action-head smoke:

```text
pod: sd1y022qwjg3b6
gpu: NVIDIA GeForce RTX 4090
status after run: deleted
model: openbmb/MiniCPM-V-4.6
transformers: 5.12.0
training rows: 64
vision-language embedding dim: 1024
robot state dim: 27
action chunk: 10 x 32 normalized joint targets
```

This run froze MiniCPM-V 4.6, encoded image + instruction rows from the
manipulation-heavy manifest, concatenated those embeddings with robot state, and
trained a continuous action head.

RunPod eval:

```text
pick_up: 1/1
```

Files:

```text
Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_minicpm_vla_action_head_smoke/minicpm_vla_action_head.pt
Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_minicpm_vla_action_head_smoke/train_minicpm_vla_action_head.json
Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_minicpm_vla_action_head_smoke/eval_pick_up_minicpm_vla.json
Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_minicpm_vla_action_head_smoke/minicpm_embedding_cache.npz

Fireboy-training-policy-vla/runpod-artifacts/runpod_artifacts/fireboy_minicpm_vla_action_head_smoke/minicpm_vla_pick_up_policy_ep000.mp4
```

Interpretation:

- MiniCPM-V 4.6 loads and runs on RunPod for this project.
- The image + language + robot state -> action chunk path is now proven at
  smoke scale.
- This is not LoRA yet; MiniCPM was frozen.
- Next: scale rows, evaluate `go_eat_berry`, then add LoRA only after the frozen
  encoder/action-head pass is reliable.

### Scaled MiniCPM-V Residual-Fusion Gate

Plain scaled run first failed closed-loop:

```text
head: single_tower_v1
training rows: 256
pick_up:       0/1
go_eat_berry: 0/1
issue: arm moved, but gripper did not align/close reliably enough to latch
```

Fix:

```text
archive: Fireboy-training-policy-vla/vla-rollouts/minicpm_slices/manip_2048_uniform/fireboy-vla-manip-2048-uniform-320px.tgz
rows: 2048
pick_up rows: 1024
go_eat_berry rows: 1024
sample mode: uniform across 72 episodes per task
head: state_residual_fusion_v1
MiniCPM-V: frozen
VL embedding dim: 1024
robot state dim: 27
action chunk: 10 x 32 normalized joint targets
GPU: NVIDIA RTX 6000 Ada Generation
pod: 288oqe4tpvkcvq
status after run: deleted
runpodctl pod list --all -> []
```

RunPod training:

```text
checkpoint: fireboy-vla-physics/build/checkpoints/fireboy_minicpm_vla_action_head_residual_2048/minicpm_vla_action_head.pt
rows: 2048
train rows: 1802
val rows: 246
final val loss: 0.006485409568995237
vl_residual_scale: 0.12
action_std_floor: 0.01
```

Live MuJoCo eval:

```text
pick_up:       3/3
go_eat_berry: 3/3
replan interval: 8 sim steps
```

Files:

```text
Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_minicpm_vla_action_head_residual_2048/minicpm_vla_action_head.pt
Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_minicpm_vla_action_head_residual_2048/train_minicpm_vla_action_head.json
Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_minicpm_vla_action_head_residual_2048/eval_pick_up_minicpm_vla.json
Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_minicpm_vla_action_head_residual_2048/eval_go_eat_berry_minicpm_vla.json
Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_minicpm_vla_action_head_residual_2048/minicpm_embedding_cache.npz

Fireboy-training-policy-vla/runpod-artifacts/runpod_artifacts/fireboy_minicpm_vla_action_head_residual_2048/minicpm_vla_pick_up_policy_ep000.mp4
Fireboy-training-policy-vla/runpod-artifacts/runpod_artifacts/fireboy_minicpm_vla_action_head_residual_2048/minicpm_vla_go_eat_berry_policy_ep000.mp4
Fireboy-training-policy-vla/runpod-artifacts/runpod_artifacts/fireboy_minicpm_vla_action_head_residual_2048/minicpm_vla_pick_up_policy_contact_sheet.jpg
Fireboy-training-policy-vla/runpod-artifacts/runpod_artifacts/fireboy_minicpm_vla_action_head_residual_2048/minicpm_vla_go_eat_berry_policy_contact_sheet.jpg
```

Interpretation:

- `image + language + robot state -> action chunk` is now proven beyond smoke
  scale for two manipulation skills.
- This is still frozen MiniCPM-V plus a trained action head, not LoRA.
- The next LoRA run should start from this residual-fusion setup, not from the
  failed single-tower 256-row setup.

### MiniCPM-V LoRA Adapter Gate

First MiniCPM-V LoRA run:

```text
seed checkpoint: fireboy_minicpm_vla_action_head_residual_2048
LoRA checkpoint: fireboy-vla-physics/build/checkpoints/fireboy_minicpm_vla_lora_residual_512/minicpm_vla_lora_action_head.pt
LoRA adapter: fireboy-vla-physics/build/checkpoints/fireboy_minicpm_vla_lora_residual_512/lora_adapter
model: openbmb/MiniCPM-V-4.6
rows: 512
train rows: 461
val rows: 51
LoRA rank: 8
LoRA alpha: 16
state controller branch: frozen
GPU: NVIDIA RTX 6000 Ada Generation
pod: vszxq5pu6avgbu
status after run: deleted
runpodctl pod list --all -> []
```

Live MuJoCo eval with the LoRA adapter loaded:

```text
initial gate:
  pick_up:       1/1
  go_eat_berry: 1/1

latest eval-only RunPod gate:
  GPU: NVIDIA A40
  PyTorch: 2.4.1+cu124
  CUDA: true
  checkpoint: fireboy_minicpm_vla_lora_residual_512
  pick_up:       3/3
  go_eat_berry: 3/3
replan interval: 8 sim steps
```

Files:

```text
Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_minicpm_vla_lora_residual_512/minicpm_vla_lora_action_head.pt
Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_minicpm_vla_lora_residual_512/lora_adapter/adapter_model.safetensors
Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_minicpm_vla_lora_residual_512/lora_adapter/adapter_config.json
Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_minicpm_vla_lora_residual_512/train_minicpm_vla_lora_action_head.json
Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_minicpm_vla_lora_residual_512/eval_pick_up_minicpm_vla_lora.json
Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_minicpm_vla_lora_residual_512/eval_go_eat_berry_minicpm_vla_lora.json
Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_minicpm_vla_lora_residual_512_eval_3ep/eval_pick_up_minicpm_vla.json
Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_minicpm_vla_lora_residual_512_eval_3ep/eval_go_eat_berry_minicpm_vla.json

Fireboy-training-policy-vla/runpod-artifacts/runpod_artifacts/fireboy_minicpm_vla_lora_residual_512/minicpm_vla_pick_up_policy_ep000.mp4
Fireboy-training-policy-vla/runpod-artifacts/runpod_artifacts/fireboy_minicpm_vla_lora_residual_512/minicpm_vla_go_eat_berry_policy_ep000.mp4
Fireboy-training-policy-vla/runpod-artifacts/runpod_artifacts/fireboy_minicpm_vla_lora_residual_512/minicpm_vla_lora_pick_up_policy_contact_sheet.jpg
Fireboy-training-policy-vla/runpod-artifacts/runpod_artifacts/fireboy_minicpm_vla_lora_residual_512/minicpm_vla_lora_go_eat_berry_policy_contact_sheet.jpg
Fireboy-training-policy-vla/runpod-artifacts/runpod_artifacts/fireboy_minicpm_vla_lora_residual_512_eval_3ep/minicpm_vla_pick_up_policy_ep000.mp4
Fireboy-training-policy-vla/runpod-artifacts/runpod_artifacts/fireboy_minicpm_vla_lora_residual_512_eval_3ep/minicpm_vla_go_eat_berry_policy_ep000.mp4
```

## Modal Live Inference Wiring

The promoted frozen router is now served from Modal for the local Toy Room app:

```text
Modal app: fireboy-vla-router
URL: https://sanjuhs123--fireboy-vla-router.modal.run
GPU: L40S
idle scaledown window: 60 seconds
checkpoint: Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_minicpm_vla_skill_param_head/minicpm_vla_skill_param_head.pt
model: openbmb/MiniCPM-V-4.6
policy_kind: minicpm_vla_frozen_encoder_skill_param_head_v1
```

Toy Room local env:

```bash
TOYBOX_VLA_ROUTER_URL='https://sanjuhs123--fireboy-vla-router.modal.run' \
TOYBOX_VLA_ROUTER_ACTION=1 \
PORT=65373 PID_FILE=.toybox-65373.pid LOG_FILE=.toybox-65373.log ./start.sh
```

Verified through `/api/pet-action`:

```text
VLA router: walk to the yellow marker -> walk_to, cuda, MuJoCo success true
VLA router: run around -> run_around, cuda, MuJoCo success true
VLA router: pick up the berry -> pick_up, cuda, MuJoCo success true
VLA router: go find berry and eat it -> find_and_eat_berry, cuda, MuJoCo success true
```

Final resource state after proof traffic:

```text
RunPod pods: []
Modal fireboy-vla-router: deployed, tasks 0
```

Proof:

```text
Fireboy-training-policy-vla/modal-inference-results-2026-06-15.md
Fireboy-training-policy-vla/proofs/modal-vla-router-policy-gallery.png
fireboy-vla-physics/build/fireboy-policy-proof-bundle.tgz
```

Repeatable final smoke gate:

```bash
PYTHONPATH=fireboy-vla-physics/src \
fireboy-vla-physics/.venv/bin/python \
fireboy-vla-physics/src/final_vla_demo_smoke.py \
  --out Fireboy-training-policy-vla/proofs/final-vla-demo-smoke.json
```

Latest smoke result:

```text
ok: true
route checks: all four expected skills passed on cuda
pet-action checks: all four commands dispatched through Modal VLA + MuJoCo
registry: checked_paths 49, missing_count 0
RunPod pods: []
proof json: Fireboy-training-policy-vla/proofs/final-vla-demo-smoke.json
proof bundle: copied_count 35, checkpoint_reference_count 21
```

Interpretation:

- This is a real MiniCPM-V LoRA adapter plus continuous action head.
- It is proven for three live eval rollouts each of `pick_up` and
  `go_eat_berry`.
- It is not yet a broad generalized pet model. Movement commands still need to
  be folded into the MiniCPM-V/LoRA dataset and eval suite.

### All-Skill MiniCPM-V Frozen-Encoder Attempt

All-skill source archive:

```text
source: Fireboy-training-policy-vla/vla-rollouts/vla_manifests/fireboy_vla_action_chunks_allskill_interleaved_source_20260615.jsonl
archive: Fireboy-training-policy-vla/vla-rollouts/minicpm_slices/allskill_3072_uniform/fireboy-vla-allskill-3072-uniform-320px.tgz
rows: 3072
pick_up rows: 1028
go_eat_berry rows: 1052
run_around rows: 512
go_to_point rows: 480
```

RunPod training:

```text
pod: mcynpcuc5g0pzj
gpu: NVIDIA A40
status after run: deleted
checkpoint: fireboy-vla-physics/build/checkpoints/fireboy_minicpm_vla_action_head_allskill_3072/minicpm_vla_action_head.pt
head: state_residual_fusion_v1
rows: 3072
train rows: 2703
val rows: 369
final val loss: 0.0608733631670475
```

Live MuJoCo eval:

```text
pick_up:       2/2
go_eat_berry: 0/2
run_around:   2/2
go_to_point:  0/2
```

Files:

```text
Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_minicpm_vla_action_head_allskill_3072/minicpm_vla_action_head.pt
Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_minicpm_vla_action_head_allskill_3072/eval_pick_up_minicpm_vla.json
Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_minicpm_vla_action_head_allskill_3072/eval_go_eat_berry_minicpm_vla.json
Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_minicpm_vla_action_head_allskill_3072/eval_run_around_minicpm_vla.json
Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_minicpm_vla_action_head_allskill_3072/eval_go_to_point_minicpm_vla.json

Fireboy-training-policy-vla/runpod-artifacts/runpod_artifacts/fireboy_minicpm_vla_action_head_allskill_3072/minicpm_vla_pick_up_policy_ep000.mp4
Fireboy-training-policy-vla/runpod-artifacts/runpod_artifacts/fireboy_minicpm_vla_action_head_allskill_3072/minicpm_vla_go_eat_berry_policy_ep000.mp4
Fireboy-training-policy-vla/runpod-artifacts/runpod_artifacts/fireboy_minicpm_vla_action_head_allskill_3072/minicpm_vla_run_around_policy_ep000.mp4
Fireboy-training-policy-vla/runpod-artifacts/runpod_artifacts/fireboy_minicpm_vla_action_head_allskill_3072/minicpm_vla_go_to_point_policy_ep000.mp4
```

Interpretation:

- One unified frozen MiniCPM action head can already do `pick_up` and
  `run_around`.
- It does not yet solve `go_eat_berry` and `go_to_point` in one shared model.
- The next all-command attempt needs better task balancing and probably either
  per-task heads, task adapters, or a hierarchical router over specialized VLA
  heads.

### Movement-Only MiniCPM-V Frozen-Encoder Attempt

Movement-only archive:

```text
archive: Fireboy-training-policy-vla/vla-rollouts/minicpm_slices/movement_992_uniform/fireboy-vla-movement-992-uniform-320px.tgz
rows: 992
run_around rows: 512
go_to_point rows: 480
```

RunPod training:

```text
pod: b29m1rkrg0gpig
gpu: NVIDIA A40
status after run: deleted
checkpoint: fireboy-vla-physics/build/checkpoints/fireboy_minicpm_vla_action_head_movement_992/minicpm_vla_action_head.pt
rows: 992
train rows: 873
val rows: 119
```

Live MuJoCo eval:

```text
run_around:  3/3
go_to_point: 1/3
```

Files:

```text
Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_minicpm_vla_action_head_movement_992/minicpm_vla_action_head.pt
Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_minicpm_vla_action_head_movement_992/eval_run_around_minicpm_vla.json
Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_minicpm_vla_action_head_movement_992/eval_go_to_point_minicpm_vla.json
Fireboy-training-policy-vla/runpod-artifacts/runpod_artifacts/fireboy_minicpm_vla_action_head_movement_992/minicpm_vla_run_around_policy_ep000.mp4
Fireboy-training-policy-vla/runpod-artifacts/runpod_artifacts/fireboy_minicpm_vla_action_head_movement_992/minicpm_vla_go_to_point_policy_ep000.mp4
Fireboy-training-policy-vla/runpod-artifacts/runpod_artifacts/fireboy_minicpm_vla_action_head_movement_992/minicpm_vla_movement_run_around_policy_contact_sheet.jpg
Fireboy-training-policy-vla/runpod-artifacts/runpod_artifacts/fireboy_minicpm_vla_action_head_movement_992/minicpm_vla_movement_go_to_point_policy_contact_sheet.jpg
```

Interpretation:

- `run_around` is now reliable in a MiniCPM action-head format.
- `go_to_point` is not reliable enough yet in the MiniCPM action-head format,
  even though the older state/action movement policy has passed this skill.
- Navigation needs better target-conditioned state features or target-visible
  image conditioning before it should be folded into the final LoRA model.

## Learned Policy Results

### New Action-Chunk Manipulation Pass

Second RunPod pass:

```text
pod: x9gjy51o6179qj
gpu: NVIDIA RTX 6000 Ada Generation
status after run: deleted
runpodctl pod list --all -> []
dataset: 1680 expert episodes, 420 per task
```

The new chunk policy predicts a short sequence of future normalized joint
targets instead of only the next single action. This matches the VLA action-head
shape:

```text
robot state + command/task flags -> next 16 joint-target actions
```

Results:

```text
pick_up chunk:       20/20
go_eat_berry chunk: 20/20
```

Files:

```text
Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_articulated_pick_up_chunk/faithful_articulated_chunk_policy.pt
Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_articulated_pick_up_chunk/eval_pick_up_chunk.json
Fireboy-training-policy-vla/runpod-artifacts/runpod_artifacts/learned_chunk/faithful_chunk_pick_up_policy_ep000.mp4

Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_articulated_go_eat_berry_chunk/faithful_articulated_chunk_policy.pt
Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_articulated_go_eat_berry_chunk/eval_go_eat_berry_chunk.json
Fireboy-training-policy-vla/runpod-artifacts/runpod_artifacts/learned_chunk/faithful_chunk_go_eat_berry_policy_ep000.mp4
```

Local checkpoint copies:

```text
fireboy-vla-physics/checkpoints/fireboy_articulated_pick_up_chunk/faithful_articulated_chunk_policy.pt
fireboy-vla-physics/checkpoints/fireboy_articulated_go_eat_berry_chunk/faithful_articulated_chunk_policy.pt
```

Interpretation:

- The old one-step behavior-cloning pickup/eat policies failed.
- The chunked policy fixed the manipulation gate on the current MuJoCo body.
- This is still not MiniCPM-V LoRA yet, but it is the correct action-head shape
  for MiniCPM-V VLA training.

### Passed

```text
run_around:        20/20
go_to_point_clock: 20/20
```

These are real RunPod-trained checkpoints with RunPod-rendered proof clips.

Files:

```text
Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_articulated_run_around/faithful_articulated_policy.pt
Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_articulated_run_around/faithful_articulated_policy.npz
Fireboy-training-policy-vla/runpod-artifacts/runpod_artifacts/learned/faithful_learned_run_around.mp4

Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_articulated_go_to_point_clock/faithful_articulated_policy.pt
Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_articulated_go_to_point_clock/faithful_articulated_policy.npz
Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_articulated_go_to_point_clock/eval_go_to_point_clock_fixed_target.json
Fireboy-training-policy-vla/runpod-artifacts/runpod_artifacts/learned_clock/faithful_learned_go_to_point.mp4
```

### Failed

```text
pick_up:       0/20
go_eat_berry: 0/20
go_to_point:  0/20 with full-state BC
```

Interpretation:

- `pick_up` and `go_eat_berry` failed only in the old single-step
  behavior-cloning lane. The new action-chunk lane above passes 20/20.
- `go_to_point` failed with the full-state BC policy by driving root XY to the
  joint limits. The clock/target-conditioned policy fixed this and passed 20/20.

## Controller Proof Clips

The controller/expert lane works for all five proof modes:

```text
body
go_to_point
run_around
pick_up
go_eat_berry
```

Files:

```text
Fireboy-training-policy-vla/runpod-artifacts/runpod_artifacts/controller/fireboy_articulated_body.mp4
Fireboy-training-policy-vla/runpod-artifacts/runpod_artifacts/controller/fireboy_articulated_go_to_point.mp4
Fireboy-training-policy-vla/runpod-artifacts/runpod_artifacts/controller/fireboy_articulated_run_around.mp4
Fireboy-training-policy-vla/runpod-artifacts/runpod_artifacts/controller/fireboy_articulated_pick_up.mp4
Fireboy-training-policy-vla/runpod-artifacts/runpod_artifacts/controller/fireboy_articulated_go_eat_berry.mp4
```

Important caveat:

```text
The controller clips prove the body and task mechanics.
They are not learned VLA policies.
```

## Newton Probe

Newton was validated on RunPod GPU.

Command class:

```text
pip install "newton[examples]" in a venv
python -m newton.examples --list
python -m newton.examples robot_g1 --device cuda:0 --viewer null --num-frames 120
```

Result:

```text
Warp initialized cuda:0 on NVIDIA RTX 6000 Ada Generation
Unitree G1 assets downloaded
Newton/MuJoCo-Warp kernels compiled on cuda:0
robot_g1 completed
```

Log:

```text
Fireboy-training-policy-vla/runpod-artifacts/probes/newton_probe_venv.log
```

Meaning:

```text
Newton is usable on RunPod for G1/humanoid rollout.
Fire Boy direct Newton rollout still needs an adapter from our MJCF/body into
Newton-compatible asset loading, or the faster route: use G1/ProtoMotions and
render Fire Boy as a visual costume.
```

## Kimodo Probe

Kimodo official repo cloned and installed on RunPod after adding:

```text
cmake
build-essential
python dev headers
```

Validated:

```text
kimodo_gen exists
kimodo_demo exists
import kimodo passes
```

Attempted:

```text
kimodo_gen "A humanoid robot walks forward to a target point." \
  --model Kimodo-G1-RP-v1 \
  --duration 2 \
  --num_samples 1 \
  --diffusion_steps 10
```

Result:

```text
Kimodo fetched model files, then failed because its fallback local text encoder
needs gated Hugging Face access to meta-llama/Meta-Llama-3-8B-Instruct.
```

Blocker:

```text
Need an authenticated HF token with access to meta-llama/Meta-Llama-3-8B-Instruct,
or a running Kimodo text-encoder service.
```

Logs:

```text
Fireboy-training-policy-vla/runpod-artifacts/probes/kimodo_probe.log
Fireboy-training-policy-vla/runpod-artifacts/probes/kimodo_probe_install_after_python_dev.log
Fireboy-training-policy-vla/runpod-artifacts/probes/kimodo_gen_help.log
Fireboy-training-policy-vla/runpod-artifacts/probes/kimodo_generation_probe.log
```

## ProtoMotions Probe

ProtoMotions official repo cloned and installed on RunPod.

Validated:

```text
import protomotions passes
G1 robot config exists
Kimodo prep path exists
G1 CSV converter exists
Newton sim2sim support exists
tiny G1 motion sets exist
```

Log:

```text
Fireboy-training-policy-vla/runpod-artifacts/probes/protomotions_probe.log
```

Meaning:

```text
ProtoMotions is the correct next lane for human-like walk/run/steering/terrain.
The fastest route is not direct Fire Boy custom-RL first.
The fastest route is:

Kimodo or existing G1 motions
  -> ProtoMotions G1 tracking/steering policy
  -> Newton/MuJoCo sim2sim proof
  -> Fire Boy GLB visual costume retargeted on top
```

## MiniCPM-V 4.6 Probe

MiniCPM-V 4.6 was smoke-tested on RunPod before pod shutdown.

Result from terminal:

```text
transformers: 5.12.0
cuda: true
model_id: openbmb/MiniCPM-V-4.6
processor_loaded: MiniCPMV4_6Processor
model_loaded: MiniCPMV4_6ForConditionalGeneration
device_map_ready
```

Meaning:

```text
The MiniCPM-V 4.6 backbone path is available on RunPod.
We can build the VLA action-head/LoRA stage after producing image/state/action
rollout rows.
```

Note:

The log file was not copied before pod deletion because the stop command closed
SSH first. The terminal output above is the captured proof.

## What Works Now

```text
Fire Boy body proof: yes
RunPod MP4 proof: yes
learned run_around: yes, 20/20
learned go_to_point: yes, 20/20 with clock/target policy
controller pickup/eat: yes
learned pickup/eat: yes, 20/20 with action-chunk policy
Newton GPU: yes
Kimodo install: yes
Kimodo generation: blocked by gated Llama text encoder
ProtoMotions install/import: yes
MiniCPM-V 4.6 load: yes
```

## Next Technical Move

Next best sequence:

1. Generate image-rich rollout datasets on RunPod for all four skills.
2. Build VLA manifests with image path, instruction, robot state, and action
   chunks.
3. Train the non-MiniCPM state/action-head baseline on those manifests.
4. Attach MiniCPM-V 4.6 as the vision-language encoder.
5. Fine-tune the small robot-state encoder and action head first.
6. Add LoRA adapters to MiniCPM-V only after the action-head rollout gate works.

```text
MiniCPM-V(image, instruction)
  + robot_state_encoder(qpos, qvel, contacts, target)
  -> action head
  -> next 0.5 seconds of joint targets / skill parameters
```

## Overnight Navigation VLA Attempts

Three MiniCPM-V frozen-encoder `go_to_point` navigation heads were trained and
evaluated on RunPod A40 after the earlier failures:

```text
checkpoint: fireboy_minicpm_vla_action_head_go_to_point_full_1step_480
mode: absolute_joint_targets, full state, 1-step replan
eval: go_to_point 0/5
failure: root drifted to negative X / positive Y limits

checkpoint: fireboy_minicpm_vla_action_head_go_to_point_rootvel_480
mode: root_velocity_v1, nav_clock state, 1-step replan
eval: go_to_point 0/5
failure: root drifted to positive Y limit

checkpoint: fireboy_minicpm_vla_action_head_go_to_point_recovery_rootvel_884
mode: root_velocity_v1, nav_clock state, recovery dataset
eval: go_to_point 0/5
failure: root saturated to positive X / negative Y limits
```

Artifacts:

```text
Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_minicpm_vla_action_head_go_to_point_full_1step_480/
Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_minicpm_vla_action_head_go_to_point_rootvel_480/
Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_minicpm_vla_action_head_go_to_point_recovery_rootvel_884/
Fireboy-training-policy-vla/runpod-artifacts/runpod_artifacts/fireboy_minicpm_vla_action_head_go_to_point_recovery_rootvel_884/minicpm_vla_go_to_point_policy_ep000.mp4
```

Recovery data generated on RunPod:

```text
run id: goto-recovery-20260615-01
episodes: 96
images / manifest rows: 884
archive: Fireboy-training-policy-vla/vla-rollouts/fireboy-vla-rollouts-goto-recovery-20260615-01.tgz
slice: Fireboy-training-policy-vla/vla-rollouts/minicpm_slices/go_to_point_recovery_884_rootvel/fireboy-vla-go-to-point-recovery-884-1step-320px.tgz
```

Interpretation:

```text
Direct MiniCPM low-level root action is not reliable for go_to_point yet.
The failure is closed-loop compounding / out-of-distribution control, not just
training loss. Keep MiniCPM for manipulation and route navigation through the
proven low-level movement policies until a better navigation objective is built.
```

Runtime bridge fix:

```text
fireboy-vla-physics/src/pet_runtime.py now routes:
  walk_to/run_to     -> go_to_point_clock articulated policy
  walk_around/run_around -> run_around articulated policy

src/mujoco_policy_bridge.py now accepts articulated movement rollouts and
returns GIF/MP4 URLs to Toy V3 debug output.
```

Verified local command-level tests:

```text
"walk to the yellow marker": success true
policy: Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_articulated_go_to_point_clock/faithful_articulated_policy.npz
mp4: fireboy-vla-physics/build/toy-v3-policy/articulated/faithful_learned_go_to_point.mp4

"run around": success true
policy: Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_articulated_run_around/faithful_articulated_policy.npz
mp4: fireboy-vla-physics/build/toy-v3-policy/articulated/faithful_learned_run_around.mp4
```

Policy registry:

```text
file: fireboy-vla-physics/policy_registry.json
validator: fireboy-vla-physics/src/validate_policy_registry.py
checked_paths: 24
missing_count: 0
ok: true
```

Bridge-level verification:

```text
"walk to the yellow marker with mujoco policy"
  intent: mujoco_articulated_policy
  animation: walk
  success: true
  registryStatus: active
  registrySuccessRate: 1.0
  mp4Url: /fireboy-vla/build/toy-v3-policy/articulated/faithful_learned_go_to_point.mp4

"run around with mujoco policy"
  intent: mujoco_articulated_policy
  animation: run
  success: true
  registryStatus: active
  registrySuccessRate: 1.0
  mp4Url: /fireboy-vla/build/toy-v3-policy/articulated/faithful_learned_run_around.mp4
```

## Stronger MiniCPM-V LoRA Manipulation Eval

Added an eval-only RunPod helper:

```text
fireboy-vla-physics/scripts/eval_minicpm_vla_checkpoint_runpod.sh
```

It uploads an existing checkpoint directory, runs `eval_minicpm_vla_policy.py`
on a fresh GPU pod, downloads artifacts, then stops/deletes the pod.

Run:

```text
pod: s9ekny96kkt1l1
gpu: NVIDIA A40
checkpoint: fireboy_minicpm_vla_lora_residual_512/minicpm_vla_lora_action_head.pt
run name: fireboy_minicpm_vla_lora_residual_512_eval_3ep
pod cleanup: deleted
```

Results:

```text
pick_up:       3/3, success_rate 1.0
go_eat_berry: 3/3, success_rate 1.0
```

Artifacts:

```text
Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_minicpm_vla_lora_residual_512_eval_3ep/eval_pick_up_minicpm_vla.json
Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_minicpm_vla_lora_residual_512_eval_3ep/eval_go_eat_berry_minicpm_vla.json
Fireboy-training-policy-vla/runpod-artifacts/runpod_artifacts/fireboy_minicpm_vla_lora_residual_512_eval_3ep/minicpm_vla_pick_up_policy_ep000.mp4
Fireboy-training-policy-vla/runpod-artifacts/runpod_artifacts/fireboy_minicpm_vla_lora_residual_512_eval_3ep/minicpm_vla_go_eat_berry_policy_ep000.mp4
```
