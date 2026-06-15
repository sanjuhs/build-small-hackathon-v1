#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
POD_ID="${POD_ID:-}"
GPU_ID="${GPU_ID:-NVIDIA RTX 6000 Ada Generation}"
POD_NAME="${POD_NAME:-fireboy-faithful-articulated-train}"
IMAGE="${IMAGE:-runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04}"
NUM_EPISODES="${NUM_EPISODES:-600}"
MAX_STEPS="${MAX_STEPS:-18000}"
SKILL_MAX_STEPS="${SKILL_MAX_STEPS:-22000}"
CHUNK_MAX_STEPS="${CHUNK_MAX_STEPS:-26000}"
CHUNK_STEPS="${CHUNK_STEPS:-16}"
CHUNK_REPLAN_INTERVAL="${CHUNK_REPLAN_INTERVAL:-8}"
CHUNK_STATE_MODE="${CHUNK_STATE_MODE:-clock}"
EVAL_EPISODES="${EVAL_EPISODES:-20}"
SEED="${SEED:-8100}"
EVAL_SEED="${EVAL_SEED:-9100}"
SMOOTH_ALPHA="${SMOOTH_ALPHA:-0.0}"
TRAIN_MIXED_POLICY="${TRAIN_MIXED_POLICY:-0}"
TRAIN_SKILL_POLICIES="${TRAIN_SKILL_POLICIES:-1}"
TRAIN_CHUNK_POLICIES="${TRAIN_CHUNK_POLICIES:-1}"
REMOTE_ROOT="/workspace"
REMOTE_PROJECT="$REMOTE_ROOT/fireboy-vla-physics"
LOCAL_ARTIFACT_DIR="$ROOT/fireboy-vla-physics/checkpoints/fireboy_articulated_all"
LOCAL_BUILD_ARTIFACT_DIR="$ROOT/fireboy-vla-physics/build/checkpoints/fireboy_articulated_all"
LOCAL_RUNPOD_ARTIFACT_DIR="$ROOT/Fireboy-training-policy-vla/runpod-artifacts"
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
    --container-disk-in-gb 50 \
    --volume-in-gb 30 \
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

echo "Packing faithful articulated source..."
PACK="$ROOT/fireboy-vla-physics/build/runpod/fireboy-faithful-articulated-source.tgz"
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
"${SCP[@]}" "$PACK" "root@$SSH_IP:$REMOTE_ROOT/fireboy-faithful-articulated-source.tgz"

echo "Training faithful Fireboy articulated policy on RunPod..."
"${SSH[@]}" "set -euo pipefail
cd $REMOTE_ROOT
rm -rf $REMOTE_PROJECT
tar --no-same-owner -xzf fireboy-faithful-articulated-source.tgz
apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq libosmesa6 libosmesa6-dev libgl1 libglfw3 >/dev/null
python -m pip install -q -r $REMOTE_PROJECT/requirements.txt
python - <<'PY'
import torch
print({'torch': torch.__version__, 'cuda_available': torch.cuda.is_available(), 'device': torch.cuda.get_device_name(0) if torch.cuda.is_available() else None})
if not torch.cuda.is_available():
    raise SystemExit('CUDA is not available on this pod; refusing to spend time training on CPU.')
PY
export MUJOCO_GL=osmesa
export PYOPENGL_PLATFORM=osmesa
python $REMOTE_PROJECT/src/fireboy_articulated_mjcf.py
mkdir -p $REMOTE_PROJECT/build/runpod_artifacts/render_gate
python $REMOTE_PROJECT/src/render_articulated_fireboy.py --mode body --out-dir $REMOTE_PROJECT/build/runpod_artifacts/render_gate
python $REMOTE_PROJECT/src/generate_articulated_dataset.py --task all --num-episodes 1 --out-dir $REMOTE_PROJECT/build/datasets/fireboy_articulated_gate --seed 42 --no-images
python $REMOTE_PROJECT/src/generate_articulated_dataset.py --task all --num-episodes $NUM_EPISODES --out-dir $REMOTE_PROJECT/build/datasets/fireboy_articulated_all --seed $SEED --no-images
if [[ '$TRAIN_MIXED_POLICY' == '1' ]]; then
  python $REMOTE_PROJECT/src/train_articulated_policy.py --dataset-dir $REMOTE_PROJECT/build/datasets/fireboy_articulated_all --out-dir $REMOTE_PROJECT/build/checkpoints/fireboy_articulated_all --max-steps $MAX_STEPS --include-stage-flags
  python $REMOTE_PROJECT/src/eval_articulated_policy.py --checkpoint $REMOTE_PROJECT/build/checkpoints/fireboy_articulated_all/faithful_articulated_policy.pt --task pick_up --num-episodes $EVAL_EPISODES --seed $EVAL_SEED --smooth-alpha $SMOOTH_ALPHA | tee $REMOTE_PROJECT/build/checkpoints/fireboy_articulated_all/eval_pick_up.json
  python $REMOTE_PROJECT/src/eval_articulated_policy.py --checkpoint $REMOTE_PROJECT/build/checkpoints/fireboy_articulated_all/faithful_articulated_policy.pt --task go_eat_berry --num-episodes $EVAL_EPISODES --seed $EVAL_SEED --smooth-alpha $SMOOTH_ALPHA | tee $REMOTE_PROJECT/build/checkpoints/fireboy_articulated_all/eval_go_eat_berry.json
  python $REMOTE_PROJECT/src/eval_articulated_policy.py --checkpoint $REMOTE_PROJECT/build/checkpoints/fireboy_articulated_all/faithful_articulated_policy.pt --task run_around --num-episodes $EVAL_EPISODES --seed $EVAL_SEED --smooth-alpha $SMOOTH_ALPHA | tee $REMOTE_PROJECT/build/checkpoints/fireboy_articulated_all/eval_run_around.json
  python $REMOTE_PROJECT/src/export_policy_npz.py --checkpoint $REMOTE_PROJECT/build/checkpoints/fireboy_articulated_all/faithful_articulated_policy.pt --out $REMOTE_PROJECT/build/checkpoints/fireboy_articulated_all/faithful_articulated_policy.npz
