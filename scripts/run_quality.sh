#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-./.venv/bin/python}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Python executable not found: $PYTHON_BIN"
  exit 1
fi

echo "[1/4] pytest + coverage"
if "$PYTHON_BIN" -c "import importlib.util,sys; sys.exit(0 if importlib.util.find_spec('pytest_cov') else 1)"; then
  "$PYTHON_BIN" -m pytest --cov=enigma --cov=cracker --cov-report=term-missing tests/
else
  echo "pytest-cov not installed, running pytest without coverage"
  "$PYTHON_BIN" -m pytest tests/
fi

echo "[2/4] ruff"
if "$PYTHON_BIN" -m ruff --version >/dev/null 2>&1; then
  "$PYTHON_BIN" -m ruff check .
else
  echo "ruff not installed, skipping lint"
fi

echo "[3/4] mypy"
if "$PYTHON_BIN" -m mypy --version >/dev/null 2>&1; then
  "$PYTHON_BIN" -m mypy enigma cracker enigma_cli.py benchmark.py
else
  echo "mypy not installed, skipping type-check"
fi

echo "[4/4] done"
