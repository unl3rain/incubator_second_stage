"""Puzzle Rush / Survival mode service - timed tactical puzzle challenges."""

from datetime import datetime, timezone
from random import choice
from threading import RLock
from uuid import uuid4

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.puzzle_bank_entry import PuzzleBankEntry

# In-memory sessions (production would use Redis)
_SESSIONS: dict[str, dict] = {}
_SESSIONS_LOCK = RLock()


def _normalize_move(move: dict) -> dict | None:
    if not isinstance(move, dict):
        return None

    from_pos = move.get("from") if move.get("from") is not None else move.get("from_pos")
    to_pos = move.get("to")
    capture = move.get("capture")

    if not _is_square(from_pos) or not _is_square(to_pos):
        return None
    if capture is not None and not _is_square(capture):
        return None

    return {
        "from": from_pos,
        "to": to_pos,
        "capture": capture,
    }


def _is_square(value: object) -> bool:
    return isinstance(value, list) and len(value) == 2 and all(isinstance(v, int) and 0 <= v < 8 for v in value)


def _serialize_puzzle(entry: PuzzleBankEntry) -> dict:
    return {
        "puzzle_id": entry.code,
        "difficulty": entry.difficulty,
        "title": entry.title,
        "hint": entry.hint,
        "board": entry.board,
        "player_to_move": entry.turn,
        "source": entry.source,
    }


def _seed_if_empty() -> None:
    with SessionLocal() as session:
        existing = session.execute(select(PuzzleBankEntry).where(PuzzleBankEntry.is_active.is_(True))).scalars().first()
        if existing is not None:
            return

        baseline = PuzzleBankEntry(
            code="rush-generated-0001",
            title="Rush Starter",
            hint="Find the immediate tactical strike.",
            difficulty="easy",
            source="internal-generated",
            source_url=None,
            attribution="Auto-seeded for puzzle rush.",
            board=[
                [None, None, None, None, None, None, None, None],
                [None, None, None, None, None, None, None, None],
                [None, None, None, None, None, None, None, None],
                [None, None, None, None, None, None, None, None],
                [None, {"player": "red", "king": False}, None, None, None, None, None, None],
                [{"player": "white", "king": False}, None, None, None, None, None, None, None],
                [None, None, None, None, None, None, None, None],
                [None, None, None, None, None, None, None, None],
            ],
            turn="white",
            solution={"from": [5, 0], "to": [3, 2], "capture": [4, 1]},
            is_active=True,
        )
        session.add(baseline)
        session.commit()


def _fetch_next_puzzle(difficulty: str | None, used_codes: set[str]) -> tuple[dict, dict] | tuple[None, None]:
    _seed_if_empty()
    with SessionLocal() as session:
        query = select(PuzzleBankEntry).where(PuzzleBankEntry.is_active.is_(True))
        if difficulty:
            query = query.where(PuzzleBankEntry.difficulty == difficulty)

        rows = session.execute(query.order_by(PuzzleBankEntry.id.asc())).scalars().all()
        if not rows:
            return None, None

        available = [row for row in rows if row.code not in used_codes]
        if not available:
            available = rows

        chosen = choice(available)
        solution = {
            "from": chosen.solution.get("from"),
            "to": chosen.solution.get("to"),
            "capture": chosen.solution.get("capture"),
        }
        return _serialize_puzzle(chosen), solution


