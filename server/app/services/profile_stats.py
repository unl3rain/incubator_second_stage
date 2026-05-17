from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.completed_game import CompletedGame
from app.models.auth_user import AuthUser
from app.models.profile_match import ProfileMatch
from app.models.player_profile import PlayerProfile
from app.services.entitlements import ensure_profile_inventory


RANKED_INACTIVITY_HIDE_DAYS = 30
RANKED_INACTIVITY_WARNING_DAYS = 21


def _normalize_nickname(value: str | None) -> str:
    normalized = (value or "").strip()
    return normalized or "Guest"


def _normalize_city(value: str | None) -> str | None:
    normalized = (value or "").strip()
    return normalized.title() if normalized else None


def current_season_key() -> str:
    now = datetime.utcnow()
    half = 1 if now.month <= 6 else 2
    return f"{now.year}-S{half}"


def _ensure_current_season(profile: PlayerProfile) -> None:
    season = current_season_key()
    if profile.season_key == season:
        return

    profile.season_key = season
    profile.elo_rating = 1200
    profile.ranked_games = 0
    profile.ranked_wins = 0
    profile.ranked_losses = 0
    profile.ranked_placement_remaining = 10
    profile.last_ranked_at = None


def get_or_create_profile(profile_id: str | None, nickname: str | None, city: str | None) -> dict:
    normalized_nickname = _normalize_nickname(nickname)
    normalized_city = _normalize_city(city)

    with SessionLocal() as session:
        profile = session.get(PlayerProfile, profile_id) if profile_id else None
        if profile is None:
            profile = PlayerProfile(
                profile_id=(profile_id or uuid4().hex[:16]),
                nickname=normalized_nickname,
                city=normalized_city,
                season_key=current_season_key(),
            )
            session.add(profile)
        else:
            _ensure_current_season(profile)
            profile.nickname = normalized_nickname
            profile.city = normalized_city

        ensure_profile_inventory(profile)

        session.commit()
        session.refresh(profile)
        return _serialize_profile(profile)


def get_profile(profile_id: str) -> dict | None:
    with SessionLocal() as session:
        profile = session.get(PlayerProfile, profile_id)
        if profile is None:
            return None

        auth_user = session.execute(
            select(AuthUser).where(AuthUser.profile_id == profile_id)
        ).scalar_one_or_none()

        _ensure_current_season(profile)
        ensure_profile_inventory(profile)
        session.commit()

        return _serialize_profile(
            profile,
            linked_provider=auth_user.social_provider if auth_user else None,
            linked_provider_user_id=auth_user.social_provider_user_id if auth_user else None,
            linked_provider_display_name=auth_user.social_display_name if auth_user else None,
        )


def record_profile_result(profile_id: str, did_win: bool, mode: str, ranked: bool = False) -> None:
    with SessionLocal() as session:
        profile = session.get(PlayerProfile, profile_id)
        if profile is None:
            return

        _ensure_current_season(profile)

        profile.games += 1
        if did_win:
            profile.wins += 1
        else:
            profile.losses += 1

        if mode == "vs_ai":
            profile.ai_games += 1
        else:
            profile.pvp_games += 1

        if ranked:
            profile.ranked_games += 1
            profile.last_ranked_at = datetime.utcnow()
            if profile.ranked_placement_remaining > 0:
                profile.ranked_placement_remaining -= 1
            if did_win:
                profile.ranked_wins += 1
            else:
                profile.ranked_losses += 1

        session.commit()


def _expected_score(player_rating: int, opponent_rating: int) -> float:
    return 1.0 / (1 + 10 ** ((opponent_rating - player_rating) / 400))


def record_ranked_elo_result(white_profile_id: str, red_profile_id: str, winner: str) -> dict | None:
    with SessionLocal() as session:
        white = session.get(PlayerProfile, white_profile_id)
        red = session.get(PlayerProfile, red_profile_id)
        if white is None or red is None:
            return None

        _ensure_current_season(white)
        _ensure_current_season(red)

        white_before = white.elo_rating
        red_before = red.elo_rating

        white_score = 1.0 if winner == "white" else 0.0
        red_score = 1.0 if winner == "red" else 0.0

        k_factor = 32
        white_change = round(k_factor * (white_score - _expected_score(white_before, red_before)))
        red_change = round(k_factor * (red_score - _expected_score(red_before, white_before)))

        white.elo_rating = max(100, white_before + white_change)
        red.elo_rating = max(100, red_before + red_change)

        session.commit()

        return {
            "white_before": white_before,
            "white_after": white.elo_rating,
            "red_before": red_before,
            "red_after": red.elo_rating,
            "season_key": white.season_key,
        }


