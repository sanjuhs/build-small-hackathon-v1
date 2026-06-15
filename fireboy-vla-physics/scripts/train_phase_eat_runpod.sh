#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
POD_ID="${POD_ID:-}"
GPU_ID="${GPU_ID:-NVIDIA RTX A6000}"
POD_NAME="${POD_NAME:-fireboy-phase-eat-train}"
IMAGE="${IMAGE:-runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04}"
NUM_EPISODES="${NUM_EPISODES:-800}"
MAX_STEPS="${MAX_STEPS:-30000}"
EVAL_EPISODES="${EVAL_EPISODES:-30}"
SEED="${SEED:-10100}"
EVAL_SEED="${EVAL_SEED:-11100}"
SMOOTH_ALPHA="${SMOOTH_ALPHA:-0.20}"
REMOTE_ROOT="/workspace"
REMOTE_PROJECT="$REMOTE_ROOT/fireboy-vla-physics"
REMOTE_DATASET="$REMOTE_PROJECT/build/datasets/fireboy_articulated_go_eat_berry_phase_clock"
REMOTE_CHECKPOINT="$REMOTE_PROJECT/build/checkpoints/fireboy_articulated_go_eat_berry_phase_clock"
LOCAL_BUILD_ARTIFACT_DIR="$ROOT/fireboy-vla-physics/build/checkpoints/fireboy_articulated_go_eat_berry_phase_clock"
LOCAL_ARTIFACT_DIR="$ROOT/fireboy-vla-physics/checkpoints/fireboy_articulated_go_eat_berry_phase_clock"
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
    --container-disk-in-gb 50 \
    --volume-in-gb 30 \
    --ports "22/tcp")"
  POD_ID="$(printf '%s' "$create_json" | json_get id)"
  STOP_ON_EXIT=1
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

echo "Packing phase-conditioned source..."
PACK="$ROOT/fireboy-vla-physics/build/runpod/fireboy-phase-eat-source.tgz"
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
"${SCP[@]}" "$PACK" "root@$SSH_IP:$REMOTE_ROOT/fireboy-phase-eat-source.tgz"

echo "Training phase-conditioned eat policy on RunPod..."
"${SSH[@]}" "set -euo pipefail
cd $REMOTE_ROOT
rm -rf $REMOTE_PROJECT
tar --no-same-owner -xzf fireboy-phase-eat-source.tgz
python -m pip install -q -r $REMOTE_PROJECT/requirements.txt
python - <<'PY'
import torch
print({'torch': torch.__version__, 'cuda_available': torch.cuda.is_available(), 'device': torch.cuda.get_device_name(0) if torch.cuda.is_available() else None})
if not torch.cuda.is_available():
    raise SystemExit('CUDA is not available on this pod; refusing to train on CPU.')
PY
python $REMOTE_PROJECT/src/fireboy_articulated_mjcf.py
python $REMOTE_PROJECT/src/generate_articulated_dataset.py --task go_eat_berry --num-episodes $NUM_EPISODES --out-dir $REMOTE_DATASET --seed $SEED --no-images
python $REMOTE_PROJECT/src/train_articulated_policy.py --dataset-dir $REMOTE_DATASET --out-dir $REMOTE_CHECKPOINT --max-steps $MAX_STEPS --task-filter go_eat_berry --include-stage-flags --state-mode clock
python $REMOTE_PROJECT/src/eval_articulated_policy.py --checkpoint $REMOTE_CHECKPOINT/faithful_articulated_policy.pt --task go_eat_berry --num-episodes $EVAL_EPISODES --seed $EVAL_SEED --smooth-alpha $SMOOTH_ALPHA | tee $REMOTE_CHECKPOINT/eval_go_eat_berry_phase_clock.json
python $REMOTE_PROJECT/src/export_policy_npz.py --checkpoint $REMOTE_CHECKPOINT/faithful_articulated_policy.pt --out $REMOTE_CHECKPOINT/faithful_articulated_policy.npz
"

echo "Downloading phase eat artifacts..."
mkdir -p "$LOCAL_BUILD_ARTIFACT_DIR" "$LOCAL_ARTIFACT_DIR"
"${SCP[@]}" "root@$SSH_IP:$REMOTE_CHECKPOINT/faithful_articulated_policy.pt" "$LOCAL_BUILD_ARTIFACT_DIR/faithful_articulated_policy.pt"
"${SCP[@]}" "root@$SSH_IP:$REMOTE_CHECKPOINT/faithful_articulated_policy.npz" "$LOCAL_BUILD_ARTIFACT_DIR/faithful_articulated_policy.npz"
"${SCP[@]}" "root@$SSH_IP:$REMOTE_CHECKPOINT/eval_go_eat_berry_phase_clock.json" "$LOCAL_BUILD_ARTIFACT_DIR/eval_go_eat_berry_phase_clock.json"
cp "$LOCAL_BUILD_ARTIFACT_DIR/faithful_articulated_policy.npz" "$LOCAL_ARTIFACT_DIR/faithful_articulated_policy.npz"

echo "Stopping pod $POD_ID..."
runpodctl pod stop "$POD_ID" >/dev/null || true
STOP_ON_EXIT=0
trap - EXIT

echo "Done."
echo "Pod: $POD_ID"
echo "Local Torch checkpoint: $LOCAL_BUILD_ARTIFACT_DIR/faithful_articulated_policy.pt"
echo "Local NumPy checkpoint: $LOCAL_ARTIFACT_DIR/faithful_articulated_policy.npz"
