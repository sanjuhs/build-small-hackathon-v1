# Fire Boy Local Submission Demo

This folder now contains two MuJoCo lanes for Fire Boy:

```text
legacy smoke lane
  -> old two-hand berry harness
  -> learned local checkpoint

faithful articulated lane
  -> Fireboy-shaped connected physics body
  -> command-conditioned joint-target demonstrations
  -> RunPod retraining path for pick/eat/run
```

The included learned checkpoint is only for the legacy smoke lane:

```text
fireboy-vla-physics/checkpoints/berry_eat_wide/state_policy.npz
```

The Torch checkpoint used for cloud training/eval is stored under `build/` when available:

```text
fireboy-vla-physics/build/checkpoints/berry_eat_wide/state_policy.pt
```

## Run The Local Demo

Use the local demo wrapper:

```bash
bash fireboy-vla-physics/scripts/run_local_demo.sh
```

It should:

- route pet commands such as walk/run/wave/sit/dance,
- run the learned berry-eat policy locally,
- render a GIF to:

```text
fireboy-vla-physics/build/submission/learned_berry_eat.gif
```

You can run a single command:

```bash
bash fireboy-vla-physics/scripts/run_pet_command.sh "go find berry and eat it"
bash fireboy-vla-physics/scripts/run_pet_command.sh "walk around"
```

## Run Inside ToyV3 / Gradio

Start the Gradio/FastAPI app:

```bash
./start.sh
```

Open:

```text
http://127.0.0.1:65372/toy-v3
```

Then type:

```text
Fire Boy, go find berry and eat it using the MuJoCo policy
```

ToyV3 routes that command through `/api/pet-action`, runs the local MuJoCo policy, returns a normal PET `eat` action for the Three.js room, and shows the learned-policy rollout GIF from:

```text
/fireboy-vla/build/toy-v3-policy/learned_berry_eat.gif
```

## Inspect The MuJoCo Policies

The dedicated MuJoCo viewer is:

```text
http://127.0.0.1:65372/mujoco-policy
```

It renders three modes from the actual MuJoCo model:

- `Rest / Physics Body`: shows the current MuJoCo body.
- `IK Expert Rollout`: shows the privileged demonstration policy.
- `Learned Policy Rollout`: shows the trained checkpoint rollout.

The generated media files are under:

```text
fireboy-vla-physics/build/showcase/
```

Important: the first three viewer modes are the legacy bimanual manipulation harness. It has a static Fire Boy visual body and two actuated Cartesian hand controllers:

```text
hand_R_x, hand_R_y, hand_R_z,
hand_L_x, hand_L_y, hand_L_z
```

That is enough to show learned two-hand berry grasp/eat behavior, but it is not the body we should use for serious Fireboy policy training.

## Articulated Fireboy Proof

A separate connected-body proof now exists and is the new body gate for retraining:

```bash
MUJOCO_GL=glfw fireboy-vla-physics/.venv/bin/python \
  fireboy-vla-physics/src/render_articulated_fireboy.py --mode all
```

Generated media:

```text
fireboy-vla-physics/build/articulated/fireboy_articulated_body.mp4
fireboy-vla-physics/build/articulated/fireboy_articulated_run_around.mp4
fireboy-vla-physics/build/articulated/fireboy_articulated_pick_up.mp4
fireboy-vla-physics/build/articulated/fireboy_articulated_go_eat_berry.mp4
fireboy-vla-physics/build/articulated/articulated_report.json
```

This MJCF is rebuilt from `fireboy_articulated_mjcf.py` with Fireboy-like proportions measured from the real GLB: big round head, short rounded torso, short arms, small legs/feet, and attached paw/gripper helpers. It has 23 bodies, 33 joints, and 32 actuators:

```text
root slides/yaw -> pelvis
pelvis -> spine -> chest -> neck -> head/flame
chest -> shoulders -> elbows -> wrists -> gripper fingers
pelvis -> hips -> knees -> ankles -> feet
```

The proof succeeds for body inspection, assisted run-around, connected-arm pickup, and go-eat-berry. It is still an expert/controller proof, not a learned ProtoMotions or end-to-end VLA policy.

Do not train new serious policies on the older `fireboy_two_hand_pick_ball.xml` harness. Regenerate and use:

```text
fireboy-vla-physics/build/fireboy_articulated.xml
```

If the local environment is missing packages:

```bash
python3 -m venv fireboy-vla-physics/.venv
fireboy-vla-physics/.venv/bin/pip install -r fireboy-vla-physics/requirements-local.txt
```

## Faithful Retrain On RunPod

The repeatable training path for the faithful Fireboy body is:

```bash
bash fireboy-vla-physics/scripts/train_faithful_articulated_runpod.sh
```

Defaults:

- GPU: `NVIDIA RTX A6000`
- demos: `600` per task for `pick_up`, `go_eat_berry`, and `run_around`
- mixed policy training: disabled by default because the first run overfit pick and failed eat/run
- per-skill train steps: `22000`
- eval: `20` held-out episodes per task
- action smoothing: `0.20`

