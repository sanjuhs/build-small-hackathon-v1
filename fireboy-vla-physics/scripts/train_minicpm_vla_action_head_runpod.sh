#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
POD_ID="${POD_ID:-}"
GPU_ID="${GPU_ID:-NVIDIA GeForce RTX 4090}"
POD_NAME="${POD_NAME:-fireboy-minicpm-vla-head}"
IMAGE="${IMAGE:-runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04}"
MINICPM_MODEL_ID="${MINICPM_MODEL_ID:-openbmb/MiniCPM-V-4.6}"
LIMIT_ROWS="${LIMIT_ROWS:-48}"
MAX_STEPS="${MAX_STEPS:-600}"
TASK_FILTERS="${TASK_FILTERS:-pick_up go_eat_berry}"
EVAL_TASKS="${EVAL_TASKS:-pick_up}"
EVAL_EPISODES="${EVAL_EPISODES:-1}"
REPLAN_INTERVAL="${REPLAN_INTERVAL:-10}"
SMOOTH_ALPHA="${SMOOTH_ALPHA:-0.0}"
DOWNSAMPLE_MODE="${DOWNSAMPLE_MODE:-16x}"
MAX_SLICE_NUMS="${MAX_SLICE_NUMS:-9}"
HEAD_ARCHITECTURE="${HEAD_ARCHITECTURE:-state_residual_fusion_v1}"
VL_RESIDUAL_SCALE="${VL_RESIDUAL_SCALE:-0.15}"
ACTION_STD_FLOOR="${ACTION_STD_FLOOR:-0.01}"
STATE_MODE="${STATE_MODE:-clock}"
ACTION_TARGET_MODE="${ACTION_TARGET_MODE:-absolute_joint_targets}"
ROOT_VELOCITY_MAX_STEP_M="${ROOT_VELOCITY_MAX_STEP_M:-0.035}"
RUN_EVAL="${RUN_EVAL:-1}"
REMOTE_ROOT="/workspace"
REMOTE_PROJECT="$REMOTE_ROOT/fireboy-vla-physics"
HEAD_NAME="${HEAD_NAME:-fireboy_minicpm_vla_action_head}"
LOCAL_RUNPOD_ARTIFACT_DIR="$ROOT/Fireboy-training-policy-vla/runpod-artifacts"
LOCAL_CHECKPOINT_DIR="$ROOT/fireboy-vla-physics/build/checkpoints/$HEAD_NAME"
STOP_ON_EXIT=0
CREATED_POD=0
DELETE_CREATED_POD="${DELETE_CREATED_POD:-1}"

if [[ -z "${VLA_ROLLOUT_ARCHIVE:-}" ]]; then
  VLA_ROLLOUT_ARCHIVE="$(find "$ROOT/Fireboy-training-policy-vla/vla-rollouts" -maxdepth 1 -name 'fireboy-vla-rollouts-manip-*.tgz' | sort | tail -n 1)"
fi
if [[ -z "$VLA_ROLLOUT_ARCHIVE" || ! -f "$VLA_ROLLOUT_ARCHIVE" ]]; then
  echo "No VLA rollout archive found. Run scripts/generate_vla_rollouts_runpod.sh first." >&2
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
    --container-disk-in-gb 70 \
    --volume-in-gb 50 \
    --ports "22/tcp")"
  POD_ID="$(printf '%s' "$create_json" | json_get id)"
  STOP_ON_EXIT=1
  CREATED_POD=1
else
  echo "Using existing pod $POD_ID..."
  if ! runpodctl pod start "$POD_ID" >/dev/null; then
    echo "Could not start existing pod $POD_ID. Try again later or omit POD_ID to create a fresh pod." >&2
    exit 1
  fi
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

echo "Packing source..."
PACK="$ROOT/fireboy-vla-physics/build/runpod/fireboy-minicpm-vla-source.tgz"
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

echo "Uploading source and VLA rollout archive..."
"${SCP[@]}" "$PACK" "root@$SSH_IP:$REMOTE_ROOT/fireboy-minicpm-vla-source.tgz"
"${SCP[@]}" "$VLA_ROLLOUT_ARCHIVE" "root@$SSH_IP:$REMOTE_ROOT/vla-rollouts.tgz"

