from __future__ import annotations

from datetime import datetime


def _create_ranked_game_with_two_players(client):
    create_resp = client.post(
        "/api/games",
        json={"mode": "pvp", "ranked": True, "time_control_minutes": 5},
    )
    assert create_resp.status_code == 200
    game_id = create_resp.json()["game"]["game_id"]

    white_join = client.post(
        f"/api/games/{game_id}/join",
        json={"nickname": "WhiteTest", "city": "Almaty", "preferred_color": "white"},
    )
    assert white_join.status_code == 200

    red_join = client.post(
        f"/api/games/{game_id}/join",
        json={"nickname": "RedTest", "city": "Astana", "preferred_color": "red"},
    )
    assert red_join.status_code == 200

    return game_id, white_join.json(), red_join.json()


def test_cosmetics_equip_enforces_server_owned_inventory(client):
    game_id, white_join, _ = _create_ranked_game_with_two_players(client)
    assert game_id

    profile_id = white_join["profile_id"]

    baseline = client.get(f"/api/profiles/{profile_id}/cosmetics")
    assert baseline.status_code == 200
    baseline_payload = baseline.json()

    assert "classic" in baseline_payload["owned_board_skins"]
    assert "marble" in baseline_payload["owned_piece_skins"]

    equip_owned = client.post(
        f"/api/profiles/{profile_id}/cosmetics/equip",
        json={"kind": "board", "skin_id": "classic"},
    )
    assert equip_owned.status_code == 200
    assert equip_owned.json()["equipped_board_skin"] == "classic"

    equip_unowned = client.post(
        f"/api/profiles/{profile_id}/cosmetics/equip",
        json={"kind": "board", "skin_id": "carbon"},
    )
    assert equip_unowned.status_code == 400
    assert "not owned" in equip_unowned.json()["detail"]


def test_ranked_result_decrements_placement_via_move_endpoint(client, monkeypatch):
    from app.api import routes

    game_id, white_join, red_join = _create_ranked_game_with_two_players(client)

    white_profile_id = white_join["profile_id"]
    red_profile_id = red_join["profile_id"]

    profile_before = client.get(f"/api/profiles/{white_profile_id}")
    assert profile_before.status_code == 200
    assert profile_before.json()["ranked_placement_remaining"] == 10

    # Avoid Postgres-only city upsert path in test environment.
    monkeypatch.setattr(routes, "record_finished_game", lambda winner_city, loser_city: None)

    fake_summary = {
        "game_id": game_id,
        "mode": "pvp",
        "ranked": True,
        "season_key": None,
        "winner": "white",
        "winner_reason": "test",
        "winner_city": "Almaty",
        "loser_city": "Astana",
        "players": {
            "white": {"profile_id": white_profile_id, "nickname": "WhiteTest", "city": "Almaty"},
            "red": {"profile_id": red_profile_id, "nickname": "RedTest", "city": "Astana"},
        },
        "move_history": [],
        "created_at": datetime.utcnow(),
        "finished_at": datetime.utcnow(),
        "time_control_minutes": 5,
    }
    monkeypatch.setattr(routes.store, "consume_finished_summary", lambda _game_id: fake_summary)

    move_resp = client.post(
        f"/api/games/{game_id}/moves",
        json={
            "from": [5, 0],
            "to": [4, 1],
            "player_id": white_join["player_id"],
        },
    )
    assert move_resp.status_code == 200

    profile_after = client.get(f"/api/profiles/{white_profile_id}")
    assert profile_after.status_code == 200
    assert profile_after.json()["ranked_placement_remaining"] == 9


def test_puzzle_rush_uses_db_puzzle_and_validates_solution(client):
    start_resp = client.post("/api/puzzle-rush/start?time_seconds=60&difficulty=easy")
    assert start_resp.status_code == 200

    start_payload = start_resp.json()
    assert start_payload["session_id"]
    assert start_payload["puzzles"]

    puzzle = start_payload["puzzles"][0]
    assert puzzle["puzzle_id"]
    assert puzzle["board"]
    assert puzzle["player_to_move"] in {"white", "red"}

    # Baseline seeded puzzle solution: from [5,0] to [3,2] capturing [4,1]
    submit_resp = client.post(
        "/api/puzzle-rush/submit",
        json={
            "session_id": start_payload["session_id"],
            "puzzle_id": puzzle["puzzle_id"],
            "moves": [{"from": [5, 0], "to": [3, 2], "capture": [4, 1]}],
        },
    )
    assert submit_resp.status_code == 200

    submit_payload = submit_resp.json()
    assert submit_payload["correct"] is True
    assert submit_payload["score_earned"] >= 10
    assert submit_payload["total_score"] >= submit_payload["score_earned"]

    finish_resp = client.post(f"/api/puzzle-rush/finish?session_id={start_payload['session_id']}")
    assert finish_resp.status_code == 200
    finish_payload = finish_resp.json()
    assert finish_payload["status"] == "finished"
    assert finish_payload["final_score"] >= 0


