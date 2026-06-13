from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.pet_payload import trace_payload


def write_trace(payload: dict[str, Any], action: dict[str, Any]) -> None:
    if os.getenv("TOYBOX_TRACE", "1").lower() in {"0", "false", "no"}:
        return

    path = Path(os.getenv("TOYBOX_TRACE_PATH", "data/traces/pet-actions.jsonl"))
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "input": trace_payload(payload),
        "output": action,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=True) + "\n")