echo "Training MiniCPM-V frozen-encoder action head on RunPod..."
"${SSH[@]}" "set -euo pipefail
cd $REMOTE_ROOT
rm -rf $REMOTE_PROJECT
tar --no-same-owner -xzf fireboy-minicpm-vla-source.tgz
mkdir -p $REMOTE_PROJECT/build/imported_vla_rollouts
tar --no-same-owner -xzf vla-rollouts.tgz -C $REMOTE_PROJECT/build/imported_vla_rollouts
MANIFEST=\$(find $REMOTE_PROJECT/build/imported_vla_rollouts -path '*/vla_manifests/*.jsonl' | sort | tail -n 1)
DATASET=\$(find $REMOTE_PROJECT/build/imported_vla_rollouts/datasets -mindepth 1 -maxdepth 1 -type d | sort | tail -n 1)
if [[ -z \"\$DATASET\" ]]; then
  echo 'Could not find imported VLA dataset directory' >&2
  exit 1
fi
python - \"\$MANIFEST\" \"\$DATASET\" <<'PY'
import json
import sys
from pathlib import Path
manifest = Path(sys.argv[1])
dataset = Path(sys.argv[2])
fixed = []
for line in manifest.read_text(encoding='utf-8').splitlines():
    if not line.strip():
        continue
    row = json.loads(line)
    path = Path(row.get('image_path', ''))
    if not path.exists():
        text = str(path)
        marker = '/images/'
        if marker in text:
            row['image_path'] = str(dataset / 'images' / text.split(marker, 1)[1])
    fixed.append(json.dumps(row, ensure_ascii=True))
manifest.write_text('\\n'.join(fixed) + '\\n', encoding='utf-8')
print({'manifest': str(manifest), 'dataset': str(dataset), 'rows': len(fixed)})
PY
apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq libosmesa6 libosmesa6-dev libgl1 libglfw3 >/dev/null
python -m pip install -q -r $REMOTE_PROJECT/requirements.txt
python -m pip install -q 'transformers[torch]>=5.7.0' torchvision av accelerate safetensors
python - <<'PY'
import torch
import transformers
print({'torch': torch.__version__, 'transformers': transformers.__version__, 'cuda_available': torch.cuda.is_available(), 'device': torch.cuda.get_device_name(0) if torch.cuda.is_available() else None})
if not torch.cuda.is_available():
    raise SystemExit('CUDA is not available on this pod.')
PY
export MUJOCO_GL=osmesa
export PYOPENGL_PLATFORM=osmesa
OUT_DIR=$REMOTE_PROJECT/build/checkpoints/$HEAD_NAME
mkdir -p \$OUT_DIR
TASK_ARGS=''
for TASK in $TASK_FILTERS; do
  TASK_ARGS=\"\$TASK_ARGS --task-filter \$TASK\"
done
python $REMOTE_PROJECT/src/train_minicpm_vla_action_head.py \
  --manifest \$MANIFEST \
  --out-dir \$OUT_DIR \
  --model-id $MINICPM_MODEL_ID \
  --limit-rows $LIMIT_ROWS \
  --max-steps $MAX_STEPS \
  --state-mode $STATE_MODE \
  --include-stage-flags \
  --downsample-mode $DOWNSAMPLE_MODE \
  --max-slice-nums $MAX_SLICE_NUMS \
  --head-architecture $HEAD_ARCHITECTURE \
  --vl-residual-scale $VL_RESIDUAL_SCALE \
  --action-std-floor $ACTION_STD_FLOOR \
  --action-target-mode $ACTION_TARGET_MODE \
  --root-velocity-max-step-m $ROOT_VELOCITY_MAX_STEP_M \
  --embedding-cache \$OUT_DIR/minicpm_embedding_cache.npz \
  \$TASK_ARGS \
  | tee \$OUT_DIR/train_minicpm_vla_action_head.json
mkdir -p $REMOTE_PROJECT/build/runpod_artifacts/$HEAD_NAME
if [[ '$RUN_EVAL' == '1' ]]; then
  for TASK in $EVAL_TASKS; do
    python $REMOTE_PROJECT/src/eval_minicpm_vla_policy.py \
      --checkpoint \$OUT_DIR/minicpm_vla_action_head.pt \
      --task \$TASK \
      --num-episodes $EVAL_EPISODES \
      --seed 20100 \
      --replan-interval $REPLAN_INTERVAL \
      --smooth-alpha $SMOOTH_ALPHA \
      --out-dir $REMOTE_PROJECT/build/runpod_artifacts/$HEAD_NAME \
      | tee \$OUT_DIR/eval_\${TASK}_minicpm_vla.json
  done
fi
cd $REMOTE_PROJECT/build
tar -czf fireboy-minicpm-vla-artifacts.tgz checkpoints/$HEAD_NAME runpod_artifacts/$HEAD_NAME
"

echo "Downloading MiniCPM-VLA artifacts..."
mkdir -p "$LOCAL_RUNPOD_ARTIFACT_DIR" "$LOCAL_CHECKPOINT_DIR"
"${SCP[@]}" "root@$SSH_IP:$REMOTE_PROJECT/build/fireboy-minicpm-vla-artifacts.tgz" "$LOCAL_RUNPOD_ARTIFACT_DIR/fireboy-minicpm-vla-artifacts.tgz"
tar -xzf "$LOCAL_RUNPOD_ARTIFACT_DIR/fireboy-minicpm-vla-artifacts.tgz" -C "$LOCAL_RUNPOD_ARTIFACT_DIR"
cp "$LOCAL_RUNPOD_ARTIFACT_DIR/checkpoints/$HEAD_NAME/minicpm_vla_action_head.pt" "$LOCAL_CHECKPOINT_DIR/minicpm_vla_action_head.pt"

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
echo "Local checkpoint: $LOCAL_CHECKPOINT_DIR/minicpm_vla_action_head.pt"
echo "RunPod artifact root: $LOCAL_RUNPOD_ARTIFACT_DIR"
