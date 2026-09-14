#!/usr/bin/env bash
# Phase 0 check: /health responds, and complete() returns schema-valid JSON
# with latency and logprobs for a constrained yes/no toy prompt.
set -euo pipefail
cd "$(dirname "$0")/.."

MODEL_ID="qwen3.5-0.8b-q8"
GGUF_PATH="$(uv run python -c "import json; print(json.load(open('models/registry.json'))['$MODEL_ID']['path'])")"

if [ ! -f "$GGUF_PATH" ]; then
  echo "FAIL: GGUF not found at $GGUF_PATH"
  echo "Download it first (see phase 0 instructions), then rerun."
  exit 1
fi

# --- 1. /health ---
PORT=8765
uv run uvicorn app.api:app --port "$PORT" --log-level warning &
SERVER_PID=$!
trap 'kill $SERVER_PID 2>/dev/null || true' EXIT

for _ in $(seq 1 30); do
  if curl -sf "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; then break; fi
  sleep 0.5
done

HEALTH="$(curl -sf "http://127.0.0.1:$PORT/health")"
echo "GET /health -> $HEALTH"
[ "$HEALTH" = '{"status":"ok"}' ] || { echo "FAIL: unexpected /health body"; exit 1; }

# --- 2. constrained yes/no through llm_client.complete() ---
uv run python -c "
import json
from app.llm_client import complete
schema = {'type': 'object', 'properties': {'intent': {'type': 'string', 'enum': ['yes', 'no', 'other']}}, 'required': ['intent'], 'additionalProperties': False}
prompt = 'The assistant asked: Is this your first consultation with us? The user replied: yes it is. Classify the reply as yes, no, or other.'
r = complete('$MODEL_ID', prompt, schema, {'temperature': 0.0, 'max_tokens': 32})
print('raw:', r['raw'])
print('output:', r['output'])
print('latency_ms:', r['latency_ms'])
print('logprobs tokens:', len(r['logprobs']))
assert r['output']['intent'] in ('yes', 'no', 'other'), 'intent not in enum'
assert r['latency_ms'] > 0, 'latency_ms missing'
assert isinstance(r['logprobs'], list) and len(r['logprobs']) > 0, 'logprobs missing'
print('PASS: constrained yes/no parsed with latency and logprobs')
"

echo "phase_0: PASS"
