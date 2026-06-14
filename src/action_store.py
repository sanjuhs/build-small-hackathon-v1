from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any


DEFAULT_DB_PATH = "data/pet-action-events.sqlite3"


def record_pet_action(payload: dict[str, Any], action: dict[str, Any], server_latency_ms: float) -> None:
    db_path = action_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    request_json, frame_bytes, frame_sha = sanitized_payload(payload)
    debug = action.get("debug") if isinstance(action.get("debug"), dict) else {}
    interaction = action.get("interaction") if isinstance(action.get("interaction"), dict) else {}
    power = action.get("power") if isinstance(action.get("power"), dict) else {}

    with sqlite3.connect(db_path) as connection:
        ensure_schema(connection)
        connection.execute(
            """
            INSERT INTO pet_action_events (
              created_at, pet, message, policy, provider, model, intent, speech,
              emotion, animation, interaction_verb, power_name, target_id,
              camera_frame_source, frame_bytes, frame_sha256,
              prompt_tokens, completion_tokens, tokens_per_second,
              model_latency_ms, server_latency_ms, function_calls,
              state_updates_requested, error_reason, error_type,
              request_json, action_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                iso_now(),
                str(payload.get("pet") or ""),
                str(payload.get("message") or ""),
                str(debug.get("policy") or ""),
                str(debug.get("provider") or ""),
                str(debug.get("model") or ""),
                str(action.get("intent") or ""),
                str(action.get("speech") or ""),
                str(action.get("emotion") or ""),
                str(action.get("animation") or ""),
                str(interaction.get("verb") or ""),
                str(power.get("name") or ""),
                str(interaction.get("targetId") or power.get("targetId") or ""),
                str(payload.get("cameraFrameSource") or debug.get("cameraFrameSource") or ""),
                frame_bytes,
                frame_sha,
                int_or_none(debug.get("promptTokens")),
                int_or_none(debug.get("completionTokens")),
                float_or_none(debug.get("tokensPerSecond")),
                float_or_none(debug.get("modelLatencyMs")),
                float_or_none(debug.get("serverLatencyMs") or server_latency_ms),
                int_or_none(debug.get("functionCalls")),
                int_or_none(debug.get("stateUpdatesRequested")),
                str(debug.get("reason") or debug.get("modalLastError") or debug.get("visionLastError") or ""),
                str(debug.get("modalLastErrorType") or debug.get("visionLastErrorType") or ""),
                request_json,
                json.dumps(action, ensure_ascii=True, sort_keys=True),
            ),
        )


def fetch_action_events(limit: int = 50) -> dict[str, Any]:
    db_path = action_db_path()
    if not db_path.exists():
        return {"events": [], "dbPath": str(db_path), "count": 0}
    limit = max(1, min(250, int(limit or 50)))
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        ensure_schema(connection)
        rows = connection.execute(
            """
            SELECT id, created_at, pet, message, policy, provider, model, intent, speech,
                   interaction_verb, power_name, target_id, camera_frame_source,
                   prompt_tokens, completion_tokens, tokens_per_second,
                   model_latency_ms, server_latency_ms, function_calls,
                   state_updates_requested, error_reason, error_type
            FROM pet_action_events
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return {"events": [dict(row) for row in rows], "dbPath": str(db_path), "count": len(rows)}


def action_stats() -> dict[str, Any]:
    db_path = action_db_path()
    if not db_path.exists():
        return {"dbPath": str(db_path), "total": 0, "modalActions": 0, "unavailable": 0}
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        ensure_schema(connection)
        summary = dict(
            connection.execute(
                """
                SELECT
                  COUNT(*) AS total,
                  SUM(CASE WHEN policy = 'modal_omni_action' THEN 1 ELSE 0 END) AS modalActions,
                  SUM(CASE WHEN policy = 'model_unavailable' THEN 1 ELSE 0 END) AS unavailable,
                  ROUND(AVG(CASE WHEN model_latency_ms IS NOT NULL THEN model_latency_ms END), 1) AS avgModelLatencyMs,
                  ROUND(AVG(CASE WHEN tokens_per_second IS NOT NULL THEN tokens_per_second END), 2) AS avgTokensPerSecond,
                  ROUND(AVG(CASE WHEN prompt_tokens IS NOT NULL THEN prompt_tokens END), 1) AS avgPromptTokens,
                  ROUND(AVG(CASE WHEN completion_tokens IS NOT NULL THEN completion_tokens END), 1) AS avgCompletionTokens
                FROM pet_action_events
                """
            ).fetchone()
        )
        by_policy = [
            dict(row)
            for row in connection.execute(
                """
                SELECT policy, COUNT(*) AS count, ROUND(AVG(server_latency_ms), 1) AS avgServerLatencyMs
                FROM pet_action_events
                GROUP BY policy
                ORDER BY count DESC
                """
            ).fetchall()
        ]
    summary["dbPath"] = str(db_path)
    summary["byPolicy"] = by_policy
    return summary


def ensure_schema(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS pet_action_events (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          created_at TEXT NOT NULL,
          pet TEXT,
          message TEXT,
          policy TEXT,
          provider TEXT,
          model TEXT,
          intent TEXT,
          speech TEXT,
          emotion TEXT,
          animation TEXT,
          interaction_verb TEXT,
          power_name TEXT,
          target_id TEXT,
          camera_frame_source TEXT,
          frame_bytes INTEGER,
          frame_sha256 TEXT,
          prompt_tokens INTEGER,
          completion_tokens INTEGER,
          tokens_per_second REAL,
          model_latency_ms REAL,
          server_latency_ms REAL,
          function_calls INTEGER,
          state_updates_requested INTEGER,
          error_reason TEXT,
          error_type TEXT,
          request_json TEXT NOT NULL,
          action_json TEXT NOT NULL
        )
        """
    )
    connection.execute("CREATE INDEX IF NOT EXISTS idx_pet_action_events_created ON pet_action_events(created_at)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_pet_action_events_policy ON pet_action_events(policy)")


def sanitized_payload(payload: dict[str, Any]) -> tuple[str, int | None, str | None]:
    frame = payload.get("cameraFrame")
    frame_bytes = None
    frame_sha = None
    clean = dict(payload)
    if isinstance(frame, str) and frame:
        frame_bytes = len(frame.encode("utf-8"))
        frame_sha = hashlib.sha256(frame.encode("utf-8")).hexdigest()
        prefix = frame.split(",", 1)[0][:72]
        clean["cameraFrame"] = f"{prefix},<omitted {frame_bytes} bytes sha256:{frame_sha[:12]}>"
    return json.dumps(clean, ensure_ascii=True, sort_keys=True), frame_bytes, frame_sha


def action_db_path() -> Path:
    return Path(os.getenv("TOYBOX_ACTION_DB_PATH", DEFAULT_DB_PATH)).expanduser()


def iso_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def int_or_none(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def float_or_none(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
