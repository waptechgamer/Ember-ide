#!/usr/bin/env bash
# Ember IDE — POSIX/macOS/Linux setup script (Phase 0)
# Creates a venv at ./venv, upgrades pip, and installs requirements.txt.
set -euo pipefail

cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 not found on PATH" >&2
  exit 1
fi

if [ ! -d "venv" ]; then
  echo "[setup] Creating virtual environment in ./venv"
  python3 -m venv venv
else
  echo "[setup] Reusing existing ./venv"
fi

# shellcheck disable=SC1091
source venv/bin/activate

echo "[setup] Upgrading pip"
python -m pip install --upgrade pip

echo "[setup] Installing requirements"
pip install -r requirements.txt

echo "[setup] Verifying environment"
python verify_env.py
