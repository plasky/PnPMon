#!/usr/bin/env python3
"""
PnPMonitor — LIGO P&P page monitor.
Run this file directly: python PnPMonitor.py
"""
import os
import sys
import pathlib

ROOT = pathlib.Path(__file__).parent.resolve()
VENV_PYTHON = ROOT / ".venv" / "bin" / "python3"

# Re-exec into the virtual environment if not already inside it
if sys.executable != str(VENV_PYTHON):
    if not VENV_PYTHON.exists():
        print("Virtual environment not found. Please run ./setup.sh first.")
        sys.exit(1)
    os.execv(str(VENV_PYTHON), [str(VENV_PYTHON)] + sys.argv)

# Add the project root to the path so 'pnpmonitor' package is importable
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pnpmonitor.app import main

if __name__ == "__main__":
    main()
