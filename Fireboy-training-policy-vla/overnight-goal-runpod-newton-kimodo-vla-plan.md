# Overnight Goal: Fire Boy Pet VLA On RunPod

Date: 2026-06-15

## Final Objective

Build Fire Boy toward a true pet-like VLA:

```text
image + language command + robot state -> next 0.5 seconds of actions
```

The target behavior is:

- "go from here to there" -> navigate to a target point.
- "walk around" / "run around" -> locomotion behavior.
- "go find berry and eat" -> object approach, grasp/carry, mouth contact.
- later: obstacle traversal, looking at points of interest, pet-like idle/curious behaviors.

The GLB visual identity remains:

```text
fire-boy-rig/fire-boy-rigged-full.glb
```

The corrected MuJoCo body is the physics proxy until the GLB mesh is retargeted as a skin/costume on top of the physics body.

## Hard Rules For This Run

- RunPod is the source of truth for training, eval, and MP4 proof.
- Local machine is only for launching scripts and receiving artifacts.
- Stop/delete pods that are not needed.
- Do not claim a policy works unless RunPod eval JSON and MP4/GIF artifacts prove it.
- Do not start MiniCPM-V LoRA until at least one motion-policy gate is clean.
  This gate is now clean for pickup/eat with the frozen MiniCPM-V residual
  action head, so LoRA can be the next stage.

## Current RunPod State

Current state:

```text
runpodctl pod list --all -> []
no active pods
```

Old exited pods from the dashboard were deleted:

```text
9obtpq0emwxfrp
1w1hzvr8kf9dwc
borvhykzelprh8
46v22g62dytxww
6pqr6nf9vvqbmt
tdseqidwwxj154
kc8hitul9nsx23
vojlusilehlbpg
```

The later chunk-policy pod was also deleted after artifact download:

```text
x9gjy51o6179qj
288oqe4tpvkcvq
vszxq5pu6avgbu
hkk9skw9d38h5t
xb6dv76ajw7tzq
```

## What Is Running Now

Nothing is currently running.

Reusable RunPod scripts:

```text
fireboy-vla-physics/scripts/train_faithful_articulated_runpod.sh
fireboy-vla-physics/scripts/generate_vla_rollouts_runpod.sh
fireboy-vla-physics/scripts/train_vla_manifest_head_runpod.sh
fireboy-vla-physics/scripts/train_minicpm_vla_action_head_runpod.sh
```

It can train command-conditioned skill policies:

```text
pick_up
go_eat_berry
run_around
go_to_point
```

The first no-stage/single-step run failed for manipulation:

```text
pick_up:       0/20
go_eat_berry: 0/20
```

Diagnosis: the policy likely averaged actions across phases such as approach,
reach, descend, close, lift, and mouth.

Current fix:

```text
pick_up action-chunk:       20/20
go_eat_berry action-chunk: 20/20
```

Current best MiniCPM-V VLA-style gate:

```text
model: openbmb/MiniCPM-V-4.6
MiniCPM-V: frozen
head: state_residual_fusion_v1
training rows: 2048 uniform manipulation rows
GPU: NVIDIA RTX 6000 Ada Generation
pick_up live MuJoCo eval:       3/3
go_eat_berry live MuJoCo eval: 3/3
checkpoint: fireboy-vla-physics/build/checkpoints/fireboy_minicpm_vla_action_head_residual_2048/minicpm_vla_action_head.pt
```

Current best all-skill command router:

```text
model: openbmb/MiniCPM-V-4.6
MiniCPM-V: frozen
head: skill_param_head_v1
GPU: NVIDIA A40
input: image + language + Fire Boy robot state
output: skill_id + target_x, target_y, target_z, radius, speed_hint, object_is_berry
skills: walk_to, run_around, pick_up, find_and_eat_berry
eval rows: 512
skill_accuracy: 1.0
param_mae: 0.017043352127075195
checkpoint: fireboy-vla-physics/build/checkpoints/fireboy_minicpm_vla_skill_param_head/minicpm_vla_skill_param_head.pt
artifact checkpoint: Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_minicpm_vla_skill_param_head/minicpm_vla_skill_param_head.pt
```

This is the current best route for pet commands because it chooses a proven
skill and parameters, then dispatches into MP4-proven MuJoCo policies.

Current LoRA all-skill router checkpoint:

