#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

./scripts/run_quality.sh
./.venv/bin/python benchmark.py
./.venv/bin/python scripts/profile_full_cracker.py

echo "Release checks completed."
