#!/usr/bin/env bash
# E2 check: fidelity gate tests pass, every card in both pools has a transcript or a discard
# record, and the held-out discard rate is at most 10 percent. Prints counts only.
set -euo pipefail
cd "$(dirname "$0")/.."

uv run pytest tests/test_fidelity.py -q
OUT="$(uv run python -m evals.fidelity --pool all)"
echo "$OUT"

for pool in dev heldout; do
  cards=$(ls evals/cards/$pool/*.json | wc -l | tr -d ' ')
  have=$(ls evals/transcripts/$pool/*.json 2>/dev/null | wc -l | tr -d ' ')
  disc=$(for f in evals/transcripts/discarded/*.json; do [ -f "$f" ] && python3 -c "import json,sys;print(json.load(open('$f'))['pool'])"; done 2>/dev/null | grep -c "^$pool$" || true)
  echo "$pool: cards=$cards kept=$have discarded=$disc"
  [ "$((have + disc))" -ge "$cards" ] || { echo "FAIL: $pool has cards without a transcript or discard record"; exit 1; }
done

rate=$(echo "$OUT" | awk -F'discard_rate=' '/^heldout:/{print $2}' | tr -d '%')
awk -v r="$rate" 'BEGIN{exit !(r <= 10.0)}' || { echo "FAIL: heldout discard rate $rate% > 10%"; exit 1; }
echo "eval_2: PASS"