Override defaults with environment variables:

```bash
GPU_ID="NVIDIA RTX A6000" \
NUM_EPISODES=1000 \
SKILL_MAX_STEPS=30000 \
bash fireboy-vla-physics/scripts/train_faithful_articulated_runpod.sh
```

Use an existing pod:

```bash
POD_ID=your_pod_id bash fireboy-vla-physics/scripts/train_faithful_articulated_runpod.sh
```

The script stops the pod at the end and downloads:

```text
fireboy-vla-physics/build/checkpoints/fireboy_articulated_all/faithful_articulated_policy.pt
fireboy-vla-physics/build/checkpoints/fireboy_articulated_all/faithful_articulated_policy.npz
fireboy-vla-physics/checkpoints/fireboy_articulated_all/faithful_articulated_policy.npz
fireboy-vla-physics/build/checkpoints/fireboy_articulated_all/eval_pick_up.json
fireboy-vla-physics/build/checkpoints/fireboy_articulated_all/eval_go_eat_berry.json
fireboy-vla-physics/build/checkpoints/fireboy_articulated_all/eval_run_around.json
fireboy-vla-physics/build/checkpoints/fireboy_articulated_pick_up/faithful_articulated_policy.pt
fireboy-vla-physics/build/checkpoints/fireboy_articulated_pick_up/faithful_articulated_policy.npz
fireboy-vla-physics/build/checkpoints/fireboy_articulated_run_around/faithful_articulated_policy.pt
fireboy-vla-physics/build/checkpoints/fireboy_articulated_run_around/faithful_articulated_policy.npz
fireboy-vla-physics/build/checkpoints/fireboy_articulated_go_eat_berry/faithful_articulated_policy.pt
fireboy-vla-physics/build/checkpoints/fireboy_articulated_go_eat_berry/faithful_articulated_policy.npz
```

Latest RunPod A6000 result:

```text
faithful expert demos: 1800 episodes
  pick_up:       600/600
  go_eat_berry:  599/600
  run_around:    600/600

mixed learned checkpoint:
  pick_up:       20/20
  go_eat_berry:   0/20
  run_around:     0/20

separate learned checkpoints:
  pick_up:       15/20
  go_eat_berry:   0/20
  run_around:    18/20

phase-conditioned learned eat:
  full-state phase BC:  0/30
  clocked phase BC:     0/30
```

Local NumPy-rendered learned previews:

```text
fireboy-vla-physics/build/articulated_policy/faithful_learned_pick_up.mp4      success=True
fireboy-vla-physics/build/articulated_policy/faithful_learned_run_around.mp4   success=True
fireboy-vla-physics/build/articulated_policy/faithful_learned_go_eat_berry.mp4 success=False, grasps but does not reach mouth
fireboy-vla-physics/build/articulated_policy_phase_clock/faithful_learned_go_eat_berry.mp4 success=False, does not establish stable grasp
```

Interpretation: the faithful physics body and demonstration generator are good enough to train against. Plain behavior cloning is not yet good enough for the full eat sequence, even with phase/clock features. The learned eat lane needs recovery/DAgger data or RL fine-tuning around grasp stability and grasp-to-mouth transition before we claim a learned eat policy.

The old script remains available as a legacy comparison only:

```bash
bash fireboy-vla-physics/scripts/train_berry_runpod.sh
```

Do not use that legacy checkpoint as proof of the faithful Fireboy body.

## What This Is

This is a real learned physics control slice, but it is not yet a fully general end-to-end MiniCPM-V VLA.

Current working architecture:

```text
text command
  -> skill router
  -> low-level policy lane
  -> MuJoCo continuous actions
```

For the legacy berry task, the low-level policy is learned from expert MuJoCo demonstrations. For the faithful articulated lane, `generate_articulated_dataset.py` creates command-conditioned demonstrations on the Fireboy-shaped 32-actuator body, and `train_articulated_policy.py` trains a policy to output normalized joint targets.

What can work on the fly now:

- known pet skills: walk/run route, wave, sit, dance,
- the legacy learned `go find berry and eat it` manipulation policy,
- faithful articulated expert proofs for pick/eat/run,
- commands that map to these known skills.

What needs the next training stage:

- robust learned `go_eat_berry` on the faithful body,
- arbitrary unseen manipulation commands,
- camera-only control,
- MiniCPM-V language+vision encoder conditioning,
- many object/action demonstrations,
- locomotion from ProtoMotions/Kimodo instead of the current route-level locomotion lane.

The honest next VLA upgrade is:

```text
camera image + language + qpos/qvel
  -> MiniCPM-V / vision-language encoder
  -> action head
  -> same MuJoCo action space
```

The environment, demos, checkpoint runner, and cloud training loop are already set up so that upgrade can reuse the same data pipeline.
