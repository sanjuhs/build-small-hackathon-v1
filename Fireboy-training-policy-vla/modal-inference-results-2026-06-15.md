# Modal Inference Results: Fire Boy MiniCPM-V Router

Date: 2026-06-15

## Live Endpoint

```text
Modal app: fireboy-vla-router
URL: https://sanjuhs123--fireboy-vla-router.modal.run
GPU: L40S
idle scaledown window: 60 seconds
checkpoint: Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_minicpm_vla_skill_param_head/minicpm_vla_skill_param_head.pt
model: openbmb/MiniCPM-V-4.6
policy_kind: minicpm_vla_frozen_encoder_skill_param_head_v1
```

This endpoint serves the promoted frozen MiniCPM-V skill/parameter router with a
custom PyTorch action head. It is not served through vLLM because the router
needs MiniCPM hidden states plus a custom continuous head, not token generation.

## Local Website Wiring

```text
TOYBOX_VLA_ROUTER_URL=https://sanjuhs123--fireboy-vla-router.modal.run
TOYBOX_VLA_ROUTER_ACTION=1
local app: http://127.0.0.1:65373
policy gallery: http://127.0.0.1:65373/fireboy-policy-gallery
```

The Toy Room path is:

```text
browser command -> /api/pet-action
  -> Modal /route
  -> MiniCPM-V frozen encoder + skill/parameter head
  -> MuJoCo policy registry dispatch
  -> Toy Room animation/result JSON
```

## Verification Matrix

All commands below were tested through the local website API on 2026-06-15.
The VLA router ran on Modal with `device: cuda`.

```text
walk to the yellow marker
  served skill: walk_to
  dispatch: registry:walk_to
  /api/pet-action: success true
  animation: walk

run around
  served skill: run_around
  dispatch: registry:run_around
  /api/pet-action: success true
  animation: run

pick up the berry
  served skill: pick_up
  dispatch: registry:pick_up
  /api/pet-action: success true
  animation: hold

go find berry and eat it
  served skill: find_and_eat_berry
  dispatch: registry:find_and_eat_berry
  /api/pet-action: success true
  animation: hold
```

## Important Runtime Guard

With a blank/generated camera frame, the raw neural skill head can become
overconfident toward `find_and_eat_berry`. The live endpoint therefore exposes:

```text
neural_skill: raw MiniCPM-V head prediction
skill: command/scene-stabilized served skill
raw_params: raw continuous head output
params: scene-grounded served parameters
```

This keeps the demo reliable while preserving transparency. If the browser sends
a real camera frame and full robot state, the same endpoint can be tested with
`force_neural_skill: true` to inspect the pure neural decision.

## Proof Screenshot

```text
Fireboy-training-policy-vla/proofs/modal-vla-router-policy-gallery.png
```

## Repeatable Final Smoke Gate

Run this before submission:

```bash
PYTHONPATH=fireboy-vla-physics/src \
fireboy-vla-physics/.venv/bin/python \
fireboy-vla-physics/src/final_vla_demo_smoke.py \
  --out Fireboy-training-policy-vla/proofs/final-vla-demo-smoke.json
```

Latest result:

```text
ok: true
route checks: walk_to, run_around, pick_up, find_and_eat_berry all passed on cuda
pet-action checks: all four commands dispatched through Modal VLA + MuJoCo successfully
registry validation: checked_paths 49, missing_count 0
RunPod pods in proof: []
```

Proof JSON:

```text
Fireboy-training-policy-vla/proofs/final-vla-demo-smoke.json
```