def start_puzzle_rush(time_limit_seconds: int = 60, difficulty: str | None = None) -> dict:
    """
    Start a new Puzzle Rush session.
    time_limit_seconds: 30, 60, 120, 300 (5 min)
    difficulty: "easy", "medium", "hard", or None for mixed
    """
    normalized_difficulty = None if difficulty in (None, "", "mixed") else difficulty
    if normalized_difficulty not in (None, "easy", "medium", "hard"):
        raise ValueError("difficulty must be easy, medium, hard, or mixed")

    current_puzzle, current_solution = _fetch_next_puzzle(normalized_difficulty, set())
    if current_puzzle is None or current_solution is None:
        raise ValueError("No active puzzles found in puzzle bank")

    session_id = str(uuid4())[:16]

    session = {
        "session_id": session_id,
        "time_limit_seconds": time_limit_seconds,
        "difficulty": normalized_difficulty or "mixed",
        "started_at": datetime.now(timezone.utc),
        "score": 0,
        "puzzles_solved": 0,
        "current_puzzle": current_puzzle,
        "current_solution": current_solution,
        "used_puzzle_codes": {current_puzzle["puzzle_id"]},
        "status": "active",
    }

    with _SESSIONS_LOCK:
        _SESSIONS[session_id] = session

    return {
        "session_id": session_id,
        "time_limit_seconds": time_limit_seconds,
        "difficulty": normalized_difficulty or "mixed",
        "puzzles": [current_puzzle],
    }


def get_session(session_id: str) -> dict | None:
    """Fetch session details."""
    with _SESSIONS_LOCK:
        return _SESSIONS.get(session_id)


def submit_puzzle_solution(session_id: str, puzzle_id: str, moves: list[dict]) -> dict:
    """
    Submit solution for a puzzle in Puzzle Rush.
    Returns: {correct, score_earned, total_score, time_remaining}
    """
    with _SESSIONS_LOCK:
        session = _SESSIONS.get(session_id)
        if not session or session["status"] != "active":
            return {"correct": False, "error": "Session not active"}

    # Check if time expired
    elapsed = (datetime.now(timezone.utc) - session["started_at"]).total_seconds()
    time_remaining = max(0, session["time_limit_seconds"] - elapsed)

    if time_remaining <= 0:
        session["status"] = "finished"
        return {"correct": False, "error": "Time expired", "final_score": session["score"]}

    current_puzzle = session.get("current_puzzle")
    current_solution = session.get("current_solution")
    if not current_puzzle or not current_solution:
        return {"correct": False, "error": "Session puzzle state is invalid"}

    if puzzle_id != current_puzzle.get("puzzle_id"):
        return {"correct": False, "error": "Submitted puzzle does not match current session puzzle"}

    first_move = _normalize_move(moves[0]) if moves else None
    correct = bool(
        first_move
        and first_move.get("from") == current_solution.get("from")
        and first_move.get("to") == current_solution.get("to")
        and (
            current_solution.get("capture") is None
            or first_move.get("capture") == current_solution.get("capture")
        )
    )

    difficulty = current_puzzle.get("difficulty")
    base_score = {"easy": 10, "medium": 15, "hard": 20}.get(difficulty, 10)
    score_earned = base_score if correct else 0

    next_puzzle = None
    next_solution = None
    with _SESSIONS_LOCK:
        session["score"] += score_earned
        if correct:
            session["puzzles_solved"] += 1

        if time_remaining > 0:
            used_codes = session.get("used_puzzle_codes", set())
            next_puzzle, next_solution = _fetch_next_puzzle(
                None if session.get("difficulty") == "mixed" else session.get("difficulty"),
                used_codes,
            )
            if next_puzzle and next_solution:
                session["current_puzzle"] = next_puzzle
                session["current_solution"] = next_solution
                used_codes.add(next_puzzle["puzzle_id"])
                session["used_puzzle_codes"] = used_codes

    return {
        "correct": correct,
        "score_earned": score_earned,
        "total_score": session["score"],
        "puzzles_solved": session["puzzles_solved"],
        "time_remaining": int(time_remaining),
        "next_puzzle": next_puzzle,
    }


def finish_puzzle_rush(session_id: str) -> dict:
    """End session and return final score."""
    with _SESSIONS_LOCK:
        session = _SESSIONS.get(session_id)
        if not session:
            return {"error": "Session not found"}
        
        session["status"] = "finished"
        session["finished_at"] = datetime.now(timezone.utc)
        
        return {
            "session_id": session_id,
            "final_score": session["score"],
            "puzzles_solved": session["puzzles_solved"],
            "duration_seconds": (session["finished_at"] - session["started_at"]).total_seconds(),
            "status": "finished",
        }
