#!/usr/bin/env bash
# Runs every phase check in numeric order. Stops on the first failure.
set -euo pipefail
cd "$(dirname "$0")/.."

for f in $(ls checks/phase_*.sh | sort -t_ -k2 -n) $(ls checks/eval_*.sh 2>/dev/null | sort -t_ -k2 -n); do
  echo "=== $f ==="
  bash "$f"
done

echo "all: PASS"