def link_profile_to_completed_match(summary: dict) -> None:
    with SessionLocal() as session:
        match = session.execute(
            select(CompletedGame).where(CompletedGame.game_id == summary["game_id"])
        ).scalar_one_or_none()
        if match is None:
            return

        winner = summary.get("winner")
        for color in ("white", "red"):
            profile_id = summary.get("players", {}).get(color, {}).get("profile_id")
            if not profile_id:
                continue

            existing = session.execute(
                select(ProfileMatch).where(
                    ProfileMatch.profile_id == profile_id,
                    ProfileMatch.completed_game_id == match.id,
                )
            ).scalar_one_or_none()
            if existing is not None:
                continue

            session.add(
                ProfileMatch(
                    profile_id=profile_id,
                    completed_game_id=match.id,
                    role_color=color,
                    did_win=winner == color,
                )
            )

        session.commit()


def get_profile_matches(profile_id: str, limit: int = 10) -> list[dict]:
    with SessionLocal() as session:
        rows = session.execute(
            select(ProfileMatch, CompletedGame)
            .join(CompletedGame, CompletedGame.id == ProfileMatch.completed_game_id)
            .where(ProfileMatch.profile_id == profile_id)
            .order_by(CompletedGame.finished_at.desc())
            .limit(limit)
        ).all()

        return [
            {
                "id": game.id,
                "game_id": game.game_id,
                "mode": game.mode,
                "ranked": bool(game.ranked),
                "season_key": game.season_key,
                "winner": game.winner,
                "winner_reason": game.winner_reason,
                "ai_elo": game.ai_elo,
                "ai_color": game.ai_color,
                "time_control_minutes": game.time_control_minutes,
                "total_moves": game.total_moves,
                "created_at": game.created_at,
                "finished_at": game.finished_at,
                "players": {
                    "white": {
                        "nickname": game.white_nickname,
                        "city": game.white_city,
                    },
                    "red": {
                        "nickname": game.red_nickname,
                        "city": game.red_city,
                    },
                },
                "role_color": rel.role_color,
                "did_win": rel.did_win,
            }
            for rel, game in rows
        ]


def get_ranked_leaderboard(limit: int = 20) -> dict:
    with SessionLocal() as session:
        season = current_season_key()
        rows = session.execute(
            select(PlayerProfile)
            .where(PlayerProfile.season_key == season)
            .where(PlayerProfile.ranked_games > 0)
            .order_by(PlayerProfile.elo_rating.desc(), PlayerProfile.ranked_wins.desc())
        ).scalars()

        now = datetime.utcnow()
        players: list[dict] = []
        for row in rows:
            if row.last_ranked_at is None:
                inactivity_days = RANKED_INACTIVITY_HIDE_DAYS
            else:
                inactivity_days = max(0, (now - row.last_ranked_at).days)

            if inactivity_days > RANKED_INACTIVITY_HIDE_DAYS:
                continue

            players.append(
                {
                    "profile_id": row.profile_id,
                    "nickname": row.nickname,
                    "city": row.city,
                    "elo_rating": row.elo_rating,
                    "ranked_games": row.ranked_games,
                    "ranked_wins": row.ranked_wins,
                    "ranked_losses": row.ranked_losses,
                    "ranked_placement_remaining": row.ranked_placement_remaining,
                    "season_key": row.season_key,
                    "inactivity_days": inactivity_days,
                    "days_until_hidden": max(0, RANKED_INACTIVITY_HIDE_DAYS - inactivity_days),
                    "activity_status": "inactive-soon" if inactivity_days >= RANKED_INACTIVITY_WARNING_DAYS else "active",
                }
            )
            if len(players) >= limit:
                break

        return {
            "season_key": season,
            "players": players,
        }


def _serialize_profile(
    profile: PlayerProfile,
    linked_provider: str | None = None,
    linked_provider_user_id: str | None = None,
    linked_provider_display_name: str | None = None,
) -> dict:
    _ensure_current_season(profile)
    ensure_profile_inventory(profile)
    games = profile.games or 0
    win_rate = round((profile.wins / games) * 100, 1) if games else 0.0

    return {
        "profile_id": profile.profile_id,
        "nickname": profile.nickname,
        "city": profile.city,
        "games": profile.games,
        "wins": profile.wins,
        "losses": profile.losses,
        "pvp_games": profile.pvp_games,
        "ai_games": profile.ai_games,
        "elo_rating": profile.elo_rating,
        "ranked_games": profile.ranked_games,
        "ranked_wins": profile.ranked_wins,
        "ranked_losses": profile.ranked_losses,
        "ranked_placement_remaining": profile.ranked_placement_remaining,
        "last_ranked_at": profile.last_ranked_at,
        "season_key": profile.season_key,
        "pro_active": profile.pro_active,
        "pro_plan": profile.pro_plan,
        "pro_expires_at": profile.pro_expires_at,
        "linked_provider": linked_provider,
        "linked_provider_user_id": linked_provider_user_id,
        "linked_provider_display_name": linked_provider_display_name,
        "owned_board_skins": profile.owned_board_skins,
        "owned_piece_skins": profile.owned_piece_skins,
        "equipped_board_skin": profile.equipped_board_skin,
        "equipped_piece_skin": profile.equipped_piece_skin,
        "win_rate": win_rate,
        "created_at": profile.created_at,
        "updated_at": profile.updated_at,
    }