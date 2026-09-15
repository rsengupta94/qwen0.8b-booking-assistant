#!/usr/bin/env bash
# Phase 6 check: the UI is served at /, /models and /prompts return non-empty lists,
# and one turn through /message/stream ends with a done event. Then the API tests.
set -euo pipefail
cd "$(dirname "$0")/.."

PORT=8772
BOOKING_LOG_PATH="logs/phase_6_check.jsonl" uv run uvicorn app.api:app --port "$PORT" --log-level warning &
SERVER_PID=$!
trap 'kill $SERVER_PID 2>/dev/null || true' EXIT
for _ in $(seq 1 30); do
  curl -sf "http://127.0.0.1:$PORT/health" >/dev/null 2>&1 && break
  sleep 0.5
done
BASE="http://127.0.0.1:$PORT"

# 1. static UI
CT="$(curl -sf -o /dev/null -w '%{content_type}' "$BASE/")"
BODY="$(curl -sf "$BASE/")"
echo "GET / -> $CT, $(echo -n "$BODY" | wc -c | tr -d ' ') bytes"
case "$CT" in text/html*) ;; *) echo "FAIL: / is not text/html"; exit 1;; esac
echo "$BODY" | grep -q 'id="model"' || { echo "FAIL: / has no model dropdown"; exit 1; }
echo "$BODY" | grep -q 'id="prompt_version"' || { echo "FAIL: / has no prompt-version dropdown"; exit 1; }
echo "$BODY" | grep -q 'id="debug"' || { echo "FAIL: / has no debug panel"; exit 1; }

# 2. dropdown sources
MODELS="$(curl -sf "$BASE/models")"
PROMPTS="$(curl -sf "$BASE/prompts")"
echo "GET /models -> $MODELS"
echo "GET /prompts -> $PROMPTS"
uv run python - "$MODELS" "$PROMPTS" <<'PY'
import json, sys
models, prompts = json.loads(sys.argv[1]), json.loads(sys.argv[2])
assert isinstance(models, list) and models, "models list empty"
assert all({"model_id", "quant", "available"} <= set(m) for m in models), models
assert any(m["available"] for m in models), "no model has its GGUF on disk"
assert isinstance(prompts, list) and "baseline" in prompts, prompts
print(f"{len(models)} model(s), {len(prompts)} prompt version(s)")
PY

# 3. streaming turn: first turn is GREET, one NLG call for the greeting
STREAM="$(curl -sf -N -X POST "$BASE/message/stream" -H 'content-type: application/json' \
  -d '{"session_id":"check6","model_id":"qwen3.5-0.8b-q8","prompt_version":"baseline","text":"hi"}')"
echo "$STREAM" | sed 's/^/  /' | head -20
echo "$STREAM" | grep -q '^event: start$' || { echo "FAIL: no start event"; exit 1; }
echo "$STREAM" | grep -q '^event: done$' || { echo "FAIL: no done event"; exit 1; }
echo "$STREAM" | grep -A1 '^event: done$' | grep -q '"state": "ASK_FIRST_CONSULT"' || { echo "FAIL: done event has wrong state"; exit 1; }
echo "stream: start + done events received"

uv run pytest tests/test_api.py -q

echo "phase_6: PASS"
