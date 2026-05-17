from __future__ import annotations

from copy import deepcopy
from typing import Literal, TypedDict

BOARD_SIZE = 8
Player = Literal["white", "red"]


class Piece(TypedDict):
    player: Player
    king: bool


class Move(TypedDict):
    from_: tuple[int, int]
    to: tuple[int, int]
    capture: tuple[int, int] | None


def _inside(row: int, col: int) -> bool:
    return 0 <= row < BOARD_SIZE and 0 <= col < BOARD_SIZE


def create_initial_board() -> list[list[Piece | None]]:
    board: list[list[Piece | None]] = [[None for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]

    for row in range(BOARD_SIZE):
        for col in range(BOARD_SIZE):
            if (row + col) % 2 == 0:
                continue

            if row < 3:
                board[row][col] = {"player": "red", "king": False}
            elif row > 4:
                board[row][col] = {"player": "white", "king": False}

    return board


def _movement_directions(piece: Piece) -> list[int]:
    if piece["king"]:
        return [1, -1]

    return [-1] if piece["player"] == "white" else [1]


def _capture_directions() -> list[int]:
    return [1, -1]


def _piece_moves(
    board: list[list[Piece | None]],
    row: int,
    col: int,
    force_capture_only: bool = False,
) -> list[Move]:
    piece = board[row][col]
    if piece is None:
        return []

    if piece["king"]:
        return _king_moves(board, row, col, force_capture_only)

    moves: list[Move] = []

    for row_delta in _movement_directions(piece):
        for col_delta in (-1, 1):
            next_row = row + row_delta
            next_col = col + col_delta

            if not _inside(next_row, next_col):
                continue

            next_cell = board[next_row][next_col]
            if next_cell is None and not force_capture_only:
                moves.append({"from_": (row, col), "to": (next_row, next_col), "capture": None})

    for row_delta in _capture_directions():
        for col_delta in (-1, 1):
            next_row = row + row_delta
            next_col = col + col_delta

            if not _inside(next_row, next_col):
                continue

            next_cell = board[next_row][next_col]
            if next_cell is None or next_cell["player"] == piece["player"]:
                continue

            jump_row = next_row + row_delta
            jump_col = next_col + col_delta

            if not _inside(jump_row, jump_col):
                continue

            if board[jump_row][jump_col] is None:
                moves.append({"from_": (row, col), "to": (jump_row, jump_col), "capture": (next_row, next_col)})

    return moves


def _king_moves(
    board: list[list[Piece | None]],
    row: int,
    col: int,
    force_capture_only: bool = False,
) -> list[Move]:
    piece = board[row][col]
    if piece is None:
        return []

    moves: list[Move] = []

    for row_delta in (1, -1):
        for col_delta in (1, -1):
            next_row = row + row_delta
            next_col = col + col_delta

            if not force_capture_only:
                while _inside(next_row, next_col) and board[next_row][next_col] is None:
                    moves.append({"from_": (row, col), "to": (next_row, next_col), "capture": None})
                    next_row += row_delta
                    next_col += col_delta

            enemy_square: tuple[int, int] | None = None
            scan_row = row + row_delta
            scan_col = col + col_delta

            while _inside(scan_row, scan_col):
                cell = board[scan_row][scan_col]

                if cell is None:
                    if enemy_square is not None:
                        moves.append({"from_": (row, col), "to": (scan_row, scan_col), "capture": enemy_square})
                    scan_row += row_delta
                    scan_col += col_delta
                    continue

                if cell["player"] == piece["player"]:
                    break

                if enemy_square is not None:
                    break

                enemy_square = (scan_row, scan_col)
                scan_row += row_delta
                scan_col += col_delta

    return moves


def all_moves(board: list[list[Piece | None]], player: Player) -> list[Move]:
    moves: list[Move] = []

    for row in range(BOARD_SIZE):
        for col in range(BOARD_SIZE):
            piece = board[row][col]
            if piece is None or piece["player"] != player:
                continue
            moves.extend(_piece_moves(board, row, col))

    has_capture = any(move["capture"] is not None for move in moves)
    if has_capture:
        return [move for move in moves if move["capture"] is not None]

    return moves


def moves_for_piece(
    board: list[list[Piece | None]],
    row: int,
    col: int,
    player: Player,
    chain_capture_only: bool = False,
) -> list[Move]:
    piece = board[row][col]
    if piece is None or piece["player"] != player:
        return []

    if chain_capture_only:
        return [move for move in _piece_moves(board, row, col, True) if move["capture"] is not None]

    return [move for move in all_moves(board, player) if move["from_"] == (row, col)]


def _promote(piece: Piece, row: int) -> Piece:
    if piece["king"]:
        return piece

    if piece["player"] == "red" and row == BOARD_SIZE - 1:
        return {"player": piece["player"], "king": True}

    if piece["player"] == "white" and row == 0:
        return {"player": piece["player"], "king": True}

    return piece


def apply_move(board: list[list[Piece | None]], move: Move) -> list[list[Piece | None]]:
    next_board = deepcopy(board)

    from_row, from_col = move["from_"]
    to_row, to_col = move["to"]

    moving_piece = next_board[from_row][from_col]
    if moving_piece is None:
        raise ValueError("No piece at source square")

    next_board[from_row][from_col] = None

    if move["capture"] is not None:
        cap_row, cap_col = move["capture"]
        next_board[cap_row][cap_col] = None

    next_board[to_row][to_col] = _promote(moving_piece, to_row)
    return next_board


def detect_winner(board: list[list[Piece | None]], player_to_move: Player) -> Player | None:
    red_count = 0
    white_count = 0

    for row in board:
        for piece in row:
            if piece is None:
                continue
            if piece["player"] == "red":
                red_count += 1
            else:
                white_count += 1

    if red_count == 0:
        return "white"
    if white_count == 0:
        return "red"

    if not all_moves(board, player_to_move):
        return "white" if player_to_move == "red" else "red"

    return None
