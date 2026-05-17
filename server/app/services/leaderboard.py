from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.db import SessionLocal
from app.models.leaderboard import CityStat


def _normalize_city(city: str | None) -> str | None:
    if city is None:
        return None

    normalized = city.strip()
    if not normalized:
        return None

    return normalized.title()


def _upsert_city_stat(city: str, wins_delta: int, games_delta: int) -> None:
    statement = pg_insert(CityStat).values(
        city=city,
        wins=wins_delta,
        games=games_delta,
        updated_at=datetime.utcnow(),
    )

    statement = statement.on_conflict_do_update(
        index_elements=[CityStat.city],
        set_={
            "wins": CityStat.wins + wins_delta,
            "games": CityStat.games + games_delta,
            "updated_at": datetime.utcnow(),
        },
    )

    with SessionLocal() as session:
        session.execute(statement)
        session.commit()


def record_finished_game(winner_city: str | None, loser_city: str | None) -> None:
    winner = _normalize_city(winner_city)
    loser = _normalize_city(loser_city)

    if winner is None and loser is None:
        return

    if winner is not None:
        _upsert_city_stat(winner, wins_delta=1, games_delta=1)

    if loser is not None and loser != winner:
        _upsert_city_stat(loser, wins_delta=0, games_delta=1)


def get_top_cities(limit: int = 10) -> list[dict]:
    with SessionLocal() as session:
        rows = session.execute(
            select(CityStat).order_by(CityStat.wins.desc(), CityStat.games.asc(), CityStat.city.asc()).limit(limit)
        ).scalars()

        return [
            {
                "city": row.city,
                "wins": row.wins,
                "games": row.games,
            }
            for row in rows
        ]