```text
model: openbmb/MiniCPM-V-4.6
MiniCPM-V: LoRA adapters
head: skill_param_head_v1
GPU: NVIDIA A40
seed checkpoint: fireboy_minicpm_vla_skill_param_head
rows: 512
eval rows: 256
skill_accuracy: 1.0
param_mae: 0.06290113925933838
checkpoint: fireboy-vla-physics/build/checkpoints/fireboy_minicpm_vla_lora_skill_param_head/minicpm_vla_lora_skill_param_head.pt
adapter: fireboy-vla-physics/build/checkpoints/fireboy_minicpm_vla_lora_skill_param_head/lora_adapter
artifact checkpoint: Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_minicpm_vla_lora_skill_param_head/minicpm_vla_lora_skill_param_head.pt
```

Decision:

```text
The LoRA router path works and preserves perfect skill selection.
Do not promote it over the frozen router yet: parameter MAE is 0.0629 vs the
frozen router's 0.0170 separate eval MAE.
```

Current LoRA checkpoint:

```text
model: openbmb/MiniCPM-V-4.6
checkpoint: fireboy-vla-physics/build/checkpoints/fireboy_minicpm_vla_lora_residual_512/minicpm_vla_lora_action_head.pt
adapter: fireboy-vla-physics/build/checkpoints/fireboy_minicpm_vla_lora_residual_512/lora_adapter
LoRA rank: 8
rows: 512
initial live MuJoCo eval:
  pick_up:       1/1
  go_eat_berry: 1/1
latest eval-only RunPod gate:
  pick_up:       3/3
  go_eat_berry: 3/3
```

Proof clips:

```text
Fireboy-training-policy-vla/runpod-artifacts/runpod_artifacts/fireboy_minicpm_vla_action_head_residual_2048/minicpm_vla_pick_up_policy_ep000.mp4
Fireboy-training-policy-vla/runpod-artifacts/runpod_artifacts/fireboy_minicpm_vla_action_head_residual_2048/minicpm_vla_go_eat_berry_policy_ep000.mp4
Fireboy-training-policy-vla/runpod-artifacts/runpod_artifacts/fireboy_minicpm_vla_lora_residual_512/minicpm_vla_pick_up_policy_ep000.mp4
Fireboy-training-policy-vla/runpod-artifacts/runpod_artifacts/fireboy_minicpm_vla_lora_residual_512/minicpm_vla_go_eat_berry_policy_ep000.mp4
Fireboy-training-policy-vla/runpod-artifacts/runpod_artifacts/fireboy_minicpm_vla_lora_residual_512_eval_3ep/minicpm_vla_pick_up_policy_ep000.mp4
Fireboy-training-policy-vla/runpod-artifacts/runpod_artifacts/fireboy_minicpm_vla_lora_residual_512_eval_3ep/minicpm_vla_go_eat_berry_policy_ep000.mp4
```

Registry-backed proof gallery:

```text
http://127.0.0.1:65373/fireboy-policy-gallery
validation: checked_paths 31, missing_count 0, ok true
videos ready in browser: 7/7
```

## Immediate Gates

### Gate 1: Cloud Simulator Proof

Already passed on RunPod:

```text
CUDA: available
device: NVIDIA RTX 6000 Ada Generation
remote MuJoCo body MP4 render: success
one-episode demo generation: 4/4 skills success
```

### Gate 2: Stage-Aware Skill Policies

Required pass criteria:

```text
go_to_point:   >= 18/20 eval success
run_around:   >= 18/20 eval success
pick_up:      nonzero success, ideally >= 10/20
go_eat_berry: nonzero success, ideally >= 10/20
```

This gate has now passed for the manipulation-heavy MiniCPM frozen-encoder
action head:

```text
pick_up:       3/3
go_eat_berry: 3/3
```

The older fallback remains available if wider generalization fails:

```text
high-level command policy -> stage/target params
stage controller / IK policy -> joint targets
```

## Newton Plan

Newton is useful because it is a GPU-accelerated physics engine built on NVIDIA
Warp and OpenUSD, with MuJoCo Warp as a primary backend. Official docs describe
it as compatible with robot-learning frameworks including MuJoCo Playground and
Isaac Lab.

Source:

- https://developer.nvidia.com/newton-physics
- https://github.com/newton-physics/newton

RunPod Newton probe after the current policy run finishes:

