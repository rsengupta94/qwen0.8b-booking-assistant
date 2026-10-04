#!/usr/bin/env bash
# Phase 7 check (static Space, design.md 11a): export tests pass; the export builds into a temp folder and
# finds no held-out-only utterance in any exported file; a plain static file server serves the page, the
# scripts and every data file; the page reads exported files, not the local eval server; the README
# declares a static Space. Prints counts only.
set -euo pipefail
cd "$(dirname "$0")/.."

uv run pytest tests/test_export_space.py -q

OUT="$(mktemp -d)/space"
uv run python -m evals.export_space --out "$OUT"

grep -q '^sdk: static$' "$OUT/README.md" || { echo "FAIL: README does not declare a static Space"; exit 1; }
grep -q 'EVALS_SOURCE' "$OUT/index.html" || { echo "FAIL: page does not point the Evals view at exported files"; exit 1; }
! grep -q '8001' "$OUT/index.html" "$OUT/replay.js" || { echo "FAIL: Space page references the local eval server"; exit 1; }

# Fresh free port; own process group so the trap stops the server, not just the uv wrapper.
PORT="$(uv run python -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1])')"
set -m
uv run python -m http.server "$PORT" --bind 127.0.0.1 --directory "$OUT" >/dev/null 2>&1 &
SERVER_PID=$!
set +m
trap 'kill -- -$SERVER_PID 2>/dev/null || true' EXIT
BASE="http://127.0.0.1:$PORT"
for _ in $(seq 1 40); do curl -sf "$BASE/index.html" >/dev/null 2>&1 && break; sleep 0.25; done

for f in index.html replay.js evals.js data/evals/runs.json data/conversations.json; do
  curl -sf -o /dev/null "$BASE/$f" || { echo "FAIL: $f not served"; exit 1; }
done
uv run python - "$BASE" <<'PY'
import json, sys, urllib.request
from pathlib import Path
base = sys.argv[1]
get = lambda p: json.loads(urllib.request.urlopen(f"{base}/{p}").read())
runs = get("data/evals/runs.json")
assert runs, "no runs exported"
for r in runs:
    run = get(f"data/evals/runs/{r['run_id']}.json")
    assert "turns" not in run["pools"]["heldout"], "held-out turns exported"
convs = get("data/conversations.json")
dev = len(list(Path("evals/transcripts/dev").glob("*.json")))
assert len(convs) == dev, f"{len(convs)} conversations exported, {dev} dev transcripts"
print(f"served: page, scripts, {len(runs)} run(s), {len(convs)} conversations ({sum(len(c['turns']) for c in convs)} turns)")
PY

echo "phase_7: PASS"
