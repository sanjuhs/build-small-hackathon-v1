#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

PID_FILE="${PID_FILE:-.toybox.pid}"

if [[ ! -f "$PID_FILE" ]]; then
  echo "Tiny Toybox is not running: no $PID_FILE found."
  exit 0
fi

pid="$(cat "$PID_FILE")"

if [[ -z "$pid" ]] || ! kill -0 "$pid" >/dev/null 2>&1; then
  rm -f "$PID_FILE"
  echo "Tiny Toybox was not running; removed stale $PID_FILE."
  exit 0
fi

kill "$pid"

for _ in {1..20}; do
  if ! kill -0 "$pid" >/dev/null 2>&1; then
    rm -f "$PID_FILE"
    echo "Tiny Toybox stopped."
    exit 0
  fi
  sleep 0.25
done

kill -9 "$pid" >/dev/null 2>&1 || true
rm -f "$PID_FILE"
echo "Tiny Toybox stopped forcefully."

