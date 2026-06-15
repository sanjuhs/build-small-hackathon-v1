#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
POD_ID="${POD_ID:-}"
GPU_ID="${GPU_ID:-NVIDIA A40}"
POD_NAME="${POD_NAME:-fireboy-minicpm-vla-eval}"
IMAGE="${IMAGE:-runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04}"
CHECKPOINT_DIR="${CHECKPOINT_DIR:-$ROOT/Fireboy-training-policy-vla/runpod-artifacts/checkpoints/fireboy_minicpm_vla_lora_residual_512}"
CHECKPOINT_FILE="${CHECKPOINT_FILE:-minicpm_vla_lora_action_head.pt}"
EVAL_TASKS="${EVAL_TASKS:-pick_up go_eat_berry}"
EVAL_EPISODES="${EVAL_EPISODES:-3}"
REPLAN_INTERVAL="${REPLAN_INTERVAL:-8}"
SMOOTH_ALPHA="${SMOOTH_ALPHA:-0.0}"
EVAL_SEED="${EVAL_SEED:-27100}"
REMOTE_ROOT="/workspace"
REMOTE_PROJECT="$REMOTE_ROOT/fireboy-vla-physics"
REMOTE_CHECKPOINT_DIR="$REMOTE_ROOT/checkpoint"
RUN_NAME="${RUN_NAME:-$(basename "$CHECKPOINT_DIR")_eval_${EVAL_EPISODES}ep}"
LOCAL_RUNPOD_ARTIFACT_DIR="$ROOT/Fireboy-training-policy-vla/runpod-artifacts"
STOP_ON_EXIT=0
CREATED_POD=0
DELETE_CREATED_POD="${DELETE_CREATED_POD:-1}"

if [[ ! -d "$CHECKPOINT_DIR" ]]; then
  echo "Missing checkpoint directory: $CHECKPOINT_DIR" >&2
  exit 1
fi
if [[ ! -f "$CHECKPOINT_DIR/$CHECKPOINT_FILE" ]]; then
  echo "Missing checkpoint file: $CHECKPOINT_DIR/$CHECKPOINT_FILE" >&2
  exit 1
fi

json_get() {
  python3 -c 'import json,sys; data=json.load(sys.stdin); path=sys.argv[1].split("."); cur=data
for key in path:
    cur=cur[int(key)] if isinstance(cur, list) else cur[key]
print(cur)' "$1"
}

pod_get() {
  runpodctl pod get "$POD_ID"
}

if [[ -z "$POD_ID" ]]; then
  echo "Creating RunPod pod on $GPU_ID..."
  create_json="$(runpodctl pod create \
    --name "$POD_NAME" \
    --image "$IMAGE" \
    --gpu-id "$GPU_ID" \
    --container-disk-in-gb 75 \
    --volume-in-gb 50 \
    --ports "22/tcp")"
  POD_ID="$(printf '%s' "$create_json" | json_get id)"
  STOP_ON_EXIT=1
  CREATED_POD=1
else
  echo "Using existing pod $POD_ID..."
  runpodctl pod start "$POD_ID" >/dev/null
  STOP_ON_EXIT=1
fi

cleanup() {
  if [[ "$STOP_ON_EXIT" == "1" && -n "${POD_ID:-}" && "${KEEP_POD_RUNNING:-0}" != "1" ]]; then
    runpodctl pod stop "$POD_ID" >/dev/null 2>&1 || true
    if [[ "$CREATED_POD" == "1" && "$DELETE_CREATED_POD" == "1" ]]; then
      runpodctl pod delete "$POD_ID" >/dev/null 2>&1 || true
    fi
  fi
}
trap cleanup EXIT

echo "Waiting for SSH on pod $POD_ID..."
ssh_json=""
for _ in $(seq 1 60); do
  pod_json="$(pod_get)"
  if printf '%s' "$pod_json" | python3 -c 'import json,sys; data=json.load(sys.stdin); sys.exit(0 if data.get("ssh", {}).get("ip") and data.get("ssh", {}).get("port") else 1)'; then
    ssh_json="$pod_json"
    break
  fi
  sleep 5
done
if [[ -z "$ssh_json" ]]; then
  echo "Pod did not expose SSH in time. Check: runpodctl pod get $POD_ID" >&2
  exit 1
fi

SSH_IP="$(printf '%s' "$ssh_json" | json_get ssh.ip)"
SSH_PORT="$(printf '%s' "$ssh_json" | json_get ssh.port)"
SSH_KEY="$(printf '%s' "$ssh_json" | json_get ssh.ssh_key.path)"
SSH=(ssh -o StrictHostKeyChecking=no -p "$SSH_PORT" -i "$SSH_KEY" "root@$SSH_IP")
SCP=(scp -o StrictHostKeyChecking=no -P "$SSH_PORT" -i "$SSH_KEY")

