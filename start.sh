#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd -P)"
cd "$ROOT_DIR"

PORT="${PORT:-65372}"
PYTHON_VERSION="${PYTHON_VERSION:-3.12}"
PID_FILE="${PID_FILE:-.toybox.pid}"
LOG_FILE="${LOG_FILE:-.toybox.log}"

port_pids() {
  lsof -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null || true
}

process_cwd() {
  local pid="$1"
  lsof -a -p "$pid" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p' | head -n 1
}

is_toybox_pid() {
  local pid="$1"
  local cwd
  local command
  command="$(ps -p "$pid" -o command= 2>/dev/null || true)"
  cwd="$(process_cwd "$pid")"
  [[ "$command" == *"app.py"* && "$cwd" == "$ROOT_DIR" ]]
}

toybox_pids() {
  ps -axww -o pid=,command= | awk '/[a]pp[.]py/ {print $1}' | while read -r pid; do
    if [[ -n "$pid" ]] && is_toybox_pid "$pid"; then
      echo "$pid"
    fi
  done
}

queue_pid() {
  local pid="$1"
  [[ -n "$pid" ]] || return
  if ! printf '%s\n' "$queued_pids" | grep -qx "$pid"; then
    queued_pids="${queued_pids}${pid}"$'\n'
  fi
}

stop_pid() {
  local pid="$1"
  if ! kill -0 "$pid" >/dev/null 2>&1; then
    return
  fi
  if ! is_toybox_pid "$pid"; then
    echo "Refusing to stop pid $pid because it is not Tiny Toybox from this workspace."
    return 1
  fi

  echo "Stopping previous Tiny Toybox process pid $pid."
  kill "$pid" >/dev/null 2>&1 || true
  for _ in {1..30}; do
    if ! kill -0 "$pid" >/dev/null 2>&1; then
      return
    fi
    sleep 0.2
  done

  echo "Pid $pid did not stop cleanly; killing forcefully."
  kill -9 "$pid" >/dev/null 2>&1 || true
}

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required. Install it first: https://docs.astral.sh/uv/"
  exit 1
fi

if [[ -f ".env" ]]; then
  echo "Loading local .env runtime settings."
  set -a
  # shellcheck disable=SC1091
  source ".env"
  set +a
fi

queued_pids=""

if [[ -f "$PID_FILE" ]]; then
  existing_pid="$(cat "$PID_FILE")"
  if [[ -n "$existing_pid" ]] && kill -0 "$existing_pid" >/dev/null 2>&1; then
    if is_toybox_pid "$existing_pid"; then
      queue_pid "$existing_pid"
    else
      echo "Ignoring stale $PID_FILE: pid $existing_pid is not Tiny Toybox from this workspace."
    fi
  fi
  rm -f "$PID_FILE"
fi

for pid in $(toybox_pids); do
  queue_pid "$pid"
done

existing_port_pids="$(port_pids)"
for pid in $existing_port_pids; do
  if is_toybox_pid "$pid"; then
    queue_pid "$pid"
  else
    echo "Port $PORT is already in use by pid $pid:"
    ps -p "$pid" -o command= 2>/dev/null || true
    echo "Refusing to stop a process that is not Tiny Toybox from this workspace."
    echo "Stop that process yourself or choose another port: PORT=65400 ./start.sh"
    exit 1
  fi
done

if [[ -n "$queued_pids" ]]; then
  echo "Restarting Tiny Toybox on port $PORT."
  for pid in $queued_pids; do
    stop_pid "$pid"
  done
else
  echo "Starting Tiny Toybox on port $PORT."
fi

remaining_port_pids="$(port_pids)"
if [[ -n "$remaining_port_pids" ]]; then
  echo "Port $PORT is still in use by pid(s):"
  echo "$remaining_port_pids"
  echo "Tiny Toybox could not restart on this port."
  exit 1
fi

uv sync --python "$PYTHON_VERSION"

pid="$(
  PORT="$PORT" LOG_FILE="$LOG_FILE" ROOT_DIR="$ROOT_DIR" .venv/bin/python - <<'PY'
import os
import subprocess

log_path = os.environ["LOG_FILE"]
root_dir = os.environ["ROOT_DIR"]
env = os.environ.copy()

log = open(log_path, "ab", buffering=0)
process = subprocess.Popen(
    [".venv/bin/python", "app.py"],
    cwd=root_dir,
    env=env,
    stdin=subprocess.DEVNULL,
    stdout=log,
    stderr=subprocess.STDOUT,
    start_new_session=True,
    close_fds=True,
)
print(process.pid)
PY
)"
echo "$pid" > "$PID_FILE"
base_url="http://127.0.0.1:$PORT"

for _ in {1..60}; do
  if ! kill -0 "$pid" >/dev/null 2>&1; then
    rm -f "$PID_FILE"
    echo "Tiny Toybox failed to start. Last log lines:"
    tail -n 80 "$LOG_FILE" || true
    exit 1
  fi

  if curl -fsS "$base_url/" >/dev/null 2>&1; then
    if ! port_pids | grep -qx "$pid"; then
      rm -f "$PID_FILE"
      echo "Tiny Toybox did not bind port $PORT with expected pid $pid."
      echo "Current listener pid(s):"
      port_pids
      exit 1
    fi
    echo "Tiny Toybox started on $base_url"
    echo "pid: $pid"
    echo "logs: $LOG_FILE"
    echo "home: $base_url/"
    echo "pages: $base_url/pages"
    echo "toy room v3: $base_url/toy-v3"
    echo "toy room v2: $base_url/toy-v2"
    echo "toy room: $base_url/toy"
    echo "model lab: $base_url/models"
    echo "blender models: $base_url/blender-models"
    echo "parts lab: $base_url/parts-lab"
    echo "fire boy rigged: $base_url/fireboy-rigged"
    echo "mujoco policy viewer: $base_url/mujoco-policy"
    echo "fire boy policy gallery: $base_url/fireboy-policy-gallery"
    exit 0
  fi

  sleep 0.25
done

echo "Tiny Toybox did not become ready on $base_url. Last log lines:"
tail -n 80 "$LOG_FILE" || true
exit 1
