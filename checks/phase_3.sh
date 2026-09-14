#!/usr/bin/env bash
# Phase 3 check: both scripted conversations produce reply text on every turn and
# still end in a booking; pytest proves a fake slot in present_slots output triggers
# the template fallback and is logged as such.
set -euo pipefail
cd "$(dirname "$0")/.."

MODEL_ID="qwen3.5-0.8b-q8"
PROMPT_VERSION="baseline"
PORT=8768
LOG="logs/phase_3_check.jsonl"
OUT="logs/phase_3_turns.jsonl"
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
    --prompt-version "$PROMPT_VERSION" --session "check3_$conv" \
    --script "checks/conversations/$conv.txt" --json | tee -a "$OUT" | uv run python -c "
import json, sys
for line in sys.stdin:
    t = json.loads(line)
    n = t['debug']['nlg']
    tag = 'model' if n and n['ok'] else ('TEMPLATE:' + n['reason_code'] if n else 'template')
    print(f\"you: {t['text']}\")
    print(f\"bot: {t['reply']}\")
    print(f\"     [{t['state']}] {t['debug']['reply_facts']['kind']} via {tag}\")
"
done

uv run python - "$LOG" "$OUT" <<'PY'
import json, sys
log_path, out_path = sys.argv[1], sys.argv[2]
turns = [json.loads(l) for l in open(out_path)]
log = [json.loads(l) for l in open(log_path)]

for t in turns:
    assert isinstance(t["reply"], str) and t["reply"].strip(), f"empty reply on turn {t['text']!r}"
for conv in ("check3_new_patient", "check3_returning_patient"):
    last = [t for t in turns if t["session_id"] == conv][-1]
    assert last["state"] == "END" and last["debug"]["reply_facts"]["kind"] == "confirm_booking", f"{conv}: no booking"
    print(f"{conv}: booked, final reply: {last['reply']!r}")

nlg_calls = [l for l in log if l["prompt_name"] in ("ask_question", "present_slots", "no_slots", "confirm_booking", "clarify")]
expected = sum(1 for t in turns if t["debug"]["nlg"])
assert len(nlg_calls) == expected, f"{len(nlg_calls)} NLG log lines, expected {expected}"
tmpl = [l for l in nlg_calls if not l["ok"]]
print(f"log: {len(log)} model calls total, {len(nlg_calls)} NLG, {len(tmpl)} used the template ({', '.join(sorted({l['prompt_name']+':'+l['reason_code'] for l in tmpl})) or 'none'})")
PY

uv run pytest tests/nlg tests/test_nlg_runner.py -q

echo "phase_3: PASS"
