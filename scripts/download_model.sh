#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p models
URL="https://huggingface.co/ggml-org/Qwen3.5-0.8B-GGUF/resolve/main/Qwen3.5-0.8B-Q8_0.gguf"
OUT="models/Qwen3.5-0.8B-Q8_0.gguf"
EXPECTED="37ae482d336108d23516fa35e8e0c4126688d81018b87178a18d752a1357814f"
[ -f "$OUT" ] || curl -L --progress-bar -o "$OUT" "$URL"
ACTUAL=$(shasum -a 256 "$OUT" | cut -d' ' -f1)
[ "$ACTUAL" = "$EXPECTED" ] && echo "OK: model verified" || { echo "FAIL: sha256 mismatch"; exit 1; }
