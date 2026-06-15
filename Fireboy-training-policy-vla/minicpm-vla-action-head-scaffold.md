# MiniCPM-V 4.6 VLA Action-Head Scaffold

## Backbone Smoke Test

RunPod smoke test passed:

```text
model_id: openbmb/MiniCPM-V-4.6
processor_loaded: MiniCPMV4_6Processor
model_loaded: MiniCPMV4_6ForConditionalGeneration
cuda: true
device_map_ready
```

This means the MiniCPM-V 4.6 backbone can load on RunPod.

Official model notes:

- MiniCPM-V 4.6 uses SigLIP2-400M plus a Qwen3.5-0.8B LLM.
- It supports image/video understanding.
- Official fine-tuning routes include LLaMA-Factory and ms-swift.

Source:

```text
https://huggingface.co/openbmb/MiniCPM-V-4.6
```

## What We Train First

Do not begin with full end-to-end MiniCPM fine-tuning.

First train:

```text
robot state encoder + continuous action head
```

Then train:

```text
MiniCPM-V LoRA adapters + action head
```

The output is an action chunk, not a sentence:

```text
next 0.5 seconds of normalized joint targets
```

At 20 Hz, 0.5 seconds is 10 action steps.

Current MuJoCo action-chunk checkpoint status:

```text
pick_up chunk:       20/20 on RunPod
go_eat_berry chunk: 20/20 on RunPod
chunk length used:   16 normalized joint-target actions
```

Artifacts:

```text
Fireboy-training-policy-vla/runpod-artifacts/runpod_artifacts/learned_chunk/faithful_chunk_pick_up_policy_ep000.mp4
Fireboy-training-policy-vla/runpod-artifacts/runpod_artifacts/learned_chunk/faithful_chunk_go_eat_berry_policy_ep000.mp4
```

## Dataset Row

The VLA row should look like:

```json
{
  "image_path": "/abs/path/to/frame.jpg",
  "instruction": "walk to the yellow target",
  "robot_state": {
    "qpos": [],
    "qvel": [],
    "ctrl": [],
    "previous_action": [],
    "right_hand_pos": [],
    "left_hand_pos": [],
    "mouth_pos": [],
    "ball_pos": [],
    "task_flags": [],
    "stage_flags": []
  },
  "action_type": "normalized_joint_targets",
  "action_chunk_steps": 10,
  "action_chunk": []
}
```

## Manifest Builder

New script:

```text
fireboy-vla-physics/src/build_vla_action_manifest.py
```

RunPod rollout-builder script:

```text
fireboy-vla-physics/scripts/generate_vla_rollouts_runpod.sh
```

First generated manifest:

```text
Fireboy-training-policy-vla/vla-rollouts/vla_manifests/fireboy_vla_action_chunks_20260615-021838.jsonl
```

Summary:

```text
episodes: 64
images: 2368
manifest rows: 2368
chunk steps: 10
tasks: pick_up, go_eat_berry, run_around, go_to_point
```

First manifest action-head baseline:

```text
checkpoint: fireboy-vla-physics/build/checkpoints/fireboy_vla_manifest_action_head/vla_manifest_action_head.pt
pick_up:       2/8
go_eat_berry: 2/8
run_around:   8/8
go_to_point:  7/8
```

Meaning:

```text
The VLA JSONL -> action-head path works.
The small mixed image dataset is not enough for reliable contact manipulation.
MiniCPM-V LoRA should not start on this tiny manifest alone.
```

Manipulation-heavy manifest result:

```text
manifest: Fireboy-training-policy-vla/vla-rollouts/vla_manifests/fireboy_vla_action_chunks_manip-20260615-025016.jsonl
episodes: 144
images: 6192
rows: 6192
tasks: pick_up, go_eat_berry
```

Focused action-head eval from that manifest:

```text
checkpoint: fireboy-vla-physics/build/checkpoints/fireboy_vla_manifest_action_head_manip/vla_manifest_action_head.pt
pick_up:       12/12
go_eat_berry: 12/12
```

Meaning:

```text
The VLA action-head path is now reliable for manipulation when the manifest is
large and task-focused enough. The next MiniCPM-V LoRA step should use this
manipulation-heavy manifest plus the locomotion/navigation manifest.
```

First MiniCPM-V frozen-encoder checkpoint:

```text
checkpoint: fireboy-vla-physics/build/checkpoints/fireboy_minicpm_vla_action_head_smoke/minicpm_vla_action_head.pt
model: openbmb/MiniCPM-V-4.6
rows: 64
VL embedding dim: 1024
state dim: 27
action chunk: 10 x 32 normalized joint targets
RunPod eval pick_up: 1/1
```

