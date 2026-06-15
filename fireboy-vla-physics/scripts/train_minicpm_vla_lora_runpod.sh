#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
POD_ID="${POD_ID:-}"
GPU_ID="${GPU_ID:-NVIDIA RTX 6000 Ada Generation}"
POD_NAME="${POD_NAME:-fireboy-minicpm-vla-lora}"
IMAGE="${IMAGE:-runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04}"
MINICPM_MODEL_ID="${MINICPM_MODEL_ID:-openbmb/MiniCPM-V-4.6}"
LIMIT_ROWS="${LIMIT_ROWS:-512}"
MAX_STEPS="${MAX_STEPS:-500}"
TASK_FILTERS="${TASK_FILTERS:-pick_up go_eat_berry}"
EVAL_TASKS="${EVAL_TASKS:-pick_up go_eat_berry}"
EVAL_EPISODES="${EVAL_EPISODES:-1}"
REPLAN_INTERVAL="${REPLAN_INTERVAL:-8}"
DOWNSAMPLE_MODE="${DOWNSAMPLE_MODE:-16x}"
MAX_SLICE_NUMS="${MAX_SLICE_NUMS:-4}"
LORA_RANK="${LORA_RANK:-8}"
LORA_ALPHA="${LORA_ALPHA:-16}"
LORA_DROPOUT="${LORA_DROPOUT:-0.05}"
LR_LORA="${LR_LORA:-1e-5}"
LR_HEAD="${LR_HEAD:-5e-5}"
RUN_EVAL="${RUN_EVAL:-1}"
REMOTE_ROOT="/workspace"
REMOTE_PROJECT="$REMOTE_ROOT/fireboy-vla-physics"
HEAD_NAME="${HEAD_NAME:-fireboy_minicpm_vla_lora_residual_512}"
LOCAL_RUNPOD_ARTIFACT_DIR="$ROOT/Fireboy-training-policy-vla/runpod-artifacts"
LOCAL_CHECKPOINT_DIR="$ROOT/fireboy-vla-physics/build/checkpoints/$HEAD_NAME"
STOP_ON_EXIT=0
CREATED_POD=0
DELETE_CREATED_POD="${DELETE_CREATED_POD:-1}"
SEED_CHECKPOINT="${SEED_CHECKPOINT:-$ROOT/fireboy-vla-physics/build/checkpoints/fireboy_minicpm_vla_action_head_residual_2048/minicpm_vla_action_head.pt}"

if [[ -z "${VLA_ROLLOUT_ARCHIVE:-}" ]]; then
  VLA_ROLLOUT_ARCHIVE="$ROOT/Fireboy-training-policy-vla/vla-rollouts/minicpm_slices/manip_2048_uniform/fireboy-vla-manip-2048-uniform-320px.tgz"
fi
if [[ ! -f "$VLA_ROLLOUT_ARCHIVE" ]]; then
  echo "Missing VLA rollout archive: $VLA_ROLLOUT_ARCHIVE" >&2
  exit 1
fi
if [[ ! -f "$SEED_CHECKPOINT" ]]; then
  echo "Missing seed checkpoint: $SEED_CHECKPOINT" >&2
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
    --container-disk-in-gb 85 \
    --volume-in-gb 70 \
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

echo "Packing source..."
PACK="$ROOT/fireboy-vla-physics/build/runpod/fireboy-minicpm-vla-lora-source.tgz"
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

echo "Uploading source, VLA rollout archive, and seed checkpoint..."
"${SCP[@]}" "$PACK" "root@$SSH_IP:$REMOTE_ROOT/fireboy-minicpm-vla-lora-source.tgz"
"${SCP[@]}" "$VLA_ROLLOUT_ARCHIVE" "root@$SSH_IP:$REMOTE_ROOT/vla-rollouts.tgz"
"${SCP[@]}" "$SEED_CHECKPOINT" "root@$SSH_IP:$REMOTE_ROOT/seed_minicpm_vla_action_head.pt"

