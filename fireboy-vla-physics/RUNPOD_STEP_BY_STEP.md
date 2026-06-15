# RunPod Step-By-Step Execution

## Budget Rule

Available RunPod balance checked from `runpodctl user`:

```text
about $45
current spend: $0/hr
```

Use this ladder:

1. Local CPU smoke tests until the MuJoCo task loads and the expert is sane.
2. RunPod RTX 6000 Ada or L40S for setup, ProtoMotions experiments, and medium training.
3. A100 80GB only if memory becomes the blocker.
4. H100/H200 only for a short final sprint, not for debugging setup.

Do not leave pods running idle.

## What We Will Train

Short-window target:

```text
Pet skill policy:
  image/state/language -> skill + target parameters

Low-level controllers:
  walk/run/turn/wave/sit/dance -> ProtoMotions or motion-tracking lane
  pick/reach/carry/drop -> MuJoCo IK/manipulation lane
```

This is the fastest route to a pet-like Fire Boy. The first policy should choose and parameterize skills. Full raw low-level VLA can be trained after the skill data is reliable.

## RunPod Pod Choice

Start with:

```text
NVIDIA RTX 6000 Ada Generation
```

Fallback:

```text
NVIDIA L40S
NVIDIA RTX A6000
NVIDIA GeForce RTX 4090
```

Escalate:

```text
NVIDIA A100-SXM4-80GB
NVIDIA H100 80GB HBM3
NVIDIA H200
```

## Create Pod

Recommended first pod:

```bash
runpodctl pod create \
  --name fireboy-vla-rtx6000 \
  --template-id runpod-torch-v240 \
  --gpu-id "NVIDIA RTX 6000 Ada Generation" \
  --gpu-count 1 \
  --container-disk-in-gb 80 \
  --volume-in-gb 80 \
  --ports "8888/http,22/tcp"
```

If RTX 6000 Ada is unavailable:

```bash
runpodctl pod create \
  --name fireboy-vla-l40s \
  --template-id runpod-torch-v240 \
  --gpu-id "NVIDIA L40S" \
  --gpu-count 1 \
  --container-disk-in-gb 80 \
  --volume-in-gb 80 \
  --ports "8888/http,22/tcp"
```

Check status:

```bash
runpodctl pod list
runpodctl pod get POD_ID
```

## Transfer Repo Pack

From local workspace:

```bash
bash fireboy-vla-physics/scripts/pack_for_runpod.sh
runpodctl send fireboy-vla-physics/build/runpod/fireboy-vla-pack.tgz
```

Inside pod:

```bash
cd /workspace
runpodctl receive TRANSFER_CODE
tar -xzf fireboy-vla-pack.tgz
cd build-small-hackathon-v1
```

## Pod Setup

Inside pod:

```bash
python -m venv /workspace/fireboy-vla-env
source /workspace/fireboy-vla-env/bin/activate
pip install --upgrade pip
pip install -r fireboy-vla-physics/requirements.txt
```

Smoke test:

```bash
python fireboy-vla-physics/src/smoke_test_env.py
```

Generate first dataset:

```bash
python fireboy-vla-physics/src/generate_dataset.py --num-episodes 100 --seed 1
```

Train smoke policy:

```bash
python fireboy-vla-physics/src/train_policy.py --max-steps 2000
python fireboy-vla-physics/src/eval_policy.py --num-episodes 20
```

## ProtoMotions Lane

Clone and install separately inside `/workspace`:

```bash
cd /workspace
git clone https://github.com/NVlabs/ProtoMotions.git
cd ProtoMotions
pip install -e .
```

Then follow ProtoMotions quick start for a supported robot first, preferably G1 or H1_2, before custom Fire Boy.

Reason:

- ProtoMotions already supports humanoid motion learning/tracking and sim-to-sim.
- Its README says custom robots are added by providing a MuJoCo XML, robot config, and factory registration.
- For ASAP, we should use a supported robot/controller and attach Fire Boy visually as a costume.

## Fire Boy Pet Skill Set

Train/log these skills first:

```text
idle_look
look_at_object
walk_to
walk_around
run_around
come_here
wave
sit
jump_happy
dance
inspect_object
reach_object
pick_ball
carry_ball
drop_object
recover_balance
```

Dataset row shape:

```json
{
  "image": "...",
  "instruction": "walk around the room",
  "state": {},
  "skill": "walk_around",
  "params": {
    "path": [[0.4, 0.1], [0.8, -0.2]],
    "speed": 1.0,
    "style": "happy"
  },
  "low_level_trace": "optional path to qpos/action frames",
  "success": true
}
```

## Stop Pod

Always stop when done:

```bash
runpodctl pod stop POD_ID
```

Delete only after artifacts are copied out:

```bash
runpodctl pod delete POD_ID
```
