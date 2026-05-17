#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "Running quick checks: frontend build and backend pytest (cosmetics test)"

# Frontend build
cd "$ROOT/client"
echo "Installing frontend deps (if needed) and building..."
npm install
npm run build

echo "Running backend tests (cosmetics-related). Ensure PYTHONPATH is set to 'server'."
cd "$ROOT"
if [ ! -d "server/.venv" ]; then
  echo "Setting up backend virtualenv..."
  cd server
  python3 -m venv .venv
  . .venv/bin/activate
  pip install -r requirements.txt
  cd "$ROOT"
fi

# run the targeted pytest
PYTHONPATH=server server/.venv/bin/python -m pytest server/tests/test_api_integration.py -q -k cosmetics_equip

echo "Checks completed."