Proof:

```text
Fireboy-training-policy-vla/runpod-artifacts/runpod_artifacts/fireboy_minicpm_vla_action_head_smoke/minicpm_vla_pick_up_policy_ep000.mp4
```

Meaning:

```text
image + language + robot state -> action chunk is now proven end-to-end at
smoke scale with MiniCPM-V 4.6 frozen. This is the correct step immediately
before LoRA. LoRA has not been trained yet.
```

Scaled MiniCPM-V residual-fusion checkpoint:

```text
checkpoint: fireboy-vla-physics/build/checkpoints/fireboy_minicpm_vla_action_head_residual_2048/minicpm_vla_action_head.pt
model: openbmb/MiniCPM-V-4.6
MiniCPM-V: frozen
rows: 2048
train rows: 1802
val rows: 246
VL embedding dim: 1024
state dim: 27
action chunk: 10 x 32 normalized joint targets
head: state_residual_fusion_v1
vl_residual_scale: 0.12
action_std_floor: 0.01
RunPod GPU: NVIDIA RTX 6000 Ada Generation
RunPod eval pick_up: 3/3
RunPod eval go_eat_berry: 3/3
pod after run: deleted
runpodctl pod list --all -> []
```

Proof:

```text
Fireboy-training-policy-vla/runpod-artifacts/runpod_artifacts/fireboy_minicpm_vla_action_head_residual_2048/minicpm_vla_pick_up_policy_ep000.mp4
Fireboy-training-policy-vla/runpod-artifacts/runpod_artifacts/fireboy_minicpm_vla_action_head_residual_2048/minicpm_vla_go_eat_berry_policy_ep000.mp4
Fireboy-training-policy-vla/runpod-artifacts/runpod_artifacts/fireboy_minicpm_vla_action_head_residual_2048/minicpm_vla_pick_up_policy_contact_sheet.jpg
Fireboy-training-policy-vla/runpod-artifacts/runpod_artifacts/fireboy_minicpm_vla_action_head_residual_2048/minicpm_vla_go_eat_berry_policy_contact_sheet.jpg
```

Why the residual head matters:

```text
The 256-row single-tower MiniCPM action head failed closed-loop eval:
pick_up 0/1, go_eat_berry 0/1.

The working version uses a state-dominant controller branch plus a smaller
MiniCPM vision-language residual branch. That preserves reliable robot-state
control while still satisfying the VLA form:

image + language + robot state -> action chunk
```

First MiniCPM-V LoRA adapter checkpoint:

```text
checkpoint: fireboy-vla-physics/build/checkpoints/fireboy_minicpm_vla_lora_residual_512/minicpm_vla_lora_action_head.pt
adapter: fireboy-vla-physics/build/checkpoints/fireboy_minicpm_vla_lora_residual_512/lora_adapter
seed checkpoint: fireboy_minicpm_vla_action_head_residual_2048
rows: 512
train rows: 461
val rows: 51
LoRA rank: 8
LoRA alpha: 16
state controller branch: frozen
RunPod eval pick_up: 1/1
RunPod eval go_eat_berry: 1/1
pod after run: deleted
runpodctl pod list --all -> []
```

LoRA proof:

```text
Fireboy-training-policy-vla/runpod-artifacts/runpod_artifacts/fireboy_minicpm_vla_lora_residual_512/minicpm_vla_pick_up_policy_ep000.mp4
Fireboy-training-policy-vla/runpod-artifacts/runpod_artifacts/fireboy_minicpm_vla_lora_residual_512/minicpm_vla_go_eat_berry_policy_ep000.mp4
Fireboy-training-policy-vla/runpod-artifacts/runpod_artifacts/fireboy_minicpm_vla_lora_residual_512/minicpm_vla_lora_pick_up_policy_contact_sheet.jpg
Fireboy-training-policy-vla/runpod-artifacts/runpod_artifacts/fireboy_minicpm_vla_lora_residual_512/minicpm_vla_lora_go_eat_berry_policy_contact_sheet.jpg
```

Important boundary:

```text
This is now a real MiniCPM-V LoRA VLA checkpoint for manipulation rollouts.
It is not yet the final generalized pet model because movement commands
run_around/go_to_point still need to be added to the MiniCPM-V LoRA dataset and
closed-loop eval suite.
```

All-skill frozen-encoder attempt:

```text
checkpoint: fireboy-vla-physics/build/checkpoints/fireboy_minicpm_vla_action_head_allskill_3072/minicpm_vla_action_head.pt
rows: 3072
pick_up:       2/2
go_eat_berry: 0/2
run_around:   2/2
go_to_point:  0/2
```