fi
if [[ '$TRAIN_SKILL_POLICIES' == '1' ]]; then
  for TASK in pick_up go_eat_berry run_around go_to_point; do
    OUT_DIR=$REMOTE_PROJECT/build/checkpoints/fireboy_articulated_\$TASK
    python $REMOTE_PROJECT/src/train_articulated_policy.py --dataset-dir $REMOTE_PROJECT/build/datasets/fireboy_articulated_all --out-dir \$OUT_DIR --max-steps $SKILL_MAX_STEPS --task-filter \$TASK --include-stage-flags
    python $REMOTE_PROJECT/src/eval_articulated_policy.py --checkpoint \$OUT_DIR/faithful_articulated_policy.pt --task \$TASK --num-episodes $EVAL_EPISODES --seed $EVAL_SEED --smooth-alpha $SMOOTH_ALPHA | tee \$OUT_DIR/eval_\$TASK.json
    python $REMOTE_PROJECT/src/export_policy_npz.py --checkpoint \$OUT_DIR/faithful_articulated_policy.pt --out \$OUT_DIR/faithful_articulated_policy.npz
  done
fi
if [[ '$TRAIN_CHUNK_POLICIES' == '1' ]]; then
  mkdir -p $REMOTE_PROJECT/build/runpod_artifacts/learned_chunk
  for TASK in pick_up go_eat_berry; do
    OUT_DIR=$REMOTE_PROJECT/build/checkpoints/fireboy_articulated_\${TASK}_chunk
    python $REMOTE_PROJECT/src/train_articulated_chunk_policy.py \
      --dataset-dir $REMOTE_PROJECT/build/datasets/fireboy_articulated_all \
      --out-dir \$OUT_DIR \
      --max-steps $CHUNK_MAX_STEPS \
      --task-filter \$TASK \
      --include-stage-flags \
      --state-mode $CHUNK_STATE_MODE \
      --chunk-steps $CHUNK_STEPS
    python $REMOTE_PROJECT/src/eval_articulated_chunk_policy.py \
      --checkpoint \$OUT_DIR/faithful_articulated_chunk_policy.pt \
      --task \$TASK \
      --num-episodes $EVAL_EPISODES \
      --seed $EVAL_SEED \
      --smooth-alpha $SMOOTH_ALPHA \
      --replan-interval $CHUNK_REPLAN_INTERVAL \
      --render \
      --out-dir $REMOTE_PROJECT/build/runpod_artifacts/learned_chunk \
      | tee \$OUT_DIR/eval_\${TASK}_chunk.json
  done
fi
mkdir -p $REMOTE_PROJECT/build/runpod_artifacts/controller $REMOTE_PROJECT/build/runpod_artifacts/learned
python $REMOTE_PROJECT/src/render_articulated_fireboy.py --mode all --out-dir $REMOTE_PROJECT/build/runpod_artifacts/controller
if [[ '$TRAIN_SKILL_POLICIES' == '1' ]]; then
  for TASK in pick_up go_eat_berry run_around go_to_point; do
    python $REMOTE_PROJECT/src/rollout_articulated_numpy_policy.py \
      --task \$TASK \
      --policy $REMOTE_PROJECT/build/checkpoints/fireboy_articulated_\$TASK/faithful_articulated_policy.npz \
      --out-dir $REMOTE_PROJECT/build/runpod_artifacts/learned \
      --seed $EVAL_SEED
  done
fi
cd $REMOTE_PROJECT/build
tar -czf fireboy-runpod-artifacts.tgz checkpoints runpod_artifacts
"

