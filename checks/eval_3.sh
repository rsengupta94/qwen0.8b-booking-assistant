#!/usr/bin/env bash
# E3 check: path table, scorer and guard tests pass; the held-out guard passes; replaying the dev
# transcripts against the current product agrees with the generation run on state per turn; the
# scorer runs over both pools and writes a results file with all three outcome classes present or
# explicitly zero. Prints aggregates only.
set -euo pipefail
cd "$(dirname "$0")/.."

uv run pytest tests/test_path_table.py tests/test_score.py tests/test_guard.py -q
uv run python -m evals.guard

echo "--- replay dev ---"
uv run python -m evals.replay --pool dev | tail -3

echo "--- score generation, both pools ---"
OUT="$(uv run python -m evals.score --pool all --source generation)"
echo "$OUT"
RUN_ID="$(echo "$OUT" | sed -n 's/^run_id=\([^ ]*\).*/\1/p')"
uv run python - "$RUN_ID" <<'PY'
import json, sys
r = json.load(open(f"evals/results/{sys.argv[1]}.json"))
agg = r["aggregate"]["by_prompt"]
classes = {c for v in agg.values() for c in v}
for c in ("pass", "rescued", "silent_wrong"):
    n = sum(v.get(c, 0) for v in agg.values())
    print(f"{c}: {n}")
assert r["n_sessions"] == 81, r["n_sessions"]
assert {"pass", "rescued", "silent_wrong"} <= classes, classes
PY
echo "eval_3: PASS"