def test_analytics_summary_aggregates_events(client):
    payloads = [
        {"event_name": "app_opened", "profile_id": "p1", "source": "web", "properties": {}},
        {"event_name": "game_created", "profile_id": "p1", "source": "web", "properties": {"mode": "pvp"}},
        {"event_name": "first_move_made", "profile_id": "p1", "source": "web", "properties": {}},
        {"event_name": "game_completed", "profile_id": "p2", "source": "web", "properties": {}},
    ]

    for payload in payloads:
        resp = client.post("/api/analytics/events", json=payload)
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    summary_resp = client.get("/api/analytics/summary?days=14")
    assert summary_resp.status_code == 200

    summary = summary_resp.json()
    assert summary["period_days"] == 14
    assert summary["total_events"] >= 4
    assert summary["unique_profiles"] >= 2
    assert summary["funnel"]["app_opened"] >= 1
    assert summary["funnel"]["game_created"] >= 1
    assert summary["funnel"]["first_move_made"] >= 1
    assert summary["funnel"]["game_completed"] >= 1


def test_social_login_creates_user_and_returns_tokens(client):
    response = client.post(
        "/api/auth/social-login",
        json={
            "provider": "google",
            "provider_user_id": "social-user-1",
            "email": "social1@example.com",
            "username": "socialone",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["access_token"]
    assert payload["refresh_token"]
    assert payload["session_id"]
    assert payload["profile_id"]
    assert payload["email"] == "social1@example.com"


def test_training_undo_rewinds_player_and_ai_turn(client):
    create_resp = client.post(
        "/api/games",
        json={"mode": "vs_ai", "ai_elo": 1200, "ai_color": "red", "ranked": False},
    )
    assert create_resp.status_code == 200
    game_id = create_resp.json()["game"]["game_id"]

    join_resp = client.post(
        f"/api/games/{game_id}/join",
        json={"nickname": "Trainer", "city": "Almaty", "preferred_color": "white"},
    )
    assert join_resp.status_code == 200
    player_id = join_resp.json()["player_id"]

    move_resp = client.post(
        f"/api/games/{game_id}/moves",
        json={"from": [5, 0], "to": [4, 1], "player_id": player_id},
    )
    assert move_resp.status_code == 200
    moved_game = move_resp.json()["game"]
    assert len(moved_game["move_history"]) >= 1

    undo_resp = client.post(
        f"/api/games/{game_id}/undo",
        json={"player_id": player_id},
    )
    assert undo_resp.status_code == 200

    undone_game = undo_resp.json()["game"]
    assert undone_game["turn"] == "white"
    assert undone_game["winner"] is None


def test_google_oauth_start_returns_auth_url(client):
    response = client.get("/api/auth/google/start?oauth_session=test-session-1")
    assert response.status_code == 200
    payload = response.json()
    assert payload["auth_url"].startswith("https://accounts.google.com/o/oauth2/v2/auth")
    assert "state=" in payload["auth_url"]
    assert "nonce=" in payload["auth_url"]


def test_google_oauth_callback_posts_success_message(client, monkeypatch):
    from app.api import routes

    state, _nonce = routes.issue_google_oauth_state("oauth-session-test")

    monkeypatch.setattr(
        routes,
        "exchange_google_code_for_profile",
        lambda code, expected_nonce: {
            "sub": "google-sub-1",
            "email": "google-user@example.com",
            "name": "Google User",
            "email_verified": True,
        },
    )

    response = client.get(f"/api/auth/google/callback?code=fake-code&state={state}")
    assert response.status_code == 200
    text = response.text
    assert "checkers_google_auth_success" in text
    assert "google-user@example.com" in text
    assert "oauth-session-test" in text