```bash
pip install "newton[examples]"
python -m newton.examples --list
python -m newton.examples robot_g1 --device cuda:0 --viewer null --num-frames 300
python -m newton.examples robot_policy --device cuda:0 --viewer null --num-frames 300
```

If those pass, the Newton rollout lane is:

```text
Fire Boy MJCF/URDF-like asset
        -> Newton/MuJoCo Warp load test on cuda:0
        -> rollout qpos/action trace
        -> convert trace to MP4/USD/npz artifacts
```

Expected risk:

- Newton may not directly run the custom Fire Boy MJCF without adapter work.
- If the direct Fire Boy load fails, use G1/robot_policy as the validated Newton
  backend and keep Fire Boy in the MuJoCo lane until adapter work is done.

## Kimodo Plan

Kimodo is not a physics controller. It is a kinematic motion diffusion model that
generates human/humanoid motions from text prompts and constraints such as root
paths, waypoints, full-body keyframes, and end-effector controls.

Sources:

- https://github.com/nv-tlabs/kimodo
- https://huggingface.co/nvidia/Kimodo-G1-RP-v1

Useful Kimodo prompts:

```text
"walk forward to a point"
"walk around curiously"
"run in a small circle"
"bend down and pick up an object"
"bring hand to mouth"
"look around and inspect objects"
```

Use Kimodo for:

```text
language/path constraints -> G1/SOMA/SMPL-X kinematic motion
        -> retarget to Fire Boy or supported humanoid
        -> ProtoMotions/Newton/MuJoCo tracking policy
        -> learned physical controller
```

Important limitation from the model card:

- Kimodo is best for locomotion, gestures, dancing, and everyday activities.
- It does not understand scene objects directly.
- It can produce foot sliding and prompt-following artifacts.

That means Kimodo is excellent for walk/run/pet gestures, but berry pickup still
needs a contact-aware manipulation policy in MuJoCo/Newton.

## ProtoMotions Plan

ProtoMotions is the right lane for physically simulated humanoid motion skills.
Its README describes it as a GPU-accelerated framework for simulated digital
humans and humanoid robots, with support for adding custom robots via MuJoCo XML
plus robot config/factory registration.

Source:

- https://github.com/NVlabs/ProtoMotions

Fastest practical route:

```text
Use supported G1/H1/SMPL-like body
        -> train/borrow ProtoMotions locomotion and steering policy
        -> render Fire Boy GLB as costume on top
        -> keep Fire Boy-specific hands/berry manipulation in MuJoCo/Newton
```

Custom Fire Boy direct route:

```text
Fire Boy MJCF
        -> ProtoMotions robot config
        -> register in factory
        -> retarget motion data
        -> train tracking/steering policy
```

This is possible, but not the fastest overnight route.

## MiniCPM-V 4.6 LoRA VLA Plan

Only after a usable policy gate:

```text
MiniCPM-V image/text encoder
        + robot state encoder
        + action head
        + LoRA adapters
        -> next 0.5 sec action chunk
```

Training data row:

```json
{
  "image": "camera frame",
  "instruction": "walk to the berry",
  "robot_state": {
    "qpos": "...",
    "qvel": "...",
    "contacts": "...",
    "target": "..."
  },
  "action_chunk": "next 0.5 seconds of normalized joint targets"
}
```

Initial training:

```text
freeze most MiniCPM-V
train robot-state encoder + action head
then add LoRA adapters to vision/language blocks
```

The VLA is judged by closed-loop rollouts, not training loss alone.

Current status:

```text
frozen MiniCPM-V + residual action head: passed pickup/eat closed-loop eval
LoRA adapters: trained for pickup/eat manipulation gate
current LoRA checkpoint: fireboy_minicpm_vla_lora_residual_512
frozen MiniCPM-V skill-param router: passed all-skill eval on 512 rows
MiniCPM-V LoRA skill-param router: trained and evaled; preserved but not promoted
remaining MiniCPM-V LoRA work: tune schedule/loss or freeze the router head if
we want LoRA to beat the frozen skill-param router
```

All-skill frozen MiniCPM checkpoint status:

```text
checkpoint: fireboy_minicpm_vla_action_head_allskill_3072
pick_up:       2/2
go_eat_berry: 0/2
run_around:   2/2
go_to_point:  0/2
```

Movement-only MiniCPM checkpoint status:

```text
checkpoint: fireboy_minicpm_vla_action_head_movement_992
run_around:  3/3
go_to_point: 1/3
```

