from __future__ import annotations

import random

from app.domain.checkers import Piece, apply_move
from app.services.advanced_engine import evaluate_candidates_with_py_draughts


def _material_score(board: list[list[Piece | None]], player: str) -> int:
    score = 0
    for row in board:
        for piece in row:
            if piece is None:
                continue
            value = 175 if piece["king"] else 100
            score += value if piece["player"] == player else -value
    return score


def _promotion_bonus(board_before: list[list[Piece | None]], move: dict) -> int:
    from_row, from_col = move["from_"]
    to_row, _ = move["to"]
    piece = board_before[from_row][from_col]
    if piece is None or piece["king"]:
        return 0

    if piece["player"] == "white" and to_row == 0:
        return 40

    if piece["player"] == "red" and to_row == 7:
        return 40

    return 0


def _heuristic_score(board_before: list[list[Piece | None]], move: dict, player: str) -> int:
    board_after = apply_move(board_before, move)
    base = _material_score(board_after, player)
    capture_bonus = 25 if move.get("capture") is not None else 0
    return base + capture_bonus + _promotion_bonus(board_before, move)


def _difficulty_from_elo(elo: int) -> tuple[str, float, int]:
    if elo < 900:
        return "beginner", 0.35, 5
    if elo < 1200:
        return "novice", 0.24, 4
    if elo < 1500:
        return "intermediate", 0.14, 3
    if elo < 1800:
        return "advanced", 0.06, 2
    return "expert", 0.02, 1


def choose_ai_move(board: list[list[Piece | None]], player: str, candidate_moves: list[dict], elo: int) -> dict:
    if not candidate_moves:
        raise ValueError("No legal moves available for AI")

    _, randomness, top_window = _difficulty_from_elo(elo)
    engine_eval = evaluate_candidates_with_py_draughts(board, player, candidate_moves)

    scored: list[tuple[dict, float]] = []
    for move in candidate_moves:
        heuristic = float(_heuristic_score(board, move, player))
        engine_score = engine_eval["scores"].get((move["from_"], move["to"]))
        if engine_score is not None:
            score = engine_score * 100 + heuristic * 0.1
        else:
            score = heuristic
        scored.append((move, score))

    scored.sort(key=lambda item: item[1], reverse=True)

    if random.random() < randomness:
        window = min(top_window, len(scored))
        return random.choice(scored[:window])[0]

    return scored[0][0]
