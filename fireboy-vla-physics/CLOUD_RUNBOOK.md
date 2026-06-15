# Fire Boy VLA Cloud Runbook

## Current Local Cloud Status

Checked from this workspace:

```text
modal: installed, client version 1.5.0
runpod: not found
runpodctl: not found
```

Plan:

- Use Modal first for quick Python jobs and GPU training.
- Use RunPod if we need an interactive persistent GPU box, Jupyter, or longer manual debugging.

## Modal First Path

Modal is the fastest cloud path from this repo because the CLI is present and the project already has Modal code.

Modal docs confirm:

- GPU functions are selected with `@app.function(gpu="A100")`, `gpu="L40S"`, `gpu="H100"`, etc.
- Modal Volumes are persistent file systems suitable for datasets/checkpoints.
- `modal run` is for iteration; `modal deploy` creates a persistent deployment.

### One-Time Modal Setup

If the CLI is authenticated, this should work:

```bash
modal profile current
```

If not:

```bash
modal setup
```

Create storage:

```bash
modal volume create fireboy-vla-data
modal volume create fireboy-vla-checkpoints
```

### Intended Modal Files To Build Next

```text
fireboy-vla-physics/
  modal_jobs.py
  src/
    fireboy_mjcf.py
    pick_ball_env.py
    ik_expert.py
    dataset.py
    train_policy.py
    eval_policy.py
```

### Modal Job Shape

`modal_jobs.py` should expose:

```text
generate_mjcf()
smoke_test_env()
generate_dataset(num_episodes, seed)
train_policy(dataset_path, max_steps)
eval_policy(checkpoint_path, num_episodes)
render_rollout(checkpoint_path, seed)
```

### Modal Commands

Smoke test:

```bash
modal run fireboy-vla-physics/modal_jobs.py::smoke_test_env
```

Generate small dataset:

```bash
modal run fireboy-vla-physics/modal_jobs.py::generate_dataset --num-episodes 200 --seed 1
```

Generate larger dataset:

```bash
modal run fireboy-vla-physics/modal_jobs.py::generate_dataset --num-episodes 2000 --seed 10
```

Train:

```bash
modal run fireboy-vla-physics/modal_jobs.py::train_policy --max-steps 5000
```

Evaluate:

```bash
modal run fireboy-vla-physics/modal_jobs.py::eval_policy --num-episodes 25
```

Render rollout:

```bash
modal run fireboy-vla-physics/modal_jobs.py::render_rollout --seed 42
```

Deploy an inference endpoint only after a local/cloud smoke test:

```bash
modal deploy fireboy-vla-physics/modal_jobs.py
```

### Recommended Modal GPUs

Fast iteration:

```text
L4 or A10
```

Dataset generation plus small training:

```text
L40S or A100
```

If we use MiniCPM-V 4.6 with a trainable head:

```text
A100-40GB, A100-80GB, L40S, or H100
```

Use cheaper GPU for environment/data first. Upgrade only when training needs memory.

## RunPod Backup Path

RunPod is better if we need a persistent interactive GPU machine.

The current CLI is `runpodctl`, not `runpod`.

### Install RunPod CLI

Official docs list macOS install options:

```bash
brew install runpod/runpodctl/runpodctl
```

or:

```bash
bash <(curl -sL cli.runpod.io)
```

Configure:

```bash
runpodctl doctor
```

or:

```bash
runpodctl config --apiKey "$RUNPOD_API_KEY"
```

Check:

```bash
runpodctl gpu list
runpodctl template search pytorch
```

### Create A Pod

Example from current docs:

```bash
runpodctl pod create \
  --name fireboy-vla \
  --template-id runpod-torch-v21 \
  --gpu-id "NVIDIA GeForce RTX 4090" \
  --volume-in-gb 80 \
  --container-disk-in-gb 80 \
  --ports "8888/http,22/tcp"
```

If a template is not available:

```bash
runpodctl pod create \
  --name fireboy-vla \
  --image "runpod/pytorch:2.8.0-py3.11-cuda12.8.1-cudnn-devel-ubuntu22.04" \
  --gpu-id "NVIDIA GeForce RTX 4090" \
  --volume-in-gb 80 \
  --container-disk-in-gb 80 \
  --ports "8888/http,22/tcp"
```

List pods:

```bash
runpodctl pod list
```

Get SSH info:

```bash
runpodctl ssh info POD_ID
```

### Transfer Files

Fast one-time transfer:

```bash
tar -czf fireboy-vla-physics.tgz fireboy-vla-physics fire-boy-rig/fire-boy-rigged-full.glb pyproject.toml uv.lock
runpodctl send fireboy-vla-physics.tgz
```

Then inside the pod:

```bash
runpodctl receive TRANSFER_CODE
tar -xzf fireboy-vla-physics.tgz
```

For full SSH/SCP, RunPod docs say full SSH requires public IP / exposed TCP 22. Once available:

```bash
scp -P SSH_PORT -i ~/.ssh/id_ed25519 fireboy-vla-physics.tgz root@POD_IP:/workspace/
```

### Pod Setup Commands

Inside pod:

```bash
cd /workspace/build-small-hackathon-v1
python -m venv .venv-vla
source .venv-vla/bin/activate
pip install --upgrade pip
pip install mujoco gymnasium numpy scipy pillow imageio imageio-ffmpeg torch torchvision transformers accelerate datasets safetensors
```

If using MiniCPM-V 4.6:

```bash
pip install transformers accelerate timm einops sentencepiece
```

Then:

```bash
python fireboy-vla-physics/src/smoke_test_env.py
python fireboy-vla-physics/src/generate_dataset.py --num-episodes 2000
python fireboy-vla-physics/src/train_policy.py --max-steps 5000
python fireboy-vla-physics/src/eval_policy.py --num-episodes 25
```

### Stop Pod When Done

```bash
runpodctl pod stop POD_ID
```

Terminate only when artifacts are downloaded or persisted:

```bash
runpodctl pod delete POD_ID
```

## 8-Hour Cloud Strategy

Use this ordering:

1. Build and test MuJoCo body locally on CPU.
2. Use Modal for `smoke_test_env`.
3. Use Modal to generate 200 demo episodes.
4. If stable, generate 2000+ episodes.
5. Train a small action head on Modal.
6. If Modal iteration becomes awkward, move to RunPod persistent pod.

## Artifact Checklist

Cloud jobs should write:

```text
/data/fireboy-vla/
  mjcf/fireboy.xml
  datasets/fireboy_pick_ball/
  checkpoints/
  eval/
  rollouts/
```

Each job should print:

```text
episode_count
expert_success_rate
dataset_path
checkpoint_path
eval_success_rate
rollout_video_path
```

## Decision Rule

If MuJoCo body loading takes more than 90 minutes:

- freeze body complexity
- use a simpler arm-on-Fire-Boy base
- preserve the same observation/action/dataset format

If MiniCPM-V integration takes more than 90 minutes:

- train a smaller frozen vision encoder policy first
- keep MiniCPM-V as the next swap-in

The core deliverable is the physics/data/control loop, not the prettiest backbone on day one.
