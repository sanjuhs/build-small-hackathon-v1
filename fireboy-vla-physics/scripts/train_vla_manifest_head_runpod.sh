#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
POD_ID="${POD_ID:-}"
GPU_ID="${GPU_ID:-NVIDIA RTX 6000 Ada Generation}"
POD_NAME="${POD_NAME:-fireboy-vla-manifest-head}"
IMAGE="${IMAGE:-runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04}"
MAX_STEPS="${MAX_STEPS:-16000}"
EVAL_EPISODES="${EVAL_EPISODES:-10}"
EVAL_SEED="${EVAL_SEED:-17300}"
REPLAN_INTERVAL="${REPLAN_INTERVAL:-5}"
STATE_MODE="${STATE_MODE:-clock}"
TASK_FILTERS="${TASK_FILTERS:-}"
EVAL_TASKS="${EVAL_TASKS:-pick_up go_eat_berry run_around go_to_point}"
HEAD_NAME="${HEAD_NAME:-fireboy_vla_manifest_action_head}"
REMOTE_ROOT="/workspace"
REMOTE_PROJECT="$REMOTE_ROOT/fireboy-vla-physics"
LOCAL_RUNPOD_ARTIFACT_DIR="$ROOT/Fireboy-training-policy-vla/runpod-artifacts"
LOCAL_CHECKPOINT_DIR="$ROOT/fireboy-vla-physics/build/checkpoints/$HEAD_NAME"
STOP_ON_EXIT=0
CREATED_POD=0
DELETE_CREATED_POD="${DELETE_CREATED_POD:-1}"

if [[ -z "${VLA_ROLLOUT_ARCHIVE:-}" ]]; then
  VLA_ROLLOUT_ARCHIVE="$(find "$ROOT/Fireboy-training-policy-vla/vla-rollouts" -maxdepth 1 -name 'fireboy-vla-rollouts-*.tgz' | sort | tail -n 1)"
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
    --container-disk-in-gb 50 \
    --volume-in-gb 40 \
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
PACK="$ROOT/fireboy-vla-physics/build/runpod/fireboy-vla-manifest-head-source.tgz"
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
"${SCP[@]}" "$PACK" "root@$SSH_IP:$REMOTE_ROOT/fireboy-vla-manifest-head-source.tgz"
"${SCP[@]}" "$VLA_ROLLOUT_ARCHIVE" "root@$SSH_IP:$REMOTE_ROOT/vla-rollouts.tgz"

echo "Training VLA manifest action head on RunPod..."
"${SSH[@]}" "set -euo pipefail
cd $REMOTE_ROOT
rm -rf $REMOTE_PROJECT
tar --no-same-owner -xzf fireboy-vla-manifest-head-source.tgz
mkdir -p $REMOTE_PROJECT/build/imported_vla_rollouts
tar --no-same-owner -xzf vla-rollouts.tgz -C $REMOTE_PROJECT/build/imported_vla_rollouts
MANIFEST=\$(find $REMOTE_PROJECT/build/imported_vla_rollouts -path '*/vla_manifests/*.jsonl' | sort | tail -n 1)
apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq libosmesa6 libosmesa6-dev libgl1 libglfw3 >/dev/null
python -m pip install -q -r $REMOTE_PROJECT/requirements.txt
python - <<'PY'
import torch
print({'torch': torch.__version__, 'cuda_available': torch.cuda.is_available(), 'device': torch.cuda.get_device_name(0) if torch.cuda.is_available() else None})
if not torch.cuda.is_available():
    raise SystemExit('CUDA is not available on this pod.')
PY
export MUJOCO_GL=osmesa
export PYOPENGL_PLATFORM=osmesa
OUT_DIR=$REMOTE_PROJECT/build/checkpoints/$HEAD_NAME
TASK_FILTER_ARGS=()
for TASK in $TASK_FILTERS; do
  TASK_FILTER_ARGS+=(--task-filter \$TASK)
done
python $REMOTE_PROJECT/src/train_vla_manifest_action_head.py \
  --manifest \$MANIFEST \
  --out-dir \$OUT_DIR \
  --max-steps $MAX_STEPS \
  --state-mode $STATE_MODE \
  --include-stage-flags \
  --allow-missing-images \
  \"\${TASK_FILTER_ARGS[@]}\"
mkdir -p $REMOTE_PROJECT/build/runpod_artifacts/$HEAD_NAME
for TASK in $EVAL_TASKS; do
  python $REMOTE_PROJECT/src/eval_articulated_chunk_policy.py \
    --checkpoint \$OUT_DIR/vla_manifest_action_head.pt \
    --task \$TASK \
    --num-episodes $EVAL_EPISODES \
    --seed $EVAL_SEED \
    --smooth-alpha 0.0 \
    --replan-interval $REPLAN_INTERVAL \
    --render \
    --out-dir $REMOTE_PROJECT/build/runpod_artifacts/$HEAD_NAME \
    | tee \$OUT_DIR/eval_\${TASK}_manifest_head.json
done
cd $REMOTE_PROJECT/build
tar -czf fireboy-vla-manifest-head-artifacts.tgz checkpoints/$HEAD_NAME runpod_artifacts/$HEAD_NAME
"

echo "Downloading manifest-head artifacts..."
mkdir -p "$LOCAL_RUNPOD_ARTIFACT_DIR" "$LOCAL_CHECKPOINT_DIR"
"${SCP[@]}" "root@$SSH_IP:$REMOTE_PROJECT/build/fireboy-vla-manifest-head-artifacts.tgz" "$LOCAL_RUNPOD_ARTIFACT_DIR/fireboy-vla-manifest-head-artifacts.tgz"
tar -xzf "$LOCAL_RUNPOD_ARTIFACT_DIR/fireboy-vla-manifest-head-artifacts.tgz" -C "$LOCAL_RUNPOD_ARTIFACT_DIR"
cp "$LOCAL_RUNPOD_ARTIFACT_DIR/checkpoints/$HEAD_NAME/vla_manifest_action_head.pt" "$LOCAL_CHECKPOINT_DIR/vla_manifest_action_head.pt"

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
echo "Local checkpoint: $LOCAL_CHECKPOINT_DIR/vla_manifest_action_head.pt"
echo "RunPod artifact root: $LOCAL_RUNPOD_ARTIFACT_DIR"
