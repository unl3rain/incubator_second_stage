#!/usr/bin/env bash
set -euo pipefail

# Simple helper to guide/link/deploy this repo to Railway using the Railway CLI (via npx).
# Interactive steps (login/link) require user action in browser/terminal.
# Usage: ./scripts/railway_setup.sh

echo "Railway setup helper for incubator_second_stage"

# 1) Ensure npx/Node installed. Use npx to avoid global install permission issues.
command -v node >/dev/null 2>&1 || { echo "Node.js not found. Install Node 18+ and retry."; exit 1; }

# 2) Login (opens browser). If already logged in, this will be a no-op.
echo "\n==> Step 1: Login to Railway (this opens your browser). Follow the prompts."
npx @railway/cli login || true

# 3) Initialize project (creates project locally if needed)
echo "\n==> Step 2: Initialize Railway project (creates project if missing)."
npx @railway/cli init --name incubator_second_stage || true

# 4) Link local repo to Railway project (interactive selection)
echo "\n==> Step 3: Link local repository to an existing Railway project (select your fork)."
echo "If the CLI asks, choose the GitHub repo rakhatzhumabekov-afk/incubator_second_stage_deploy or create a new project."
npx @railway/cli link || true

# 5) Add Postgres plugin (recommended via web UI) — attempt via CLI if supported
echo "\n==> NOTE: Add a Postgres plugin in the Railway dashboard for this project (recommended)."
echo "You can do it in the Railway web UI (Project → Plugins → Add PostgreSQL)."

default_add_postgres(){
  npx @railway/cli add --database postgres --service server --json >/dev/null 2>&1
}

read -p "Do you want to attempt to add Postgres automatically via CLI? (y/N): " addpg
if [[ "$addpg" =~ ^[Yy]$ ]]; then
  echo "Attempting to add Postgres plugin (may create a service called server)..."
  default_add_postgres || echo "Automatic plugin add failed — please use the web UI."
fi

# 6) Set environment variables (prompts)
echo "\n==> Step 4: Set environment variables (you can skip any by leaving blank)."
read -p "DATABASE_URL (paste the Railway Postgres connection string or leave blank): " DATABASE_URL
read -p "VITE_API_BASE (frontend should use this to call backend; e.g. https://<backend>.up.railway.app): " VITE_API_BASE
read -p "STRIPE_SECRET (leave blank if not using Stripe): " STRIPE_SECRET
read -p "OAUTH_GOOGLE_CLIENT_ID (leave blank if not using): " OAUTH_GOOGLE_CLIENT_ID
read -p "OAUTH_GOOGLE_CLIENT_SECRET (leave blank if not using): " OAUTH_GOOGLE_CLIENT_SECRET

set_var(){
  local name="$1" value="$2" svc="$3"
  if [[ -n "$value" ]]; then
    echo "Setting $name for service $svc"
    npx @railway/cli variable set "$name=$value" --service "$svc" || echo "Failed to set $name via CLI; please set it in the Railway dashboard."
  fi
}

# By default set server vars to `server`, frontend to `client` service as defined in railway.json
set_var "DATABASE_URL" "$DATABASE_URL" "server"
set_var "STRIPE_SECRET" "$STRIPE_SECRET" "server"
set_var "OAUTH_GOOGLE_CLIENT_ID" "$OAUTH_GOOGLE_CLIENT_ID" "server"
set_var "OAUTH_GOOGLE_CLIENT_SECRET" "$OAUTH_GOOGLE_CLIENT_SECRET" "server"
set_var "VITE_API_BASE" "$VITE_API_BASE" "client"

# 7) Deploy (bring services up)
echo "\n==> Step 5: Deploying (this runs 'npx @railway/cli up' and streams logs)."
echo "If you prefer to deploy from the Railway dashboard, cancel this and use the web UI."
read -p "Proceed with 'npx @railway/cli up'? (y/N): " proceed
if [[ "$proceed" =~ ^[Yy]$ ]]; then
  npx @railway/cli up
else
  echo "Skipping automatic 'railway up'. Use 'npx @railway/cli up' or the Railway dashboard to deploy."
fi

echo "\nDone. If deployment succeeded, note the service URLs in the Railway dashboard and set VITE_API_BASE accordingly."
