#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
POD_ID="${POD_ID:-}"
GPU_ID="${GPU_ID:-NVIDIA GeForce RTX 3090}"
POD_NAME="${POD_NAME:-fireboy-vla-berry-train}"
IMAGE="${IMAGE:-runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04}"
NUM_EPISODES="${NUM_EPISODES:-1000}"
RECOVERY_EPISODES="${RECOVERY_EPISODES:-500}"
MAX_STEPS="${MAX_STEPS:-12000}"
SEED="${SEED:-3000}"
EVAL_SEED="${EVAL_SEED:-5000}"
SMOOTH_ALPHA="${SMOOTH_ALPHA:-0.25}"
REMOTE_ROOT="/workspace"
REMOTE_PROJECT="$REMOTE_ROOT/fireboy-vla-physics"
LOCAL_ARTIFACT_DIR="$ROOT/fireboy-vla-physics/checkpoints/berry_eat_wide"
LOCAL_BUILD_ARTIFACT_DIR="$ROOT/fireboy-vla-physics/build/checkpoints/berry_eat_wide"
STOP_ON_EXIT=0

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
    --container-disk-in-gb 40 \
    --volume-in-gb 20 \
    --ports "22/tcp")"
  POD_ID="$(printf '%s' "$create_json" | json_get id)"
  CREATED_POD=1
  STOP_ON_EXIT=1
else
  CREATED_POD=0
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
PACK="$ROOT/fireboy-vla-physics/build/runpod/fireboy-vla-source.tgz"
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

echo "Uploading source..."
"${SCP[@]}" "$PACK" "root@$SSH_IP:$REMOTE_ROOT/fireboy-vla-source.tgz"

echo "Training on RunPod..."
"${SSH[@]}" "set -euo pipefail
cd $REMOTE_ROOT
rm -rf $REMOTE_PROJECT
tar --no-same-owner -xzf fireboy-vla-source.tgz
python -m pip install -q -r $REMOTE_PROJECT/requirements.txt
python - <<'PY'
import torch
print({'torch': torch.__version__, 'cuda_available': torch.cuda.is_available(), 'device': torch.cuda.get_device_name(0) if torch.cuda.is_available() else None})
PY
python $REMOTE_PROJECT/src/smoke_test_berry.py --no-render
python $REMOTE_PROJECT/src/generate_dataset.py --task eat_berry --num-episodes $NUM_EPISODES --out-dir $REMOTE_PROJECT/build/datasets/fireboy_eat_berry --seed $SEED --no-images
python $REMOTE_PROJECT/src/generate_recovery_dataset.py --num-episodes $RECOVERY_EPISODES --out-dir $REMOTE_PROJECT/build/datasets/fireboy_eat_berry_recovery --policy $REMOTE_PROJECT/checkpoints/berry_eat_wide/state_policy.npz --seed 7000
python $REMOTE_PROJECT/src/train_policy.py --dataset-dir $REMOTE_PROJECT/build/datasets/fireboy_eat_berry --extra-dataset-dir $REMOTE_PROJECT/build/datasets/fireboy_eat_berry_recovery --out-dir $REMOTE_PROJECT/build/checkpoints/berry_eat_wide --max-steps $MAX_STEPS
python $REMOTE_PROJECT/src/eval_policy.py --checkpoint $REMOTE_PROJECT/build/checkpoints/berry_eat_wide/state_policy.pt --task eat_berry --num-episodes 100 --seed $EVAL_SEED --smooth-alpha 0.0
python $REMOTE_PROJECT/src/eval_policy.py --checkpoint $REMOTE_PROJECT/build/checkpoints/berry_eat_wide/state_policy.pt --task eat_berry --num-episodes 100 --seed $EVAL_SEED --smooth-alpha $SMOOTH_ALPHA
python $REMOTE_PROJECT/src/export_policy_npz.py --checkpoint $REMOTE_PROJECT/build/checkpoints/berry_eat_wide/state_policy.pt --out $REMOTE_PROJECT/build/checkpoints/berry_eat_wide/state_policy.npz
"

echo "Downloading checkpoint artifacts..."
mkdir -p "$LOCAL_ARTIFACT_DIR" "$LOCAL_BUILD_ARTIFACT_DIR"
"${SCP[@]}" "root@$SSH_IP:$REMOTE_PROJECT/build/checkpoints/berry_eat_wide/state_policy.pt" "$LOCAL_BUILD_ARTIFACT_DIR/state_policy.pt"
"${SCP[@]}" "root@$SSH_IP:$REMOTE_PROJECT/build/checkpoints/berry_eat_wide/state_policy.npz" "$LOCAL_BUILD_ARTIFACT_DIR/state_policy.npz"
cp "$LOCAL_BUILD_ARTIFACT_DIR/state_policy.npz" "$LOCAL_ARTIFACT_DIR/state_policy.npz"

echo "Stopping pod $POD_ID..."
runpodctl pod stop "$POD_ID" >/dev/null || true
STOP_ON_EXIT=0
trap - EXIT

echo "Done."
echo "Pod: $POD_ID"
echo "Local Torch checkpoint: $LOCAL_BUILD_ARTIFACT_DIR/state_policy.pt"
echo "Local NumPy checkpoint: $LOCAL_ARTIFACT_DIR/state_policy.npz"
echo "Run local demo: bash fireboy-vla-physics/scripts/run_local_demo.sh"
