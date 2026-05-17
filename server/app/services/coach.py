from __future__ import annotations

from copy import deepcopy

from app.core.config import settings
from app.domain.checkers import Piece, all_moves, apply_move
from app.services.advanced_engine import evaluate_candidates_with_py_draughts, to_public_move


def _opponent(player: str) -> str:
    return "red" if player == "white" else "white"


def _material_score(board: list[list[Piece | None]], player: str) -> int:
    score = 0
    for row in board:
        for piece in row:
            if piece is None:
                continue
            value = 175 if piece["king"] else 100
            score += value if piece["player"] == player else -value
    return score


def _count_capture_moves(moves: list[dict]) -> int:
    return sum(1 for move in moves if move.get("capture") is not None)


def _is_promotion_move(board: list[list[Piece | None]], move: dict) -> bool:
    from_row, from_col = move["from_"]
    to_row, _ = move["to"]
    piece = board[from_row][from_col]
    if piece is None or piece["king"]:
        return False

    if piece["player"] == "white" and to_row == 0:
        return True

    if piece["player"] == "red" and to_row == 7:
        return True

    return False


def _move_key(move: dict) -> tuple[tuple[int, int], tuple[int, int]]:
    return move["from_"], move["to"]


def _candidate_note(details: dict) -> str:
    notes: list[str] = []
    if details["is_capture"]:
        notes.append("captures material")
    if details["is_promotion"]:
        notes.append("promotes to king")
    if details["threat_count"] == 0:
        notes.append("limits immediate counter-captures")

    if not notes:
        return "keeps position flexible"

    return ", ".join(notes)


def _evaluate_move(board_before: list[list[Piece | None]], move: dict, player: str) -> tuple[int, dict]:
    board_after = apply_move(deepcopy(board_before), move)
    opponent = _opponent(player)

    opponent_moves = all_moves(board_after, opponent)
    threat_count = _count_capture_moves(opponent_moves)

    # One-ply reply score: assume opponent picks reply that minimizes current player's eval.
    if opponent_moves:
        worst_reply_score = None
        for reply in opponent_moves:
            board_after_reply = apply_move(deepcopy(board_after), reply)
            candidate_score = _material_score(board_after_reply, player)
            if worst_reply_score is None or candidate_score < worst_reply_score:
                worst_reply_score = candidate_score
        reply_score = worst_reply_score if worst_reply_score is not None else _material_score(board_after, player)
    else:
        reply_score = _material_score(board_after, player) + 10000

    tactical_bonus = 0
    if move.get("capture") is not None:
        tactical_bonus += 25

    if _is_promotion_move(board_before, move):
        tactical_bonus += 35

    score = reply_score - threat_count * 20 + tactical_bonus
    details = {
        "threat_count": threat_count,
        "is_capture": move.get("capture") is not None,
        "is_promotion": _is_promotion_move(board_before, move),
        "material_after": _material_score(board_after, player),
    }
    return score, details


def analyze_move_quality(board_before: list[list[Piece | None]], player: str, selected_move: dict, candidate_moves: list[dict]) -> dict:
    if not candidate_moves:
        return {
            "rating": "neutral",
            "summary": "No alternative legal moves to compare.",
            "reasons": [],
            "analysis_mode": "heuristic-search",
            "search_depth": 2,
            "suggested_move": None,
            "top_moves": [],
        }

    engine_eval = evaluate_candidates_with_py_draughts(board_before, player, candidate_moves)

    scored = []
    for move in candidate_moves:
        heuristic_score, details = _evaluate_move(board_before, move, player)

        engine_score = engine_eval["scores"].get((move["from_"], move["to"]))
        if engine_score is not None:
            # Engine score is primary; heuristic is a tie-breaker for explanation stability.
            final_score = engine_score * 100 + heuristic_score * 0.1
        else:
            final_score = float(heuristic_score)

        details["engine_score"] = engine_score
        details["heuristic_score"] = heuristic_score
        scored.append((move, final_score, details))

    scored.sort(key=lambda item: item[1], reverse=True)
    best_move, best_score, best_details = scored[0]

    selected_entry = next((item for item in scored if _move_key(item[0]) == _move_key(selected_move)), None)
    if selected_entry is None:
        selected_entry = scored[-1]

    played_move, played_score, played_details = selected_entry
    delta = best_score - played_score

    if delta <= 15:
        rating = "good"
        summary = "Strong move. It is close to the best tactical option."
    elif delta <= 60:
        rating = "inaccuracy"
        summary = "Playable, but there was a stronger tactical continuation."
    elif delta <= 120:
        rating = "mistake"
        summary = "This move gives up important tactical value."
    else:
        rating = "blunder"
        summary = "Serious tactical error. The opponent gets a large advantage."

    reasons: list[str] = []

    if played_details["threat_count"] > best_details["threat_count"]:
        reasons.append(
            f"Your move allows {played_details['threat_count']} immediate capture threat(s), while the best move allows {best_details['threat_count']}."
        )

    if not played_details["is_capture"] and best_details["is_capture"]:
        reasons.append("Best line takes material immediately; your move misses that tactical gain.")

    if best_details["is_promotion"] and not played_details["is_promotion"]:
        reasons.append("Best move promotes to king sooner, improving long-term control.")

    material_gap = best_details["material_after"] - played_details["material_after"]
    if material_gap > 0:
        reasons.append(f"After the move sequence, the best line keeps about {material_gap} more material points.")

    if not reasons:
        reasons.append("The best move keeps safer piece coordination and reduces counterplay.")

    min_score = min(item[1] for item in scored)
    max_score = max(item[1] for item in scored)
    score_range = max(max_score - min_score, 1)
    top_moves = []
    for move, score, details in scored[:3]:
        confidence = int(max(1, min(99, round(((score - min_score) / score_range) * 100))))
        top_moves.append(
            {
                **to_public_move(move),
                "score": int(round(score)),
                "confidence": confidence,
                "note": _candidate_note(details),
            }
        )

    return {
        "rating": rating,
        "summary": summary,
        "reasons": reasons,
        "analysis_mode": engine_eval["analysis_mode"],
        "search_depth": settings.coach_engine_depth,
        "suggested_move": to_public_move(best_move),
        "top_moves": top_moves,
        "played_score": float(played_score),
        "best_score": float(best_score),
        "score_delta": float(delta),
    }
