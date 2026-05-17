# Server (FastAPI)

## Setup

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy environment variables:

```bash
cp .env.example .env
```

4. Run development server:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Coach uses advanced engine analysis via `py-draughts` when installed (with heuristic fallback).
Configure with environment variables:

- `COACH_ENGINE_PROVIDER` (`py-draughts` or `heuristic`)
- `COACH_ENGINE_DEPTH` (default `6`)
- `COACH_ENGINE_TIME_LIMIT` (default `0.25` seconds)

## Endpoints

- `GET /` basic server message
- `GET /api/health` API health check
- `POST /api/games` create a new game session
- `GET /api/games/{game_id}` fetch current game state
- `POST /api/games/{game_id}/join` join seat with profile (`nickname`, `city`, optional `preferred_color`)
- `POST /api/games/{game_id}/moves` submit a move (`{"from": [r, c], "to": [r, c], "player_id": "..."}`), response includes coach feedback (`rating`, reasons, suggested move)
- `WS /api/ws/games/{game_id}` realtime room updates (`game_snapshot`, `game_updated`)
- `GET /api/leaderboard/cities?limit=10` top cities by wins
- `GET /api/leaderboard/ranked?limit=20` seasonal ranked ladder (ELO)
- `GET /api/engine/status` advanced engine diagnostics (provider, availability, reason)
- `POST /api/quick-play/enqueue` join quick play ranked queue (1/3/5/10 min presets)
- `GET /api/quick-play/status/{ticket_id}` poll quick play status
- `DELETE /api/quick-play/status/{ticket_id}` cancel waiting quick play ticket
- `POST /api/billing/checkout` create Stripe (or mock) checkout URL for Pro
- `POST /api/billing/webhook` Stripe webhook endpoint (signature-verified when configured)
- `GET /api/profiles/{profile_id}/cosmetics` fetch owned/equipped cosmetics (server source of truth)
- `POST /api/profiles/{profile_id}/cosmetics/equip` equip owned board/piece skin
- `GET /api/puzzles/daily?profile_id=<id>` daily puzzle with streak and attribution metadata
- `POST /api/puzzles/daily/submit` submit daily puzzle move
- `POST /api/puzzles/import` import external licensed puzzle bank JSON

Ranked inactivity policy:

- No ELO decay is applied for inactivity.
- Players are hidden from ranked leaderboard after 30 days without a ranked game.
- Ladder rows include an inactivity warning before hiding.

Coach fairness policy:

- **PvP matches**: Coach feedback is disabled during active play to ensure fair competition.
- **Ranked matches**: Coach feedback is disabled during active play for competitive integrity.
- **Training mode**: Coach feedback is enabled on every move to support learning.
- **Post-game analysis**: Coach feedback is available after game completion to review performance.
- Endpoints: Coach analysis (rating, reasons, suggested moves) appears in move responses only when conditions above allow it.

## Billing configuration

By default billing runs in mock mode for local development. To enable real Stripe checkout,
configure these environment variables in `.env`:

- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET`
- `STRIPE_SUCCESS_URL`
- `STRIPE_CANCEL_URL`
- `STRIPE_PRICE_PRO_MONTHLY`
- `STRIPE_PRICE_PRO_YEARLY`
- `BILLING_MOCK_MODE=false`

### Stripe webhook replay smoke test

To verify real webhook-driven entitlement activation for a test profile:

1. Run backend locally and configure real Stripe keys + webhook secret.
2. In another terminal, run Stripe forwarding to your local webhook endpoint.
3. Run:

```bash
python scripts/stripe_webhook_replay_test.py --api-base http://localhost:8000/api --plan pro_monthly
```

The script creates (or uses) a profile, triggers `checkout.session.completed` via Stripe CLI, and checks `/api/profiles/{profile_id}/cosmetics` until `pro_active=true`.

### API integration tests

```bash
pytest -q
```

## Puzzle Import Pipeline

You can import a licensed puzzle dataset into the puzzle bank using either API or CLI.

### JSON payload format

```json
{
	"source": "licensed-dataset-name",
	"source_url": "https://example.com/license-or-source",
	"attribution": "Use with permission. Source: Example Dataset",
	"dry_run": false,
	"puzzles": [
		{
			"code": "optional-unique-code",
			"title": "Fork Tactic",
			"hint": "White to move and win material.",
			"difficulty": "medium",
			"turn": "white",
			"board": [[null, null, null, null, null, null, null, null], [null, null, null, null, null, null, null, null], [null, null, null, {"player": "white", "king": false}, null, null, null, null], [null, null, null, null, {"player": "red", "king": false}, null, null, null], [null, null, null, null, null, null, null, null], [null, null, null, null, null, null, null, null], [null, null, null, null, null, null, null, null], [null, null, null, null, null, null, null, null]],
			"solution": {
				"from": [2, 3],
				"to": [4, 5],
				"capture": [3, 4]
			}
		}
	]
}
```

### CLI import

```bash
python scripts/import_puzzles.py --file /absolute/path/to/puzzles.json
python scripts/import_puzzles.py --file /absolute/path/to/puzzles.json --dry-run
```

## Next planned modules

- Auth and profile service
- AI coach analysis pipeline
