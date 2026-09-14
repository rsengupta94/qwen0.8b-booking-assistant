#!/usr/bin/env bash
# Phase 1 check: pytest walks both workflows end to end with stubbed NLU
# and asserts a booking record exists.
set -euo pipefail
cd "$(dirname "$0")/.."

uv run pytest tests -q

echo "phase_1: PASS"
