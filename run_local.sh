#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$ROOT/logs"

echo "Starting Postgres via docker compose..."
docker compose up -d

echo "Setting up backend virtualenv and dependencies..."
cd "$ROOT/server"
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
. .venv/bin/activate
pip install -r requirements.txt

# copy example env if missing
if [ ! -f .env ]; then
  cp .env.example .env
fi

echo "Starting backend (uvicorn) in background, logs -> logs/backend.log"
nohup .venv/bin/python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 >"$ROOT/logs/backend.log" 2>&1 &
echo $! >"$ROOT/logs/backend.pid"

sleep 2

echo "Setting up frontend and env..."
cd "$ROOT/client"
npm install
if [ ! -f .env ]; then
  cp .env.example .env
fi
# ensure frontend points to local backend
if grep -q "VITE_API_BASE=" .env; then
  sed -i "s#VITE_API_BASE=.*#VITE_API_BASE=http://localhost:8000/api#" .env
else
  echo "VITE_API_BASE=http://localhost:8000/api" >> .env
fi

echo "Starting frontend (Vite) in background, logs -> logs/frontend.log"
# start dev server in background
nohup npm run dev >"$ROOT/logs/frontend.log" 2>&1 &
echo $! >"$ROOT/logs/frontend.pid"

sleep 1

echo "All services started."
echo "Frontend: http://localhost:5173"
echo "Backend: http://localhost:8000/api/health"
echo "Tail logs with: tail -f $ROOT/logs/backend.log $ROOT/logs/frontend.log"
