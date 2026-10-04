#!/usr/bin/env bash
# E5 check: eval server tests pass; the eval server, started on a fresh free port, lists at least one run
# (one per setup) and returns a run payload with a heatmap row for every NLU and NLG prompt in
# prompts/<version>/ for both pools; held-out drill-down carries no text fields; cross-origin reads from
# a product page are allowed; the product UI has the Evals view. Prints counts only.
set -euo pipefail
cd "$(dirname "$0")/.."

uv run pytest tests/test_eval_server.py -q

grep -q 'id="evals"' clients/ui/index.html || { echo "FAIL: product UI has no Evals view"; exit 1; }

# Fresh free port: a stale server on a fixed port would answer with old data.
PORT="$(uv run python -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1])')"
set -m  # own process group, so the trap kills uvicorn and not just the uv wrapper
uv run uvicorn evals.server:app --port "$PORT" --log-level warning &
SERVER_PID=$!
set +m
trap 'kill -- -$SERVER_PID 2>/dev/null || true' EXIT
BASE="http://127.0.0.1:$PORT"
for _ in $(seq 1 40); do
  curl -sf "$BASE/evals/runs" >/dev/null 2>&1 && break
  sleep 0.25
done

RUNS="$(curl -sf "$BASE/evals/runs")"
RUN_ID="$(echo "$RUNS" | uv run python -c 'import json,sys; r=json.load(sys.stdin); print(r[0]["run_id"] if r else "")')"
[ -n "$RUN_ID" ] || { echo "FAIL: /evals/runs is empty"; exit 1; }
curl -sf "$BASE/evals/runs/$RUN_ID" > "${TMPDIR:-/tmp}/eval5_run.json"

CORS="$(curl -sf -o /dev/null -D - -H 'Origin: http://localhost:8000' "$BASE/evals/runs" | tr -d '\r' | sed -n 's/^access-control-allow-origin: //Ip')"
[ "$CORS" = "http://localhost:8000" ] || { echo "FAIL: eval server does not allow reads from the product page (got '$CORS')"; exit 1; }
echo "cross-origin read from http://localhost:8000: allowed"

uv run python - "$RUNS" "${TMPDIR:-/tmp}/eval5_run.json" <<'PY'
import json, sys
from pathlib import Path
runs = json.loads(sys.argv[1])
run = json.loads(Path(sys.argv[2]).read_text())
setups = [(r["source"], r["prompt_version"], r["model_id"], r["eval_set_version"]) for r in runs]
assert len(setups) == len(set(setups)), "run list has more than one run per setup"
print(f"runs listed: {len(runs)}; checking {run['run_id']}")
want = sorted(p.stem for kind in ("nlu", "nlg") for p in Path("prompts", run["prompt_version"], kind).glob("*.md"))
TEXT = {"user", "reply", "bot", "raw_output", "summary", "text"}
for pool in ("heldout", "dev"):
    v = run["pools"][pool]
    have = sorted(row["prompt"] for row in v["heatmap"])
    missing = sorted(set(want) - set(have))
    assert not missing, f"{pool}: no heatmap row for {missing}"
    print(f"{pool}: heatmap rows={len(have)} of {len(want)} prompts; calls={sum(r['calls'] for r in v['heatmap'])}; "
          f"sessions passed={v['sessions']['passed']}/{v['sessions']['n']}")
leaks = [k for c in run["pools"]["heldout"]["calls"] for k in c if k in TEXT]
assert not leaks and not run["pools"]["heldout"].get("turns"), f"held-out payload carries text: {sorted(set(leaks))}"
print("held-out drill-down: structured fields only")
PY

echo "eval_5: PASS"
