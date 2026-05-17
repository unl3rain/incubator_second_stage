from __future__ import annotations

import hashlib
import json

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.puzzle_bank_entry import PuzzleBankEntry


def import_puzzles(payload: dict) -> dict:
    source = (payload.get("source") or "").strip()
    source_url = payload.get("source_url")
    attribution = payload.get("attribution")
    dry_run = bool(payload.get("dry_run", False))
    entries = payload.get("puzzles") or []

    if not source:
        return {
            "total": len(entries),
            "inserted": 0,
            "updated": 0,
            "skipped": len(entries),
            "errors": ["source is required"],
        }

    inserted = 0
    updated = 0
    skipped = 0
    errors: list[str] = []

    with SessionLocal() as session:
        for idx, entry in enumerate(entries):
            error = _validate_entry(entry)
            if error:
                skipped += 1
                errors.append(f"entry[{idx}]: {error}")
                continue

            code = (entry.get("code") or "").strip() or _generated_code(entry)
            existing = session.execute(select(PuzzleBankEntry).where(PuzzleBankEntry.code == code)).scalar_one_or_none()

            if existing is None:
                if not dry_run:
                    session.add(
                        PuzzleBankEntry(
                            code=code,
                            title=entry["title"],
                            hint=entry["hint"],
                            difficulty=entry.get("difficulty", "easy"),
                            source=source,
                            source_url=source_url,
                            attribution=attribution,
                            board=entry["board"],
                            turn=entry["turn"],
                            solution={
                                "from": entry["solution"]["from"],
                                "to": entry["solution"]["to"],
                                "capture": entry["solution"].get("capture"),
                            },
                            is_active=True,
                        )
                    )
                inserted += 1
                continue

            if _same_content(existing, entry, source, source_url, attribution):
                skipped += 1
                continue

            if not dry_run:
                existing.title = entry["title"]
                existing.hint = entry["hint"]
                existing.difficulty = entry.get("difficulty", "easy")
                existing.source = source
                existing.source_url = source_url
                existing.attribution = attribution
                existing.board = entry["board"]
                existing.turn = entry["turn"]
                existing.solution = {
                    "from": entry["solution"]["from"],
                    "to": entry["solution"]["to"],
                    "capture": entry["solution"].get("capture"),
                }
                existing.is_active = True

            updated += 1

        if not dry_run:
            session.commit()

    return {
        "total": len(entries),
        "inserted": inserted,
        "updated": updated,
        "skipped": skipped,
        "errors": errors,
    }


def _validate_entry(entry: dict) -> str | None:
    title = (entry.get("title") or "").strip()
    hint = (entry.get("hint") or "").strip()
    turn = entry.get("turn")
    board = entry.get("board")
    solution = entry.get("solution") or {}

    if not title:
        return "title is required"
    if not hint:
        return "hint is required"
    if turn not in ("white", "red"):
        return "turn must be white or red"
    if not _is_valid_board(board):
        return "board must be an 8x8 matrix"

    from_pos = solution.get("from")
    to_pos = solution.get("to")
    if not _is_square(from_pos) or not _is_square(to_pos):
        return "solution.from and solution.to must be [row, col]"

    return None


def _is_valid_board(board: object) -> bool:
    if not isinstance(board, list) or len(board) != 8:
        return False

    for row in board:
        if not isinstance(row, list) or len(row) != 8:
            return False

    return True


def _is_square(value: object) -> bool:
    if not isinstance(value, list) or len(value) != 2:
        return False

    return all(isinstance(v, int) and 0 <= v < 8 for v in value)


def _generated_code(entry: dict) -> str:
    raw = json.dumps(
        {
            "title": entry.get("title"),
            "turn": entry.get("turn"),
            "board": entry.get("board"),
            "solution": {
                "from": entry.get("solution", {}).get("from"),
                "to": entry.get("solution", {}).get("to"),
            },
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
    return f"import-{digest}"


def _same_content(existing: PuzzleBankEntry, entry: dict, source: str, source_url: str | None, attribution: str | None) -> bool:
    return (
        existing.title == entry["title"]
        and existing.hint == entry["hint"]
        and existing.difficulty == entry.get("difficulty", "easy")
        and existing.turn == entry["turn"]
        and existing.board == entry["board"]
        and existing.solution == {
            "from": entry["solution"]["from"],
            "to": entry["solution"]["to"],
            "capture": entry["solution"].get("capture"),
        }
        and existing.source == source
        and existing.source_url == source_url
        and existing.attribution == attribution
        and bool(existing.is_active)
    )
