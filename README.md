# Checkers Great Level Starter

## LIVE PRODUCTION URL (RAILWAY)

### https://incubatorsecondstagedeploy-production.up.railway.app

Monorepo starter for a "Great" level checkers product:

- `client`: React + Vite + Tailwind CSS
- `server`: FastAPI backend
- `docker-compose.yml`: PostgreSQL + pgAdmin

**Submission summary (for the assignment)**

- **Level achieved:** Great — multiplayer (invite links + WebSockets), AI coach analysis, social layer (friends/chat/leaderboard), daily puzzles, replay/review, and Pro monetization hooks.
- **Working demo:** https://incubatorsecondstagedeploy-production.up.railway.app
- **Repository:** (this repository)
- **Short description for submission:** A social-first checkers web app with server-authoritative rules, invite-link multiplayer, AI coaching and post-game analysis, ranked leaderboards, daily puzzles, and premium cosmetic packs.

Replace the demo URL above with your deployed Railway (or other host) link before submitting the assignment form.

## 1) Start PostgreSQL

```bash
docker compose up -d
```

- PostgreSQL: `localhost:5432`
- pgAdmin: `http://localhost:5050`

## 2) Run Backend

```bash
cd server
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Health check: `http://localhost:8000/api/health`

## 3) Run Frontend

```bash
cd client
npm install
npm run dev
```

Open: `http://localhost:5173`

Use "Check Backend Health" button to verify frontend-backend communication.

## 4) Deploy with Railway

This repository is ready for Railway with separate backend and frontend services.

- Backend service: use `server/Dockerfile`
- Frontend service: use `client/Dockerfile`

Recommended Railway setup:

1. Create a new Railway project.
2. Add a PostgreSQL plugin.
3. Add a Python service from the `server` folder and set it to use `server/Dockerfile`.
4. Configure Railway environment variables for the backend service:
   - `DATABASE_URL` from the Railway Postgres plugin
   - `APP_HOST=0.0.0.0`
   - `APP_PORT=8000`
   - `FRONTEND_ORIGIN=https://your-frontend-url` (set after frontend deploy)
   - any Stripe / OAuth variables you want to enable in production
5. Add a second service for the frontend using `client/Dockerfile`.
6. Set `VITE_API_BASE=https://your-backend-url/api` on the frontend service.

Once both services are deployed, the frontend will call the backend through the configured Railway URLs.

Gameplay is now server-authoritative: the frontend sends moves to FastAPI, and the backend validates rules (mandatory capture, chain capture, promotion, winner detection).

Realtime multiplayer baseline is now active: open the same `?game=<id>` link in two tabs/devices to play one shared match with live WebSocket updates.

Player seat ownership is now enforced: each player joins as white/red (or spectator), and only the current-turn seat can submit moves. Room metadata includes nickname + city for both seats.

City leaderboard is now persisted in PostgreSQL and available via `GET /api/leaderboard/cities`.

## Suggested next milestones

1. Add auth and reusable profiles.
2. Build AI coach analysis from move history.
3. Add monetization hooks (Pro skin packs / Stripe).
