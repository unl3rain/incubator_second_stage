from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.core.db import SessionLocal
from app.domain.checkers import create_initial_board, detect_winner
from app.models.completed_game import CompletedGame


def save_completed_game(summary: dict) -> None:
    with SessionLocal() as session:
        existing = session.execute(
            select(CompletedGame).where(CompletedGame.game_id == summary["game_id"])
        ).scalar_one_or_none()
        if existing is not None:
            return

        white = summary["players"].get("white") or {}
        red = summary["players"].get("red") or {}

        record = CompletedGame(
            game_id=summary["game_id"],
            mode=summary.get("mode", "pvp"),
            ranked=bool(summary.get("ranked", False)),
            season_key=summary.get("season_key"),
            winner=summary.get("winner"),
            winner_reason=summary.get("winner_reason"),
            ai_elo=summary.get("ai_elo"),
            ai_color=summary.get("ai_color"),
            time_control_minutes=summary.get("time_control_minutes"),
            white_nickname=white.get("nickname"),
            white_city=white.get("city"),
            red_nickname=red.get("nickname"),
            red_city=red.get("city"),
            total_moves=len(summary.get("move_history", [])),
            move_history=summary.get("move_history", []),
            created_at=summary.get("created_at", datetime.utcnow()),
            finished_at=summary.get("finished_at", datetime.utcnow()),
        )
        session.add(record)
        session.commit()


def get_recent_matches(limit: int = 10) -> list[dict]:
    with SessionLocal() as session:
        rows = session.execute(
            select(CompletedGame).order_by(CompletedGame.finished_at.desc()).limit(limit)
        ).scalars()

        return [
            {
                "id": row.id,
                "game_id": row.game_id,
                "mode": row.mode,
                "ranked": bool(row.ranked),
                "season_key": row.season_key,
                "winner": row.winner,
                "winner_reason": row.winner_reason,
                "ai_elo": row.ai_elo,
                "ai_color": row.ai_color,
                "time_control_minutes": row.time_control_minutes,
                "total_moves": row.total_moves,
                "created_at": row.created_at,
                "finished_at": row.finished_at,
                "players": {
                    "white": {
                        "nickname": row.white_nickname,
                        "city": row.white_city,
                    },
                    "red": {
                        "nickname": row.red_nickname,
                        "city": row.red_city,
                    },
                },
            }
            for row in rows
        ]


def get_match_replay(match_id: int) -> dict | None:
    with SessionLocal() as session:
        row = session.get(CompletedGame, match_id)
        if row is None:
            return None

        states = [
            {
                "move_index": 0,
                "board": create_initial_board(),
                "turn": "white",
                "winner": None,
                "last_move": None,
            }
        ]

        board = create_initial_board()
        history = row.move_history or []

        for index, move in enumerate(history, start=1):
            public_move = {
                "player": move["player"],
                "by_ai": bool(move.get("by_ai")),
                "from": move["from"],
                "to": move["to"],
                "capture": move.get("capture"),
            }
            board = _apply_public_move(board, public_move)
            next_turn = history[index]["player"] if index < len(history) else _opponent(move["player"])
            winner = row.winner if index == len(history) else detect_winner(board, next_turn)
            states.append(
                {
                    "move_index": index,
                    "board": board,
                    "turn": next_turn,
                    "winner": winner,
                    "last_move": public_move,
                }
            )

        return {
            "match": {
                "id": row.id,
                "game_id": row.game_id,
                "mode": row.mode,
                "ranked": bool(row.ranked),
                "season_key": row.season_key,
                "winner": row.winner,
                "winner_reason": row.winner_reason,
                "ai_elo": row.ai_elo,
                "ai_color": row.ai_color,
                "time_control_minutes": row.time_control_minutes,
                "total_moves": row.total_moves,
                "created_at": row.created_at,
                "finished_at": row.finished_at,
                "players": {
                    "white": {
                        "nickname": row.white_nickname,
                        "city": row.white_city,
                    },
                    "red": {
                        "nickname": row.red_nickname,
                        "city": row.red_city,
                    },
                },
            },
            "states": states,
        }


def _apply_public_move(board: list[list[dict | None]], move: dict) -> list[list[dict | None]]:
    from app.domain.checkers import apply_move

    return apply_move(
        board,
        {
            "from_": (move["from"][0], move["from"][1]),
            "to": (move["to"][0], move["to"][1]),
            "capture": (move["capture"][0], move["capture"][1]) if move.get("capture") else None,
        },
    )


def _opponent(player: str) -> str:
    return "red" if player == "white" else "white"