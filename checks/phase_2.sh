#!/usr/bin/env bash
# Phase 2 check: replay two scripted CLI conversations through the real model,
# assert each ends in a booking, and assert the JSONL log has one line per
# model call with every field from design.md section 7.
set -euo pipefail
cd "$(dirname "$0")/.."

MODEL_ID="qwen3.5-0.8b-q8"
PROMPT_VERSION="baseline"
PORT=8767
LOG="logs/phase_2_check.jsonl"
OUT="logs/phase_2_turns.jsonl"
rm -f "$LOG" "$OUT"

BOOKING_LOG_PATH="$LOG" uv run uvicorn app.api:app --port "$PORT" --log-level warning &
SERVER_PID=$!
trap 'kill $SERVER_PID 2>/dev/null || true' EXIT
for _ in $(seq 1 30); do
  curl -sf "http://127.0.0.1:$PORT/health" >/dev/null 2>&1 && break
  sleep 0.5
done

for conv in new_patient returning_patient; do
  echo "--- $conv ---"
  uv run python clients/cli.py --url "http://127.0.0.1:$PORT" --model "$MODEL_ID" \
    --prompt-version "$PROMPT_VERSION" --session "check_$conv" \
    --script "checks/conversations/$conv.txt" --json | tee -a "$OUT" | uv run python -c "
import json, sys
for line in sys.stdin:
    t = json.loads(line)
    calls = t['debug']['validator_results']
    tags = ' '.join(f\"{c['prompt_name']}={'ok' if c['ok'] else 'FALLBACK:'+c['reason_code']}\" for c in calls)
    print(f\"[{t['state']:<18}] {t['text']!r:<48} -> {t['debug']['reply_facts']['kind']:<16} {tags}\")
"
done

uv run python - "$LOG" "$OUT" <<'PY'
import json, sys
log_path, out_path = sys.argv[1], sys.argv[2]
turns = [json.loads(l) for l in open(out_path)]
log = [json.loads(l) for l in open(log_path)]

# 1. both conversations end in a booking
for conv in ("check_new_patient", "check_returning_patient"):
    last = [t for t in turns if t["session_id"] == conv][-1]
    assert last["state"] == "END", f"{conv}: final state {last['state']}"
    assert last["debug"]["reply_facts"]["kind"] == "confirm_booking", f"{conv}: no booking, got {last['debug']['reply_facts']}"
    b = last["debug"]["reply_facts"]["booking"]
    print(f"{conv}: booked {b['doctor_name']} at {b['start']} ({b['session_type']})")

# 2. one log line per model call, every required field present
required = ["session_id", "turn", "state", "model_id", "prompt_name", "prompt_version",
            "validator_version", "ok", "reason_code", "raw_output", "latency_ms"]
expected_calls = sum(len(t["debug"]["validator_results"]) for t in turns)
assert len(log) == expected_calls, f"log has {len(log)} lines, expected {expected_calls} model calls"
for line in log:
    missing = [k for k in required if k not in line]
    assert not missing, f"log line missing {missing}: {line}"
assert all(l["prompt_version"] == "baseline" for l in log)
fallbacks = [l for l in log if not l["ok"]]
print(f"log: {len(log)} model calls, {len(fallbacks)} fallbacks, all {len(required)} fields present")
PY

echo "phase_2: PASS"
