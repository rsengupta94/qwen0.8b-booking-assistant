"""Validating writer for judge verdicts. The judge sub-agent calls this once per conversation.

Refuses anything that does not line up with the transcript: wrong turn count, missing or duplicate
turns, labels outside yes/no, empty or overlong reasons. Nothing is written on refusal.
Usage: uv run python -m evals.judge_write --pool dev --card <card_id> --judge-model <name> --verdicts '<json list>'
  where the JSON list is [{"turn": 1, "fits": "yes"|"no", "reason": "<= 200 chars"}, ...], one per bot turn.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MAX_REASON = 200


def validate(transcript: dict, verdicts: list) -> list[str]:
    errors = []
    turns = [tr["turn"] for tr in transcript["turns"]]
    seen = [v.get("turn") for v in verdicts]
    if sorted(seen) != sorted(turns):
        errors.append(f"turns do not match transcript: expected {turns}, got {seen}")
    for v in verdicts:
        if v.get("fits") not in ("yes", "no"):
            errors.append(f"turn {v.get('turn')}: fits must be yes or no")
        r = (v.get("reason") or "").strip()
        if not r or len(r) > MAX_REASON:
            errors.append(f"turn {v.get('turn')}: reason must be 1 to {MAX_REASON} characters")
    return errors


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", required=True, choices=["dev", "heldout"])
    ap.add_argument("--card", required=True)
    ap.add_argument("--judge-model", required=True)
    ap.add_argument("--verdicts", required=True, help="JSON list")
    a = ap.parse_args()
    t = json.loads((ROOT / "transcripts" / a.pool / f"{a.card}.json").read_text())
    try:
        verdicts = json.loads(a.verdicts)
        assert isinstance(verdicts, list)
    except (ValueError, AssertionError):
        sys.exit("REFUSED: --verdicts is not a JSON list")
    errors = validate(t, verdicts)
    if errors:
        sys.exit("REFUSED:\n  " + "\n  ".join(errors))
    out = {"card_id": a.card, "pool": a.pool, "judge_model": a.judge_model,
           "judged_at": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
           "session_id": t["run"]["session_id"],
           "verdicts": sorted(({"turn": int(v["turn"]), "fits": v["fits"], "reason": v["reason"].strip()} for v in verdicts), key=lambda v: v["turn"])}
    d = ROOT / "verdicts" / a.pool
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{a.card}.json").write_text(json.dumps(out, indent=2) + "\n")
    n_no = sum(v["fits"] == "no" for v in out["verdicts"])
    print(f"WRITTEN {a.card}: {len(out['verdicts'])} verdicts, {n_no} no")


if __name__ == "__main__":
    main()
