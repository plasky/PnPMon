#!/usr/bin/env bash
set -e

PYTHON=/opt/homebrew/bin/python3.13
ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "==> Creating virtual environment with Python 3.13..."
"$PYTHON" -m venv "$ROOT/.venv"

echo "==> Installing dependencies..."
"$ROOT/.venv/bin/pip" install --upgrade pip --quiet
"$ROOT/.venv/bin/pip" install -r "$ROOT/requirements.txt" --quiet

echo "==> Installing Playwright Chromium browser..."
"$ROOT/.venv/bin/playwright" install chromium

echo ""
echo "Setup complete. Run the app with:"
echo "  python PnPMonitor.py"