Meaning:

```text
One shared MiniCPM action head is not reliable enough yet. The current safest
pet architecture is:

language command router
  -> manipulation LoRA VLA head for pick_up/go_eat_berry
  -> movement policy/head for run_around/go_to_point

Then train a better unified all-skill LoRA once balancing and navigation data
are improved.
```

Movement-only MiniCPM action-head attempt:

```text
checkpoint: fireboy-vla-physics/build/checkpoints/fireboy_minicpm_vla_action_head_movement_992/minicpm_vla_action_head.pt
rows: 992
run_around:  3/3
go_to_point: 1/3
```

Current practical routing:

```text
pick_up/go_eat_berry -> fireboy_minicpm_vla_lora_residual_512
run_around           -> fireboy_minicpm_vla_action_head_movement_992
go_to_point          -> existing state/action go_to_point policy for now
```

Usage after generating episodes with images:

```bash
python fireboy-vla-physics/src/generate_articulated_dataset.py \
  --task go_to_point \
  --num-episodes 200 \
  --out-dir fireboy-vla-physics/build/datasets/vla_go_to_point_images \
  --seed 12000 \
  --save-images

python fireboy-vla-physics/src/build_vla_action_manifest.py \
  --dataset-dir fireboy-vla-physics/build/datasets/vla_go_to_point_images \
  --out fireboy-vla-physics/build/vla_manifests/go_to_point_action_chunks.jsonl \
  --chunk-steps 10 \
  --stride 2
```

Use the same pattern for:

```text
run_around
pick_up
go_eat_berry
```

For pickup/eat, use expert/controller traces first because the learned BC
checkpoint is not reliable yet.

## First Training Stage

Train a state+language action head:

```text
instruction embedding + robot_state -> action_chunk
```

Purpose:

- prove action chunks train better than single-step BC
- avoid spending MiniCPM LoRA compute before the action representation works

## Second Training Stage

Freeze most of MiniCPM-V:

```text
MiniCPM-V(image, instruction) -> vision-language embedding
robot_state_encoder(robot_state) -> state embedding
concat -> action_head -> action_chunk
```

Train:

```text
state encoder
action head
optionally LoRA adapters
```

Do not train:

```text
full MiniCPM-V weights
```

until the action-head smoke test works.

## LoRA Adapter Target

Use LoRA only after the action head produces stable closed-loop rollouts.

Recommended:

```text
LoRA rank: 8 or 16
precision: bf16
batching: gradient accumulation
backbone: mostly frozen
GPU: L40S / RTX 6000 Ada / A100
```

## How This Becomes A Pet

The MiniCPM-V VLA should not directly solve every motor detail at first.

It should learn:

```text
image + command + robot_state
  -> skill/action chunk
```

Working low-level skills:

```text
go_to_point_clock
run_around
pick_up_chunk
go_eat_berry_chunk
```

Controller/expert skills available for data:

```text
pick_up
go_eat_berry
```

ProtoMotions/Newton/Kimodo lane:

```text
human-like G1 walk/run/gesture policy
  -> Fire Boy visual costume
  -> richer pet motion prior
```

## Blockers

Current blockers before full VLA:

```text
1. Need larger MiniCPM-V frozen-encoder/action-head training, not just smoke scale.
2. Need MiniCPM-backed `go_eat_berry`, `run_around`, and `go_to_point` evals.
3. Need MiniCPM-V LoRA/action-head training after frozen encoder reliability.
4. Need HF token with gated Llama access or Kimodo text-encoder service for Kimodo generation.
5. Need Fire Boy mesh retargeted onto G1/ProtoMotions body if using the fastest human-like route.
```

## Latest Navigation Result

Direct MiniCPM-V low-level navigation was tested further on RunPod:

```text
absolute 1-step go_to_point: 0/5
root_velocity_v1 go_to_point: 0/5
root_velocity_v1 with recovery data: 0/5
```

The recovery dataset itself was generated correctly:

```text
episodes: 96
rows/images: 884
root_y range: about -1.84 to +1.77
command_y labels include both signs
```

So the next VLA design should not keep asking MiniCPM to directly output root
joint targets for navigation. The practical pet architecture is now:

```text
MiniCPM-V / command router
  -> LoRA manipulation head for pick_up/go_eat_berry
  -> articulated movement policy for walk_to/go_to_point
  -> articulated movement policy for run_around
```

Toy V3 bridge/runtime status:

```text
walk to the yellow marker: passes through pet_runtime and src/mujoco_policy_bridge.py
run around: passes through pet_runtime and src/mujoco_policy_bridge.py
MP4/GIF URLs are returned in debug.mujocoPolicy
```