echo "Packing source and checkpoint..."
PACK="$ROOT/fireboy-vla-physics/build/runpod/fireboy-minicpm-vla-eval-source.tgz"
CHECKPOINT_PACK="$ROOT/fireboy-vla-physics/build/runpod/fireboy-minicpm-vla-eval-checkpoint.tgz"
mkdir -p "$(dirname "$PACK")"
cd "$ROOT"
COPYFILE_DISABLE=1 tar \
  --no-xattrs \
  --exclude='fireboy-vla-physics/.venv' \
  --exclude='fireboy-vla-physics/build' \
  --exclude='**/__pycache__' \
  --exclude='**/._*' \
  --exclude='.git' \
  -czf "$PACK" \
  fireboy-vla-physics
COPYFILE_DISABLE=1 tar --no-xattrs --exclude='**/._*' -czf "$CHECKPOINT_PACK" -C "$CHECKPOINT_DIR" .

echo "Uploading source and checkpoint..."
"${SCP[@]}" "$PACK" "root@$SSH_IP:$REMOTE_ROOT/fireboy-minicpm-vla-eval-source.tgz"
"${SCP[@]}" "$CHECKPOINT_PACK" "root@$SSH_IP:$REMOTE_ROOT/fireboy-minicpm-vla-eval-checkpoint.tgz"

echo "Evaluating MiniCPM-V checkpoint on RunPod..."
"${SSH[@]}" "set -euo pipefail
cd $REMOTE_ROOT
rm -rf $REMOTE_PROJECT $REMOTE_CHECKPOINT_DIR
tar --no-same-owner -xzf fireboy-minicpm-vla-eval-source.tgz
mkdir -p $REMOTE_CHECKPOINT_DIR
tar --no-same-owner -xzf fireboy-minicpm-vla-eval-checkpoint.tgz -C $REMOTE_CHECKPOINT_DIR
apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq libosmesa6 libosmesa6-dev libgl1 libglfw3 >/dev/null
python -m pip install -q -r $REMOTE_PROJECT/requirements.txt
python -m pip install -q 'transformers[torch]>=5.7.0' torchvision av accelerate safetensors peft
python - <<'PY'
import torch
import transformers
import peft
print({'torch': torch.__version__, 'transformers': transformers.__version__, 'peft': peft.__version__, 'cuda_available': torch.cuda.is_available(), 'device': torch.cuda.get_device_name(0) if torch.cuda.is_available() else None})
if not torch.cuda.is_available():
    raise SystemExit('CUDA is not available on this pod.')
PY
export MUJOCO_GL=osmesa
export PYOPENGL_PLATFORM=osmesa
OUT_DIR=$REMOTE_PROJECT/build/runpod_artifacts/$RUN_NAME
RESULT_DIR=$REMOTE_PROJECT/build/checkpoints/$RUN_NAME
mkdir -p \$OUT_DIR \$RESULT_DIR
for TASK in $EVAL_TASKS; do
  python $REMOTE_PROJECT/src/eval_minicpm_vla_policy.py \
    --checkpoint $REMOTE_CHECKPOINT_DIR/$CHECKPOINT_FILE \
    --task \$TASK \
    --num-episodes $EVAL_EPISODES \
    --seed $EVAL_SEED \
    --replan-interval $REPLAN_INTERVAL \
    --smooth-alpha $SMOOTH_ALPHA \
    --out-dir \$OUT_DIR \
    | tee \$RESULT_DIR/eval_\${TASK}_minicpm_vla.json
done
cd $REMOTE_PROJECT/build
tar -czf fireboy-minicpm-vla-eval-artifacts.tgz checkpoints/$RUN_NAME runpod_artifacts/$RUN_NAME
"

echo "Downloading eval artifacts..."
mkdir -p "$LOCAL_RUNPOD_ARTIFACT_DIR"
"${SCP[@]}" "root@$SSH_IP:$REMOTE_PROJECT/build/fireboy-minicpm-vla-eval-artifacts.tgz" "$LOCAL_RUNPOD_ARTIFACT_DIR/fireboy-minicpm-vla-eval-artifacts.tgz"
tar -xzf "$LOCAL_RUNPOD_ARTIFACT_DIR/fireboy-minicpm-vla-eval-artifacts.tgz" -C "$LOCAL_RUNPOD_ARTIFACT_DIR"

echo "Stopping pod $POD_ID..."
runpodctl pod stop "$POD_ID" >/dev/null || true
if [[ "$CREATED_POD" == "1" && "$DELETE_CREATED_POD" == "1" ]]; then
  echo "Deleting created pod $POD_ID..."
  runpodctl pod delete "$POD_ID" >/dev/null || true
fi
STOP_ON_EXIT=0
trap - EXIT

echo "Done."
echo "Pod: $POD_ID"
echo "Run name: $RUN_NAME"
echo "RunPod artifact root: $LOCAL_RUNPOD_ARTIFACT_DIR"
