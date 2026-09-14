"""JSONL log, one line per model call. Fields are fixed by design.md section 7."""

import json
import os
from pathlib import Path

FIELDS = (
    "session_id", "turn", "state", "model_id", "prompt_name", "prompt_version",
    "validator_version", "ok", "reason_code", "raw_output", "latency_ms",
)
DEFAULT_PATH = "logs/model_calls.jsonl"


def log_path() -> Path:
    return Path(os.environ.get("BOOKING_LOG_PATH", DEFAULT_PATH))


def write(record: dict) -> None:
    missing = [f for f in FIELDS if f not in record]
    if missing:
        raise ValueError(f"log record missing fields: {missing}")
    path = log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps({k: record[k] for k in FIELDS}) + "\n")
