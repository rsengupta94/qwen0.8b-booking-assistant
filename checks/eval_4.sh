#!/usr/bin/env bash
# E4 check: verdict writer and merge tests pass; every kept transcript in both pools has a verdict
# file with one verdict per bot turn; judge-versus-human agreement on the calibration sheet is at
# least 75 percent; every verdict file names the same judge model; coherence counts are merged
# into the latest results file. Prints counts only.
set -euo pipefail
cd "$(dirname "$0")/.."

uv run pytest tests/test_judge_merge.py -q
for pool in dev heldout; do
  cards=$(ls evals/transcripts/$pool/*.json | wc -l | tr -d ' ')
  verdicts=$(ls evals/verdicts/$pool/*.json 2>/dev/null | wc -l | tr -d ' ')
  echo "$pool: transcripts=$cards verdict_files=$verdicts"
  [ "$verdicts" -eq "$cards" ] || { echo "FAIL: $pool has transcripts without verdicts"; exit 1; }
done
uv run python - <<'PY'
import json, glob
from pathlib import Path
bad = 0
for v in glob.glob("evals/verdicts/*/*.json"):
    d = json.loads(Path(v).read_text())
    t = json.loads(Path(f"evals/transcripts/{d['pool']}/{d['card_id']}.json").read_text())
    if sorted(x["turn"] for x in d["verdicts"]) != [tr["turn"] for tr in t["turns"]]:
        bad += 1
print(f"verdict files with turn mismatch: {bad}")
assert bad == 0
# Calibration only applies if the same judge scored both pools.
models = {json.loads(Path(v).read_text())["judge_model"] for v in glob.glob("evals/verdicts/*/*.json")}
print(f"judge models across all verdict files: {sorted(models)}")
assert len(models) == 1, "verdicts come from more than one judge model"
PY
uv run python -m evals.judge_merge --floor 0.75
echo "eval_4: PASS"
