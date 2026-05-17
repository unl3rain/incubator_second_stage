# Project Brief

Read this first if you need to understand the project quickly.

## What this is
A checkers web app positioned as a social + training product, not just a board game.

## Current stack
- Client: React + Vite + Tailwind
- Server: FastAPI
- Storage: PostgreSQL
- Realtime: WebSockets

## Already built
- Server-authoritative checkers rules
- Invite-link multiplayer with WebSockets
- AI coach feedback after moves
- Ranked ladder and city leaderboard
- Daily puzzle and Puzzle Rush
- Replay viewer and post-game review
- Auth foundation, social auth, and session hardening
- Pro/Stripe flow and premium cosmetics
- Analytics instrumentation and growth dashboard
- Friends list, player chat, emoji reactions, mute/report controls
- Position editor MVP with custom setup launch into training

## Still incomplete
- Spectator mode polish
- Opening explorer
- Endgame trainer
- Lesson modules
- PGN/custom notation export
- Clubs/team play
- Tournament/championship flows
- Stronger anti-abuse and optional MFA

## Current priorities
1. Friends/activity feed polish
2. Chat UX + emoji/safety improvements
3. Position editor upgrades and presets
4. Spectator mode v2
5. Opening explorer MVP

## Key files
- Product backlog: [future_ideas.txt](future_ideas.txt)
- Product spec: [Сheckers e38d657cfb65820880dc81c0b04dd76c.md](%D0%A1heckers%20e38d657cfb65820880dc81c0b04dd76c.md)
- Client app: [client/src/App.jsx](client/src/App.jsx)
- Server API: [server/app/api/routes.py](server/app/api/routes.py)
- Game engine/store: [server/app/services/game_store.py](server/app/services/game_store.py)
- Social features: [server/app/services/social.py](server/app/services/social.py)

## Run locally
```bash
docker compose up -d
cd server
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

cd ../client
npm install
npm run dev
```

## Known issue
- The server test suite currently hits an import problem around `get_db` in the retention path, so pytest is not clean yet.

## How this compares to the spec
The project is already beyond the "Great" level from the spec file: multiplayer, AI coach, social layer, leaderboard, Pro/Stripe, replay/review, auth, daily training, and analytics are all present.
