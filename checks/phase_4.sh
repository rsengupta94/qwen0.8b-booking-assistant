#!/usr/bin/env bash
# Phase 4 check: a scripted conversation changes the doctor after slots were shown.
# Asserts the state rewinds to ASK_DOCTOR_PREF and lands on ASK_DAYS, the offered slots
# are cleared, and availability is re-fetched for the new doctor. Then pytest covers the
# rewind map, downstream clearing and the correction cap with a stubbed NLU.
set -euo pipefail
cd "$(dirname "$0")/.."

MODEL_ID="qwen3.5-0.8b-q8"
PROMPT_VERSION="baseline"
PORT=8770
LOG="logs/phase_4_check.jsonl"
OUT="logs/phase_4_turns.jsonl"
rm -f "$LOG" "$OUT"

BOOKING_LOG_PATH="$LOG" uv run uvicorn app.api:app --port "$PORT" --log-level warning &
SERVER_PID=$!
trap 'kill $SERVER_PID 2>/dev/null || true' EXIT
for _ in $(seq 1 30); do
  curl -sf "http://127.0.0.1:$PORT/health" >/dev/null 2>&1 && break
  sleep 0.5
done

echo "--- change_doctor ---"
uv run python clients/cli.py --url "http://127.0.0.1:$PORT" --model "$MODEL_ID" \
  --prompt-version "$PROMPT_VERSION" --session "check4_change_doctor" \
  --script "checks/conversations/change_doctor.txt" --json | tee -a "$OUT" | uv run python -c "
import json, sys
for line in sys.stdin:
    t = json.loads(line)
    calls = ' '.join(f\"{c['prompt_name']}={'ok' if c['ok'] else 'FALLBACK:'+c['reason_code']}\" for c in t['debug']['validator_results'])
    corr = t['debug']['correction']
    tag = f\" REWIND {corr['field']} -> {corr['rewound_to']}\" if corr else ''
    print(f\"you: {t['text']}\")
    print(f\"bot: {t['reply']}\")
    print(f\"     [{t['state']}] {t['debug']['reply_facts']['kind']} | {calls}{tag}\")
"

uv run python - "$LOG" "$OUT" <<'PY'
import json, sys
log_path, out_path = sys.argv[1], sys.argv[2]
turns = [json.loads(l) for l in open(out_path)]
log = [json.loads(l) for l in open(log_path)]
by_text = {t["text"]: t for t in turns}

# 1. slots shown for the first doctor
first = by_text["wednesday afternoon"]
assert first["state"] == "CAPTURE_CHOICE" and first["debug"]["reply_facts"]["kind"] == "present_slots", first["debug"]["reply_facts"]
assert first["debug"]["reply_facts"]["doctor_name"] == "Dr. Meera Rao"
assert all(s["doctor_id"] == "d_rao" for s in first["debug"]["reply_facts"]["slots"])

# 2. the correction rewinds, clears the offer, and lands on ASK_DAYS for the new doctor
corr = by_text["actually, I'd rather see Dr Sana Khan instead"]
assert corr["debug"]["correction"] == {"field": "doctor", "rewound_to": "ASK_DOCTOR_PREF"}, corr["debug"]["correction"]
assert corr["state"] == "ASK_DAYS", corr["state"]
assert corr["debug"]["reply_facts"] == {"kind": "ask_question", "question": "days"}, corr["debug"]["reply_facts"]
names = [c["prompt_name"] for c in corr["debug"]["validator_results"]]
assert names == ["turn_classifier"], names  # roster name in the text: doctor resolved in code, no doctor_pref call
assert corr["debug"]["nlu_output"]["source"] == "roster_match", corr["debug"]["nlu_output"]
print(f"correction turn: rewound to ASK_DOCTOR_PREF, now ASK_DAYS, NLU calls {names}")

# 3. availability re-fetched for the new doctor
second = by_text["thursday afternoon"]
assert second["debug"]["reply_facts"]["kind"] == "present_slots"
assert second["debug"]["reply_facts"]["doctor_name"] == "Dr. Sana Khan", second["debug"]["reply_facts"]["doctor_name"]
assert all(s["doctor_id"] == "d_khan" for s in second["debug"]["reply_facts"]["slots"])
print(f"re-fetched: {len(second['debug']['reply_facts']['slots'])} slots for Dr. Sana Khan")

# 4. booking is with the new doctor
last = turns[-1]
assert last["state"] == "END" and last["debug"]["reply_facts"]["kind"] == "confirm_booking", last["debug"]["reply_facts"]
assert last["debug"]["reply_facts"]["booking"]["doctor_id"] == "d_khan"
print(f"booked {last['debug']['reply_facts']['booking']['doctor_name']} at {last['debug']['reply_facts']['booking']['start']}")

# 5. every turn_classifier call is logged with its state; exactly one flagged a correction
tc = [l for l in log if l["prompt_name"] == "turn_classifier"]
assert tc, "no turn_classifier log lines"
assert all(l["validator_version"] == "1" and l["prompt_version"] == "baseline" for l in tc)
corrections = [t for t in turns if t["debug"]["correction"]]
assert len(corrections) == 1, [t["text"] for t in corrections]
print(f"log: {len(log)} model calls, {len(tc)} turn_classifier calls, 1 correction")
PY

uv run pytest tests/test_correction.py tests/nlu/test_turn_classifier.py tests/test_api.py -q

echo "phase_4: PASS"
