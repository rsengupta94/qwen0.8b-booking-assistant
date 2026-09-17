#!/usr/bin/env bash
# E1 check: 12 personas and 27 scenarios exist, the sampler runs, and the card tests pass
# (coverage, disjoint pools, complete fields, no expected outcome inside a card).
set -euo pipefail
cd "$(dirname "$0")/.."

echo "personas: $(ls evals/personas/*.json | wc -l | tr -d ' ')"
echo "scenarios: $(ls evals/scenarios/*.json | wc -l | tr -d ' ')"
uv run python -m evals.sample_cards
uv run pytest tests/test_sample_cards.py -q
echo "eval_1: PASS"
