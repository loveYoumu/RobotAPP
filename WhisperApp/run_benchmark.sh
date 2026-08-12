#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODEL="${1:-small}"
DEVICE="${2:-auto}"
exec "${PYTHON:-python3}" "$ROOT/run_whisper_benchmark.py" \
  --model "$MODEL" \
  --device "$DEVICE" \
  --manifest "$ROOT/synthetic_zh_robot_commands/manifest.jsonl" \
  --model-dir "$ROOT/models" \
  --output-dir "$ROOT/results/${MODEL}_${DEVICE}"
