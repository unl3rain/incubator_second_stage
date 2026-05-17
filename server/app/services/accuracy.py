"""Accuracy score and move quality analysis from real move reconstruction."""

from app.domain.checkers import all_moves, apply_move, create_initial_board, moves_for_piece
from app.services.coach import analyze_move_quality


def _find_selected_move(candidate_moves: list[dict], from_pos: tuple[int, int], to_pos: tuple[int, int]) -> dict | None:
    for move in candidate_moves:
        if move["from_"] == from_pos and move["to"] == to_pos:
            return move
    return None


def _rating_from_delta(score_delta: float) -> str:
    if score_delta <= 5:
        return "best"
    if score_delta <= 18:
        return "good"
    if score_delta <= 45:
        return "ok"
    if score_delta <= 90:
        return "inaccuracy"
    if score_delta <= 150:
        return "mistake"
    return "blunder"


def calculate_accuracy_score(game_id: str, move_history: list[dict]) -> dict:
    ratings = {"blunder": 0, "mistake": 0, "inaccuracy": 0, "ok": 0, "good": 0, "best": 0}
    moves_with_ratings: list[dict] = []

    if not move_history:
        return {
            "game_id": game_id,
            "blunders": 0,
            "mistakes": 0,
            "inaccuracies": 0,
            "oks": 0,
            "goods": 0,
            "bests": 0,
            "accuracy_percent": 100.0,
            "moves": [],
        }

    board = create_initial_board()
    turn = "white"
    forced_piece: tuple[int, int] | None = None

    for index, entry in enumerate(move_history):
        player = entry.get("player", turn)
        from_pos = tuple(entry.get("from", [0, 0]))
        to_pos = tuple(entry.get("to", [0, 0]))

        candidate_moves = (
            moves_for_piece(board, forced_piece[0], forced_piece[1], turn, True)
            if forced_piece is not None
            else all_moves(board, turn)
        )

        selected_move = _find_selected_move(candidate_moves, from_pos, to_pos)
        if selected_move is None:
            selected_move = {
                "from_": from_pos,
                "to": to_pos,
                "capture": tuple(entry["capture"]) if entry.get("capture") else None,
            }

        feedback = analyze_move_quality(board, player, selected_move, candidate_moves)
        score_delta = float(feedback.get("score_delta", 0.0))
        rating = _rating_from_delta(score_delta)
        if rating not in ratings:
            rating = "ok"

        ratings[rating] += 1
        best_move = feedback.get("suggested_move")
        moves_with_ratings.append(
            {
                "move_number": index + 1,
                "from": [selected_move["from_"][0], selected_move["from_"][1]],
                "to": [selected_move["to"][0], selected_move["to"][1]],
                "rating": rating,
                "player": player,
                "score_delta": round(score_delta, 2),
                "best_move": best_move,
                "summary": feedback.get("summary", ""),
            }
        )

        board = apply_move(board, selected_move)

        if selected_move.get("capture") is not None:
            continuation = moves_for_piece(board, to_pos[0], to_pos[1], turn, True)
            if continuation:
                forced_piece = to_pos
                continue

        forced_piece = None
        turn = "red" if turn == "white" else "white"

    total_moves = len(move_history)
    accuracy_percent = ((ratings["best"] + ratings["good"]) / total_moves * 100) if total_moves > 0 else 100.0

    return {
        "game_id": game_id,
        "blunders": ratings["blunder"],
        "mistakes": ratings["mistake"],
        "inaccuracies": ratings["inaccuracy"],
        "oks": ratings["ok"],
        "goods": ratings["good"],
        "bests": ratings["best"],
        "accuracy_percent": accuracy_percent,
        "moves": moves_with_ratings,
    }
