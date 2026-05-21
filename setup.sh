#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"

# ── 1. Locate Python 3.11+ ────────────────────────────────────────────────
# Homebrew lives at /opt/homebrew on Apple Silicon and /usr/local on Intel.
# Try both, preferring 3.13 then 3.12 then 3.11, before falling back to PATH.

PYTHON=""
for BREW_PREFIX in /opt/homebrew /usr/local; do
    for VER in 3.13 3.12 3.11; do
        CANDIDATE="$BREW_PREFIX/bin/python$VER"
        if [[ -x "$CANDIDATE" ]]; then
            PYTHON="$CANDIDATE"
            break 2
        fi
    done
done

# PATH fallback (pyenv, conda, official .pkg installer, etc.)
if [[ -z "$PYTHON" ]]; then
    for VER in 3.13 3.12 3.11; do
        if command -v "python$VER" &>/dev/null; then
            PYTHON="$(command -v "python$VER")"
            break
        fi
    done
fi

if [[ -z "$PYTHON" ]]; then
    echo ""
    echo "Error: Python 3.11 or newer not found."
    echo ""
    echo "Install it with Homebrew:"
    echo "  brew install python@3.13"
    echo ""
    echo "If Homebrew is not installed, get it from https://brew.sh"
    exit 1
fi

echo "==> Using $("$PYTHON" --version) at $PYTHON"

# ── 2. Create or update the virtual environment ───────────────────────────
VENV="$ROOT/.venv"

if [[ -d "$VENV" ]]; then
    echo "==> Updating existing virtual environment..."
else
    echo "==> Creating virtual environment..."
fi

"$PYTHON" -m venv "$VENV"

# ── 3. Install Python packages ────────────────────────────────────────────
echo "==> Upgrading pip..."
"$VENV/bin/pip" install --upgrade pip --quiet

echo "==> Installing dependencies..."
"$VENV/bin/pip" install -r "$ROOT/requirements.txt"

# ── 4. Install Playwright's Chromium (used as SSO login fallback) ─────────
echo "==> Installing Playwright Chromium browser..."
"$VENV/bin/playwright" install chromium

echo ""
echo "Setup complete. Run the app with:"
echo "  python PnPMonitor.py"