echo "Downloading faithful checkpoint artifacts..."
mkdir -p "$LOCAL_ARTIFACT_DIR" "$LOCAL_BUILD_ARTIFACT_DIR" "$LOCAL_RUNPOD_ARTIFACT_DIR"
if [[ "$TRAIN_MIXED_POLICY" == "1" ]]; then
  "${SCP[@]}" "root@$SSH_IP:$REMOTE_PROJECT/build/checkpoints/fireboy_articulated_all/faithful_articulated_policy.pt" "$LOCAL_BUILD_ARTIFACT_DIR/faithful_articulated_policy.pt"
  "${SCP[@]}" "root@$SSH_IP:$REMOTE_PROJECT/build/checkpoints/fireboy_articulated_all/faithful_articulated_policy.npz" "$LOCAL_BUILD_ARTIFACT_DIR/faithful_articulated_policy.npz"
  "${SCP[@]}" "root@$SSH_IP:$REMOTE_PROJECT/build/checkpoints/fireboy_articulated_all/eval_pick_up.json" "$LOCAL_BUILD_ARTIFACT_DIR/eval_pick_up.json"
  "${SCP[@]}" "root@$SSH_IP:$REMOTE_PROJECT/build/checkpoints/fireboy_articulated_all/eval_go_eat_berry.json" "$LOCAL_BUILD_ARTIFACT_DIR/eval_go_eat_berry.json"
  "${SCP[@]}" "root@$SSH_IP:$REMOTE_PROJECT/build/checkpoints/fireboy_articulated_all/eval_run_around.json" "$LOCAL_BUILD_ARTIFACT_DIR/eval_run_around.json"
  cp "$LOCAL_BUILD_ARTIFACT_DIR/faithful_articulated_policy.npz" "$LOCAL_ARTIFACT_DIR/faithful_articulated_policy.npz"
fi
if [[ "$TRAIN_SKILL_POLICIES" == "1" ]]; then
  for TASK in pick_up go_eat_berry run_around go_to_point; do
    LOCAL_SKILL_BUILD="$ROOT/fireboy-vla-physics/build/checkpoints/fireboy_articulated_$TASK"
    LOCAL_SKILL_ARTIFACT="$ROOT/fireboy-vla-physics/checkpoints/fireboy_articulated_$TASK"
    mkdir -p "$LOCAL_SKILL_BUILD" "$LOCAL_SKILL_ARTIFACT"
    "${SCP[@]}" "root@$SSH_IP:$REMOTE_PROJECT/build/checkpoints/fireboy_articulated_$TASK/faithful_articulated_policy.pt" "$LOCAL_SKILL_BUILD/faithful_articulated_policy.pt"
    "${SCP[@]}" "root@$SSH_IP:$REMOTE_PROJECT/build/checkpoints/fireboy_articulated_$TASK/faithful_articulated_policy.npz" "$LOCAL_SKILL_BUILD/faithful_articulated_policy.npz"
    "${SCP[@]}" "root@$SSH_IP:$REMOTE_PROJECT/build/checkpoints/fireboy_articulated_$TASK/eval_$TASK.json" "$LOCAL_SKILL_BUILD/eval_$TASK.json"
    cp "$LOCAL_SKILL_BUILD/faithful_articulated_policy.npz" "$LOCAL_SKILL_ARTIFACT/faithful_articulated_policy.npz"
  done
fi
if [[ "$TRAIN_CHUNK_POLICIES" == "1" ]]; then
  for TASK in pick_up go_eat_berry; do
    LOCAL_CHUNK_BUILD="$ROOT/fireboy-vla-physics/build/checkpoints/fireboy_articulated_${TASK}_chunk"
    LOCAL_CHUNK_ARTIFACT="$ROOT/fireboy-vla-physics/checkpoints/fireboy_articulated_${TASK}_chunk"
    mkdir -p "$LOCAL_CHUNK_BUILD" "$LOCAL_CHUNK_ARTIFACT"
    "${SCP[@]}" "root@$SSH_IP:$REMOTE_PROJECT/build/checkpoints/fireboy_articulated_${TASK}_chunk/faithful_articulated_chunk_policy.pt" "$LOCAL_CHUNK_BUILD/faithful_articulated_chunk_policy.pt"
    "${SCP[@]}" "root@$SSH_IP:$REMOTE_PROJECT/build/checkpoints/fireboy_articulated_${TASK}_chunk/eval_${TASK}_chunk.json" "$LOCAL_CHUNK_BUILD/eval_${TASK}_chunk.json"
    cp "$LOCAL_CHUNK_BUILD/faithful_articulated_chunk_policy.pt" "$LOCAL_CHUNK_ARTIFACT/faithful_articulated_chunk_policy.pt"
  done
fi
"${SCP[@]}" "root@$SSH_IP:$REMOTE_PROJECT/build/fireboy-runpod-artifacts.tgz" "$LOCAL_RUNPOD_ARTIFACT_DIR/fireboy-runpod-artifacts.tgz"
tar -xzf "$LOCAL_RUNPOD_ARTIFACT_DIR/fireboy-runpod-artifacts.tgz" -C "$LOCAL_RUNPOD_ARTIFACT_DIR"

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
echo "Local checkpoint root: $ROOT/fireboy-vla-physics/build/checkpoints"
echo "RunPod artifact root: $LOCAL_RUNPOD_ARTIFACT_DIR"
echo "Viewer: http://127.0.0.1:65372/mujoco-policy"
