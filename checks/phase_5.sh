#!/usr/bin/env bash
# Phase 5 check: (1) "what are your fees?" at ASK_FIRST_CONSULT gets the FAQ answer plus the
# re-asked question in one reply, state unchanged; (2) "you decide" picks a doctor_id from the
# category shortlist with a non-empty reason and the reply names that doctor. Then pytest.
set -euo pipefail
cd "$(dirname "$0")/.."

MODEL_ID="qwen3.5-0.8b-q8"
PROMPT_VERSION="baseline"
PORT=8771
LOG="logs/phase_5_check.jsonl"
OUT="logs/phase_5_turns.jsonl"
rm -f "$LOG" "$OUT"

BOOKING_LOG_PATH="$LOG" uv run uvicorn app.api:app --port "$PORT" --log-level warning &
SERVER_PID=$!
trap 'kill $SERVER_PID 2>/dev/null || true' EXIT
for _ in $(seq 1 30); do
  curl -sf "http://127.0.0.1:$PORT/health" >/dev/null 2>&1 && break
  sleep 0.5
done

for conv in faq_fees you_decide; do
  echo "--- $conv ---"
  uv run python clients/cli.py --url "http://127.0.0.1:$PORT" --model "$MODEL_ID" \
    --prompt-version "$PROMPT_VERSION" --session "check5_$conv" \
    --script "checks/conversations/$conv.txt" --json | tee -a "$OUT" | uv run python -c "
import json, sys
for line in sys.stdin:
    t = json.loads(line)
    calls = ' '.join(f\"{c['prompt_name']}={'ok' if c['ok'] else 'FALLBACK:'+c['reason_code']}\" for c in t['debug']['validator_results'])
    n = t['debug']['nlg']
    via = 'model' if n and n['ok'] else ('TEMPLATE:' + n['reason_code'] if n else 'template')
    print(f\"you: {t['text']}\")
    print(f\"bot: {t['reply']}\")
    print(f\"     [{t['state']}] {t['debug']['reply_facts']['kind']} via {via} | {calls}\")
"
done

uv run python - "$LOG" "$OUT" <<'PY'
import json, sys
log_path, out_path = sys.argv[1], sys.argv[2]
turns = [json.loads(l) for l in open(out_path)]
log = [json.loads(l) for l in open(log_path)]
faq = json.load(open("fixtures/faq.json"))
fees = next(e["answer"] for e in faq if e["topic"] == "fees")
QUESTION = "Is this your first consultation with us?"

# 1. FAQ detour: answer + re-ask in one reply, state unchanged, no re-ask count spent
t = next(t for t in turns if t["text"] == "what are your fees?")
assert t["state"] == "ASK_FIRST_CONSULT", t["state"]
facts = t["debug"]["reply_facts"]
assert facts["kind"] == "clarify" and facts["question"] == "first_consult" and facts["faq_answer"] == fees, facts
assert fees in t["reply"] and QUESTION in t["reply"], t["reply"]
names = [c["prompt_name"] for c in t["debug"]["validator_results"]]
assert names == ["yes_no", "off_script"], names
last = [x for x in turns if x["session_id"] == "check5_faq_fees"][-1]
assert last["state"] == "END" and last["debug"]["reply_facts"]["kind"] == "confirm_booking", last["debug"]["reply_facts"]
print(f"faq_fees: detour at ASK_FIRST_CONSULT answered '{fees}' and re-asked; booked {last['debug']['reply_facts']['booking']['doctor_name']}")

# 2. you decide: doctor_id from the shortlist, non-empty reason, reply names the doctor
t = next(t for t in turns if t["text"] == "you decide")
pick = next(c for c in t["debug"]["validator_results"] if c["prompt_name"] == "doctor_pick")
doctors = {d["id"]: d for d in json.load(open("fixtures/doctors.json"))}
shortlist = [d["id"] for d in doctors.values() if "sleep" in d["categories"]]
assert pick["result"]["doctor_id"] in shortlist, (pick["result"], shortlist)
assert pick["ok"] and isinstance(pick["result"]["reason"], str) and pick["result"]["reason"].strip(), pick
assert t["state"] == "ASK_DAYS" and t["debug"]["reply_facts"]["kind"] == "ask_question"
name = doctors[pick["result"]["doctor_id"]]["name"]
assert t["debug"]["reply_facts"]["suggested_doctor"] == name and name in t["reply"], t["reply"]
last = [x for x in turns if x["session_id"] == "check5_you_decide"][-1]
assert last["state"] == "END" and last["debug"]["reply_facts"]["booking"]["doctor_id"] == pick["result"]["doctor_id"]
print(f"you_decide: picked {name} from {shortlist}, reason: {pick['result']['reason']!r}; booked")

# 3. off_script, clarify and doctor_pick calls are logged with versions
for name in ("off_script", "clarify", "doctor_pick"):
    lines = [l for l in log if l["prompt_name"] == name]
    assert lines, f"no {name} log lines"
    assert all(l["prompt_version"] == "baseline" and l["validator_version"] for l in lines)
print(f"log: {len(log)} model calls")
PY

uv run pytest tests/test_off_script.py tests/nlu/test_off_script.py tests/nlu/test_doctor_pick.py tests/nlg/test_clarify.py tests/nlg/test_ask_question.py -q

echo "phase_5: PASS"
