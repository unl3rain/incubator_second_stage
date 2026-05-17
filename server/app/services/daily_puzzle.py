from __future__ import annotations

from datetime import date, datetime, timedelta
from random import Random

from sqlalchemy import func, select

from app.core.db import SessionLocal
from app.models.daily_puzzle_attempt import DailyPuzzleAttempt
from app.models.puzzle_bank_entry import PuzzleBankEntry


def _empty_board() -> list[list[dict | None]]:
    return [[None for _ in range(8)] for _ in range(8)]


def _piece(player: str, king: bool = False) -> dict:
    return {"player": player, "king": king}


def _is_dark_square(row: int, col: int) -> bool:
    return (row + col) % 2 == 1


def _generate_capture_puzzle(seed: int) -> dict:
    rng = Random(seed)
    turn = "white" if seed % 2 == 0 else "red"

    attempts = 0
    while attempts < 1000:
        attempts += 1
        board = _empty_board()

        if turn == "red":
            from_row = rng.randint(0, 5)
            row_step = 1
        else:
            from_row = rng.randint(2, 7)
            row_step = -1

        candidate_cols = [c for c in range(8) if _is_dark_square(from_row, c)]
        from_col = rng.choice(candidate_cols)
        col_step = rng.choice([-1, 1])

        mid_row = from_row + row_step
        mid_col = from_col + col_step
        to_row = from_row + row_step * 2
        to_col = from_col + col_step * 2

        if not (0 <= mid_row < 8 and 0 <= mid_col < 8 and 0 <= to_row < 8 and 0 <= to_col < 8):
            continue

        if not _is_dark_square(mid_row, mid_col) or not _is_dark_square(to_row, to_col):
            continue

        board[from_row][from_col] = _piece(turn)
        board[mid_row][mid_col] = _piece("red" if turn == "white" else "white")

        extras = rng.randint(0, 3)
        for _ in range(extras):
            r = rng.randint(0, 7)
            c = rng.randint(0, 7)
            if not _is_dark_square(r, c) or board[r][c] is not None:
                continue
            board[r][c] = _piece(rng.choice(["white", "red"]), king=rng.random() < 0.2)

        difficulty = "easy" if extras <= 1 else "medium" if extras == 2 else "hard"

        return {
            "title": f"Daily Tactic #{seed + 1}",
            "hint": "Find the forcing capture sequence starter.",
            "difficulty": difficulty,
            "source": "internal-generated",
            "source_url": None,
            "attribution": "Generated puzzle bank for training mode.",
            "board": board,
            "turn": turn,
            "solution": {"from": [from_row, from_col], "to": [to_row, to_col]},
        }

    raise RuntimeError("Failed to generate puzzle")


def _ensure_puzzle_bank_seeded(session, minimum: int = 500) -> None:
    current = session.execute(
        select(func.count()).select_from(PuzzleBankEntry).where(PuzzleBankEntry.is_active.is_(True))
    ).scalar_one()

    if current >= minimum:
        return

    missing = minimum - current
    existing_total = session.execute(select(func.count()).select_from(PuzzleBankEntry)).scalar_one()

    for offset in range(missing):
        seed = existing_total + offset
        puzzle = _generate_capture_puzzle(seed)
        session.add(
            PuzzleBankEntry(
                code=f"generated-{seed:05d}",
                title=puzzle["title"],
                hint=puzzle["hint"],
                difficulty=puzzle["difficulty"],
                source=puzzle["source"],
                source_url=puzzle["source_url"],
                attribution=puzzle["attribution"],
                board=puzzle["board"],
                turn=puzzle["turn"],
                solution=puzzle["solution"],
                is_active=True,
            )
        )

    session.commit()


def _get_puzzle_for_day(session, target_day: date) -> dict:
    _ensure_puzzle_bank_seeded(session)
    total = session.execute(
        select(func.count()).select_from(PuzzleBankEntry).where(PuzzleBankEntry.is_active.is_(True))
    ).scalar_one()

    if total == 0:
        raise RuntimeError("Puzzle bank is empty")

    index = target_day.toordinal() % total
    chosen = session.execute(
        select(PuzzleBankEntry)
        .where(PuzzleBankEntry.is_active.is_(True))
        .order_by(PuzzleBankEntry.id.asc())
        .offset(index)
        .limit(1)
    ).scalar_one()

    return {
        "puzzle_date": target_day.isoformat(),
        "title": chosen.title,
        "hint": chosen.hint,
        "difficulty": chosen.difficulty,
        "source": chosen.source,
        "source_url": chosen.source_url,
        "attribution": chosen.attribution,
        "board": chosen.board,
        "turn": chosen.turn,
        "solution": chosen.solution,
    }


def get_daily_puzzle(profile_id: str | None = None) -> dict:
    today = date.today()
    with SessionLocal() as session:
        puzzle = _get_puzzle_for_day(session, today)

        solved_today = False
        attempts_today = 0
        streak = 0

        if profile_id:
            row = session.execute(
                select(DailyPuzzleAttempt).where(
                    DailyPuzzleAttempt.profile_id == profile_id,
                    DailyPuzzleAttempt.puzzle_date == today,
                )
            ).scalar_one_or_none()
            if row is not None:
                solved_today = row.solved
                attempts_today = row.attempts

            streak = _calculate_streak(session, profile_id)

    return {
        "puzzle_date": puzzle["puzzle_date"],
        "title": puzzle["title"],
        "hint": puzzle["hint"],
        "difficulty": puzzle["difficulty"],
        "source": puzzle["source"],
        "source_url": puzzle["source_url"],
        "attribution": puzzle["attribution"],
        "board": puzzle["board"],
        "turn": puzzle["turn"],
        "solved_today": solved_today,
        "attempts_today": attempts_today,
        "streak": streak,
    }


def submit_daily_puzzle(profile_id: str, puzzle_date: str, from_pos: list[int], to_pos: list[int]) -> dict:
    target_day = date.fromisoformat(puzzle_date)
    with SessionLocal() as session:
        puzzle = _get_puzzle_for_day(session, target_day)
        correct = puzzle["solution"]["from"] == from_pos and puzzle["solution"]["to"] == to_pos

        row = session.execute(
            select(DailyPuzzleAttempt).where(
                DailyPuzzleAttempt.profile_id == profile_id,
                DailyPuzzleAttempt.puzzle_date == target_day,
            )
        ).scalar_one_or_none()

        if row is None:
            row = DailyPuzzleAttempt(
                profile_id=profile_id,
                puzzle_date=target_day,
                solved=False,
                attempts=0,
            )
            session.add(row)

        row.attempts += 1

        if correct and not row.solved:
            row.solved = True
            row.solved_at = datetime.utcnow()

        session.commit()
        streak = _calculate_streak(session, profile_id)
        solved_today = bool(row.solved)

    return {
        "correct": correct,
        "solved_today": solved_today,
        "streak": streak,
        "message": (
            "Great solve. Your streak is growing."
            if correct
            else "Already solved today. Come back tomorrow for the next challenge."
            if solved_today
            else "Not quite. Try another tactical line."
        ),
    }


def _calculate_streak(session, profile_id: str) -> int:
    rows = session.execute(
        select(DailyPuzzleAttempt.puzzle_date).where(
            DailyPuzzleAttempt.profile_id == profile_id,
            DailyPuzzleAttempt.solved.is_(True),
        )
    ).scalars()

    solved_days = set(rows)
    streak = 0
    cursor = date.today()
    while cursor in solved_days:
        streak += 1
        cursor = cursor - timedelta(days=1)

    return streak