#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
POD_ID="${POD_ID:-}"
GPU_ID="${GPU_ID:-NVIDIA RTX 6000 Ada Generation}"
POD_NAME="${POD_NAME:-fireboy-vla-rollout-builder}"
IMAGE="${IMAGE:-runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04}"
VLA_NUM_EPISODES="${VLA_NUM_EPISODES:-32}"
VLA_TASKS="${VLA_TASKS:-all}"
VLA_CHUNK_STEPS="${VLA_CHUNK_STEPS:-10}"
IMAGE_STRIDE="${IMAGE_STRIDE:-4}"
MANIFEST_STRIDE="${MANIFEST_STRIDE:-4}"
SEED="${SEED:-15100}"
GO_TO_POINT_RECOVERY="${GO_TO_POINT_RECOVERY:-0}"
RUN_ID="${RUN_ID:-$(date +%Y%m%d-%H%M%S)}"
REMOTE_ROOT="/workspace"
REMOTE_PROJECT="$REMOTE_ROOT/fireboy-vla-physics"
REMOTE_DATASET="$REMOTE_PROJECT/build/datasets/fireboy_vla_images_$RUN_ID"
REMOTE_MANIFEST="$REMOTE_PROJECT/build/vla_manifests/fireboy_vla_action_chunks_$RUN_ID.jsonl"
REMOTE_SUMMARY="$REMOTE_PROJECT/build/vla_manifests/fireboy_vla_action_chunks_$RUN_ID.summary.json"
LOCAL_VLA_DIR="$ROOT/Fireboy-training-policy-vla/vla-rollouts"
STOP_ON_EXIT=0
CREATED_POD=0
DELETE_CREATED_POD="${DELETE_CREATED_POD:-1}"

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
    --container-disk-in-gb 60 \
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
PACK="$ROOT/fireboy-vla-physics/build/runpod/fireboy-vla-rollout-source.tgz"
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
"${SCP[@]}" "$PACK" "root@$SSH_IP:$REMOTE_ROOT/fireboy-vla-rollout-source.tgz"

echo "Generating VLA image/action rollouts on RunPod..."
RECOVERY_ARGS=""
if [[ "$GO_TO_POINT_RECOVERY" == "1" ]]; then
  RECOVERY_ARGS="--go-to-point-recovery"
fi
"${SSH[@]}" "set -euo pipefail
cd $REMOTE_ROOT
rm -rf $REMOTE_PROJECT
tar --no-same-owner -xzf fireboy-vla-rollout-source.tgz
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
python $REMOTE_PROJECT/src/generate_articulated_dataset.py \
  --task '$VLA_TASKS' \
  --num-episodes $VLA_NUM_EPISODES \
  --out-dir $REMOTE_DATASET \
  --seed $SEED \
  --save-images \
  --image-stride $IMAGE_STRIDE \
  $RECOVERY_ARGS
python $REMOTE_PROJECT/src/build_vla_action_manifest.py \
  --dataset-dir $REMOTE_DATASET \
  --out $REMOTE_MANIFEST \
  --chunk-steps $VLA_CHUNK_STEPS \
  --stride $MANIFEST_STRIDE
python - <<'PY'
import json
from pathlib import Path
dataset = Path('$REMOTE_DATASET')
manifest = Path('$REMOTE_MANIFEST')
rows = sum(1 for _ in manifest.open('r', encoding='utf-8'))
images = sum(1 for _ in (dataset / 'images').glob('*/*.jpg'))
episodes = sum(1 for _ in (dataset / 'episodes').glob('*.jsonl'))
summary = {
    'run_id': '$RUN_ID',
    'dataset': str(dataset),
    'manifest': str(manifest),
    'episodes': episodes,
    'images': images,
    'manifest_rows': rows,
    'num_episodes_per_task': int('$VLA_NUM_EPISODES'),
    'tasks': '$VLA_TASKS',
    'image_stride': int('$IMAGE_STRIDE'),
    'manifest_stride': int('$MANIFEST_STRIDE'),
    'chunk_steps': int('$VLA_CHUNK_STEPS'),
    'go_to_point_recovery': bool(int('$GO_TO_POINT_RECOVERY')),
}
Path('$REMOTE_SUMMARY').write_text(json.dumps(summary, indent=2), encoding='utf-8')
print(json.dumps(summary, indent=2))
PY
cd $REMOTE_PROJECT/build
tar -czf fireboy-vla-rollouts-$RUN_ID.tgz datasets/fireboy_vla_images_$RUN_ID vla_manifests/fireboy_vla_action_chunks_$RUN_ID.jsonl vla_manifests/fireboy_vla_action_chunks_$RUN_ID.summary.json
"

echo "Downloading VLA rollout artifacts..."
mkdir -p "$LOCAL_VLA_DIR"
"${SCP[@]}" "root@$SSH_IP:$REMOTE_PROJECT/build/fireboy-vla-rollouts-$RUN_ID.tgz" "$LOCAL_VLA_DIR/fireboy-vla-rollouts-$RUN_ID.tgz"
tar -xzf "$LOCAL_VLA_DIR/fireboy-vla-rollouts-$RUN_ID.tgz" -C "$LOCAL_VLA_DIR"
LOCAL_DATASET="$LOCAL_VLA_DIR/datasets/fireboy_vla_images_$RUN_ID"
LOCAL_MANIFEST="$LOCAL_VLA_DIR/vla_manifests/fireboy_vla_action_chunks_$RUN_ID.jsonl"
LOCAL_SUMMARY="$LOCAL_VLA_DIR/vla_manifests/fireboy_vla_action_chunks_$RUN_ID.summary.json"
perl -0pi -e "s|$REMOTE_DATASET|$LOCAL_DATASET|g; s|$REMOTE_MANIFEST|$LOCAL_MANIFEST|g" "$LOCAL_MANIFEST" "$LOCAL_SUMMARY"

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
echo "Run ID: $RUN_ID"
echo "Local rollout root: $LOCAL_VLA_DIR"
