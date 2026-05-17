#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request


def request_json(url: str, method: str = "GET", payload: dict | None = None) -> dict:
    body = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"HTTP {exc.code} for {url}: {details}") from exc


def create_test_profile(api_base: str, nickname: str, city: str) -> str:
    game_payload = {"mode": "pvp", "ranked": False, "time_control_minutes": 5}
    game = request_json(f"{api_base}/games", method="POST", payload=game_payload)["game"]
    joined = request_json(
        f"{api_base}/games/{game['game_id']}/join",
        method="POST",
        payload={"nickname": nickname, "city": city, "preferred_color": "white"},
    )
    return joined["profile_id"]


def run_stripe_trigger(profile_id: str, plan: str) -> None:
    cmd = [
        "stripe",
        "trigger",
        "checkout.session.completed",
        "--add",
        f"checkout_session:client_reference_id={profile_id}",
        "--add",
        f"checkout_session:metadata[profile_id]={profile_id}",
        "--add",
        f"checkout_session:metadata[plan]={plan}",
    ]

    print("Running:", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"stripe trigger failed:\n{result.stdout}\n{result.stderr}")

    print(result.stdout.strip())


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay Stripe checkout.session.completed and verify Pro entitlement activation")
    parser.add_argument("--api-base", default="http://localhost:8000/api")
    parser.add_argument("--plan", choices=["pro_monthly", "pro_yearly"], default="pro_monthly")
    parser.add_argument("--profile-id", default=None)
    parser.add_argument("--nickname", default="StripeReplay")
    parser.add_argument("--city", default="Almaty")
    parser.add_argument("--wait-seconds", type=int, default=15)
    args = parser.parse_args()

    profile_id = args.profile_id or create_test_profile(args.api_base, args.nickname, args.city)
    print(f"Using profile_id={profile_id}")

    before = request_json(f"{args.api_base}/profiles/{profile_id}/cosmetics")
    print(f"Before: pro_active={before.get('pro_active')} plan={before.get('pro_plan')}")

    run_stripe_trigger(profile_id, args.plan)

    deadline = time.time() + args.wait_seconds
    while time.time() < deadline:
        current = request_json(f"{args.api_base}/profiles/{profile_id}/cosmetics")
        if current.get("pro_active"):
            print(f"PASS: Pro activated for {profile_id} with plan={current.get('pro_plan')}")
            return 0
        time.sleep(1)

    final = request_json(f"{args.api_base}/profiles/{profile_id}/cosmetics")
    print(f"FAIL: entitlement not activated within timeout. Final state={final}")
    return 1


if __name__ == "__main__":
    sys.exit(main())