So the reliable current pet architecture is specialized but unified at the
command-router layer:

```text
MiniCPM-V skill-param router
  -> walk_to / run_to: articulated go_to_point policy
  -> run_around / walk_around: articulated run_around policy
  -> pick_up: MiniCPM-V LoRA manipulation proof or local MuJoCo fallback
  -> find_and_eat_berry: MiniCPM-V LoRA manipulation proof or local MuJoCo fallback
```

The raw low-level all-command VLA still needs another data/model pass.

## Overnight Execution Order

1. Preserve the current proven checkpoints and MP4/GIF artifacts.
2. Extend MiniCPM-V coverage to movement commands:
   `run_around` and `go_to_point`.
3. Extend the LoRA adapter run from manipulation-only to movement commands.
4. Use Kimodo/ProtoMotions motion priors for walk/run/pet gestures where the
   model access path is unblocked.
5. Use Newton/ProtoMotions as the next physical locomotion lane for a supported
   G1/SMPL-like body, then skin Fire Boy on top.
6. Keep Fire Boy berry pickup/eat in the current MuJoCo contact lane until a
   Newton adapter is worth the extra work.
7. Stop/delete the active pod whenever a cloud command finishes.

## Success Criteria By Morning

Minimum acceptable:

```text
RunPod artifacts exist
go_to_point learned policy MP4 exists
run_around learned policy MP4 exists
controller pickup/eat MP4 exists
old pods deleted
Newton/Kimodo/ProtoMotions feasibility documented from real commands
MiniCPM-V LoRA scaffold/plan ready
```

Strong result:

```text
go_to_point learned policy passes >= 18/20
run_around learned policy passes >= 18/20
pickup/eat learned policies pass closed-loop eval
Newton GPU example passes on cuda:0
Kimodo G1 motion generation or model download path is validated
MiniCPM-V frozen-encoder action head passes pickup/eat eval
```

Excellent result:

```text
Fire Boy/Fire Boy-costumed humanoid locomotion policy uses ProtoMotions/Newton
MiniCPM-V LoRA/action-head training passes pickup/eat closed-loop eval and is
ready for movement-command expansion
```

## Overnight Reality Check

RunPod was used for the additional navigation work, and all created pods were
deleted after artifacts were copied.

What passed:

```text
MiniCPM-V LoRA manipulation: pick_up/go_eat_berry passed
MiniCPM-V frozen skill-param router: 512/512 skill choices correct, param MAE 0.0170
MiniCPM-V LoRA skill-param router: 256/256 skill choices correct, param MAE 0.0629
MiniCPM frozen movement: run_around passed
state/action go_to_point_clock policy: 20/20 and local runtime pass
Toy V3 MuJoCo bridge: walk_to and run_around now return articulated policy MP4/GIF URLs
```

What failed:

```text
MiniCPM direct go_to_point absolute 1-step: 0/5
MiniCPM direct go_to_point root_velocity_v1: 0/5
MiniCPM direct go_to_point recovery root_velocity_v1: 0/5
```

Decision:

```text
Do not use direct MiniCPM root-action navigation as the submitted movement path.
Use the proven articulated movement policies for walk/run/go-to commands.
Keep MiniCPM/LoRA as the VLA manipulation lane and as the future high-level
command/skill router.
```

Router lane result:

```text
input: image + language + robot state
output: skill_id + skill parameters
skills: walk_to, run_around, pick_up, find_and_eat_berry
manifest: Fireboy-training-policy-vla/vla-rollouts/vla_skill_params/fireboy_vla_skill_params_allskill_3072.jsonl
rows: 3072
launcher: fireboy-vla-physics/scripts/train_minicpm_vla_skill_param_head_runpod.sh
checkpoint: Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_minicpm_vla_skill_param_head/minicpm_vla_skill_param_head.pt
eval: skill_accuracy 1.0, param_mae 0.0170 on 512 cached-image rows
```

Promotion gate:

```text
held-out skill_accuracy should be high
target_x/target_y MAE should be small enough to dispatch go_to_point reliably
result must dispatch to registry-backed MuJoCo policies with existing MP4 proof
status: passed for the frozen-encoder router
```

Current runtime routing:

```text
walk_to / run_to:
  Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_articulated_go_to_point_clock/faithful_articulated_policy.npz

run_around / walk_around:
  Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_articulated_run_around/faithful_articulated_policy.npz
```
