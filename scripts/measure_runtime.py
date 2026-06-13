from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import time
from statistics import mean, median
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen


def main() -> None:
    args = parse_args()
    base_url = args.base_url.rstrip("/")
    port = infer_port(base_url, args.port)

    result: dict[str, Any] = {
        "baseUrl": base_url,
        "port": port,
        "modelStatus": get_json(f"{base_url}/api/model-status", timeout=args.timeout),
        "latencyMs": benchmark_pet_action(base_url, args.samples, args.timeout),
        "processes": process_snapshot(port),
        "ollamaPs": command_text(["ollama", "ps"]) if shutil.which("ollama") else {"available": False},
    }

    if args.power:
        result["power"] = powermetrics_snapshot()
    else:
        result["power"] = {
            "measured": False,
            "reason": "pass --power to try sudo -n powermetrics on macOS",
        }

    print(json.dumps(result, indent=2, sort_keys=True))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Measure Tiny Toybox runtime memory and latency.")
    parser.add_argument("--base-url", default="http://127.0.0.1:65372")
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--power", action="store_true", help="Try sudo -n powermetrics once.")
    return parser.parse_args()


def infer_port(base_url: str, override: int | None) -> int:
    if override:
        return override
    tail = base_url.rsplit(":", 1)[-1]
    try:
        return int(tail.split("/", 1)[0])
    except ValueError:
        return 65372


def get_json(url: str, timeout: float) -> dict[str, Any]:
    try:
        with urlopen(url, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, json.JSONDecodeError) as exc:
        return {"error": str(exc)}


def post_json(url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def benchmark_pet_action(base_url: str, samples: int, timeout: float) -> dict[str, Any]:
    timings: list[float] = []
    errors: list[str] = []
    last_action: dict[str, Any] | None = None

    for index in range(max(0, samples)):
        payload = sample_payload(index)
        started = time.perf_counter()
        try:
            last_action = post_json(f"{base_url}/api/pet-action", payload, timeout=timeout)
            timings.append(round((time.perf_counter() - started) * 1000, 1))
        except Exception as exc:
            errors.append(str(exc))

    stats: dict[str, Any] = {
        "samplesRequested": samples,
        "samplesSucceeded": len(timings),
        "values": timings,
        "errors": errors[:5],
        "lastAction": last_action,
    }
    if timings:
        stats.update(
            {
                "min": min(timings),
                "median": round(median(timings), 1),
                "mean": round(mean(timings), 1),
                "max": max(timings),
            }
        )
    return stats


def sample_payload(index: int) -> dict[str, Any]:
    x = round(0.42 + (index % 3) * 0.08, 3)
    y = round(0.56 - (index % 2) * 0.06, 3)
    return {
        "pet": "squeaky",
        "message": "i gently pet you, then freeze the blue cube",
        "camera": {"enabled": False},
        "scene": {
            "objects": [
                {"id": "cube-blue", "kind": "cube", "speed": 1.4, "distanceToPet": 1.1, "moving": True},
                {"id": "ball-red", "kind": "sphere", "speed": 0.2, "distanceToPet": 2.0, "moving": False},
                {"id": "star-yellow", "kind": "star", "speed": 0.8, "distanceToPet": 1.7, "moving": True},
            ]
        },
        "forces": [{"kind": "mouse-drag", "targetId": "cube-blue", "strength": 0.7}],
        "detectedObjects": [],
        "interactions": [
            {
                "kind": "pet",
                "pet": "squeaky",
                "at": index,
                "pointer": {
                    "modality": "mouse",
                    "screen": {"x": x, "y": y},
                    "ndc": {"x": round(x * 2 - 1, 3), "y": round(1 - y * 2, 3)},
                    "world": {"x": 0.1, "y": 0.45, "z": 0.0},
                },
            }
        ],
        "cooldowns": {},
        "petState": {"emotion": "curious"},
    }


def process_snapshot(port: int) -> dict[str, Any]:
    app_pids = listener_pids(port)
    rows = all_process_rows()
    interesting = [
        row
        for row in rows
        if row["pid"] in app_pids or "ollama" in row["command"].lower()
    ]
    return {
        "appListenerPids": app_pids,
        "rows": interesting,
        "totals": {
            "rssMb": round(sum(row["rssMb"] for row in interesting), 1),
            "cpuPercent": round(sum(row["cpuPercent"] for row in interesting), 1),
        },
    }


def listener_pids(port: int) -> list[int]:
    output = command_text(["lsof", f"-tiTCP:{port}", "-sTCP:LISTEN"])
    if not output.get("ok"):
        return []
    pids = []
    for line in output.get("stdout", "").splitlines():
        try:
            pids.append(int(line.strip()))
        except ValueError:
            pass
    return pids


def all_process_rows() -> list[dict[str, Any]]:
    output = command_text(["ps", "-axo", "pid,ppid,rss,%mem,%cpu,etime,command"])
    if not output.get("ok"):
        return []

    rows: list[dict[str, Any]] = []
    for line in output.get("stdout", "").splitlines()[1:]:
        parts = line.strip().split(None, 6)
        if len(parts) < 7:
            continue
        try:
            rss_kb = int(parts[2])
            rows.append(
                {
                    "pid": int(parts[0]),
                    "ppid": int(parts[1]),
                    "rssKb": rss_kb,
                    "rssMb": round(rss_kb / 1024, 1),
                    "memPercent": float(parts[3]),
                    "cpuPercent": float(parts[4]),
                    "etime": parts[5],
                    "command": parts[6],
                }
            )
        except ValueError:
            continue
    return rows


def powermetrics_snapshot() -> dict[str, Any]:
    if not shutil.which("powermetrics"):
        return {"measured": False, "reason": "powermetrics is not installed"}

    sudo_check = command_text(["sudo", "-n", "true"])
    if not sudo_check.get("ok"):
        return {
            "measured": False,
            "reason": "sudo is required for powermetrics; run the script with a cached sudo session",
            "stderr": sudo_check.get("stderr", "")[:400],
        }

    output = command_text(
        ["sudo", "-n", "powermetrics", "--samplers", "cpu_power,gpu_power", "-i", "1000", "-n", "1"],
        timeout=8,
    )
    return {
        "measured": bool(output.get("ok")),
        "stdoutExcerpt": output.get("stdout", "")[:2400],
        "stderrExcerpt": output.get("stderr", "")[:800],
    }


def command_text(command: list[str], timeout: float = 5) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "ok": completed.returncode == 0,
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "error": str(exc), "stdout": "", "stderr": ""}


if __name__ == "__main__":
    main()