echo "Training MiniCPM-V LoRA action head on RunPod..."
"${SSH[@]}" "set -euo pipefail
cd $REMOTE_ROOT
rm -rf $REMOTE_PROJECT
tar --no-same-owner -xzf fireboy-minicpm-vla-lora-source.tgz
mkdir -p $REMOTE_PROJECT/build/imported_vla_rollouts
tar --no-same-owner -xzf vla-rollouts.tgz -C $REMOTE_PROJECT/build/imported_vla_rollouts
MANIFEST=\$(find $REMOTE_PROJECT/build/imported_vla_rollouts -path '*/vla_manifests/*.jsonl' | sort | tail -n 1)
DATASET=\$(find $REMOTE_PROJECT/build/imported_vla_rollouts/datasets -mindepth 1 -maxdepth 1 -type d | sort | tail -n 1)
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
OUT_DIR=$REMOTE_PROJECT/build/checkpoints/$HEAD_NAME
mkdir -p \$OUT_DIR
TASK_ARGS=''
for TASK in $TASK_FILTERS; do
  TASK_ARGS=\"\$TASK_ARGS --task-filter \$TASK\"
done
python $REMOTE_PROJECT/src/train_minicpm_vla_lora_action_head.py \
  --manifest \$MANIFEST \
  --seed-checkpoint $REMOTE_ROOT/seed_minicpm_vla_action_head.pt \
  --out-dir \$OUT_DIR \
  --model-id $MINICPM_MODEL_ID \
  --limit-rows $LIMIT_ROWS \
  --max-steps $MAX_STEPS \
  --lora-rank $LORA_RANK \
  --lora-alpha $LORA_ALPHA \
  --lora-dropout $LORA_DROPOUT \
  --lr-lora $LR_LORA \
  --lr-head $LR_HEAD \
  --freeze-state-head \
  --downsample-mode $DOWNSAMPLE_MODE \
  --max-slice-nums $MAX_SLICE_NUMS \
  \$TASK_ARGS \
  | tee \$OUT_DIR/train_minicpm_vla_lora_action_head.json
mkdir -p $REMOTE_PROJECT/build/runpod_artifacts/$HEAD_NAME
if [[ '$RUN_EVAL' == '1' ]]; then
  for TASK in $EVAL_TASKS; do
    python $REMOTE_PROJECT/src/eval_minicpm_vla_policy.py \
      --checkpoint \$OUT_DIR/minicpm_vla_lora_action_head.pt \
      --task \$TASK \
      --num-episodes $EVAL_EPISODES \
      --seed 23100 \
      --replan-interval $REPLAN_INTERVAL \
      --out-dir $REMOTE_PROJECT/build/runpod_artifacts/$HEAD_NAME \
      | tee \$OUT_DIR/eval_\${TASK}_minicpm_vla_lora.json
  done
fi
cd $REMOTE_PROJECT/build
tar -czf fireboy-minicpm-vla-lora-artifacts.tgz checkpoints/$HEAD_NAME runpod_artifacts/$HEAD_NAME
"

echo "Downloading MiniCPM-VLA LoRA artifacts..."
mkdir -p "$LOCAL_RUNPOD_ARTIFACT_DIR" "$LOCAL_CHECKPOINT_DIR"
"${SCP[@]}" "root@$SSH_IP:$REMOTE_PROJECT/build/fireboy-minicpm-vla-lora-artifacts.tgz" "$LOCAL_RUNPOD_ARTIFACT_DIR/fireboy-minicpm-vla-lora-artifacts.tgz"
tar -xzf "$LOCAL_RUNPOD_ARTIFACT_DIR/fireboy-minicpm-vla-lora-artifacts.tgz" -C "$LOCAL_RUNPOD_ARTIFACT_DIR"
cp "$LOCAL_RUNPOD_ARTIFACT_DIR/checkpoints/$HEAD_NAME/minicpm_vla_lora_action_head.pt" "$LOCAL_CHECKPOINT_DIR/minicpm_vla_lora_action_head.pt"
cp -R "$LOCAL_RUNPOD_ARTIFACT_DIR/checkpoints/$HEAD_NAME/lora_adapter" "$LOCAL_CHECKPOINT_DIR/lora_adapter"

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
echo "Local checkpoint: $LOCAL_CHECKPOINT_DIR/minicpm_vla_lora_action_head.pt"
echo "RunPod artifact root: $LOCAL_RUNPOD_ARTIFACT_DIR"
