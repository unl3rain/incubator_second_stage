from __future__ import annotations

from copy import deepcopy

from app.core.config import settings
from app.domain.checkers import Piece, apply_move


def _dark_square_to_engine_index(row: int, col: int) -> int:
    return row * 4 + (col // 2)


def _engine_index_to_row_col(index: int) -> tuple[int, int]:
    row = index // 4
    col_in_row = index % 4
    if row % 2 == 0:
        return row, col_in_row * 2 + 1
    return row, col_in_row * 2


def _to_american_fen(board: list[list[Piece | None]], turn: str) -> str:
    white: list[str] = []
    black: list[str] = []

    for row in range(8):
        for col in range(8):
            if (row + col) % 2 == 0:
                continue

            piece = board[row][col]
            if piece is None:
                continue

            sq = _dark_square_to_engine_index(row, col) + 1
            token = f"K{sq}" if piece["king"] else str(sq)

            if piece["player"] == "white":
                white.append(token)
            else:
                black.append(token)

    engine_turn = "W" if turn == "white" else "B"
    return f"{engine_turn}:W{','.join(white)}:B{','.join(black)}"


def _try_import_engine():
    try:
        from draughts import AlphaBetaEngine, AmericanBoard

        return AlphaBetaEngine, AmericanBoard
    except Exception:
        return None, None


def get_engine_status() -> dict:
    provider = settings.coach_engine_provider.lower()
    AlphaBetaEngine, AmericanBoard = _try_import_engine()
    import_ok = AlphaBetaEngine is not None and AmericanBoard is not None

    available = provider == "py-draughts" and import_ok
    reason = "ok"

    if provider != "py-draughts":
        reason = "provider-disabled"
    elif not import_ok:
        reason = "missing-py-draughts"

    return {
        "provider": provider,
        "available": available,
        "import_ok": import_ok,
        "reason": reason,
        "configured_depth": settings.coach_engine_depth,
        "configured_time_limit": settings.coach_engine_time_limit,
    }


def evaluate_candidates_with_py_draughts(
    board_before: list[list[Piece | None]],
    player: str,
    candidate_moves: list[dict],
) -> dict:
    if settings.coach_engine_provider.lower() != "py-draughts":
        return {"available": False, "scores": {}, "analysis_mode": "heuristic-search"}

    AlphaBetaEngine, AmericanBoard = _try_import_engine()
    if AlphaBetaEngine is None or AmericanBoard is None:
        return {"available": False, "scores": {}, "analysis_mode": "heuristic-search"}

    scores: dict[tuple[tuple[int, int], tuple[int, int]], float] = {}

    for move in candidate_moves:
        board_after = apply_move(deepcopy(board_before), move)
        turn_after = "red" if player == "white" else "white"

        try:
            fen = _to_american_fen(board_after, turn_after)
            engine_board = AmericanBoard.from_fen(fen)
            engine = AlphaBetaEngine(
                depth_limit=settings.coach_engine_depth,
                time_limit=settings.coach_engine_time_limit,
                name="PyDraughtsEngine",
            )

            _, score = engine.get_best_move(engine_board, with_evaluation=True)

            # py-draughts score is from side-to-move perspective. Convert to player perspective.
            player_score = -float(score)
            scores[(move["from_"], move["to"])] = player_score
        except Exception:
            continue

    return {
        "available": bool(scores),
        "scores": scores,
        "analysis_mode": "py-draughts+heuristic" if scores else "heuristic-search",
    }


def to_public_move(move: dict) -> dict:
    return {
        "from": [move["from_"][0], move["from_"][1]],
        "to": [move["to"][0], move["to"][1]],
        "capture": [move["capture"][0], move["capture"][1]] if move["capture"] else None,
    }
