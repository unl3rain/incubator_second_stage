from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from threading import RLock
from uuid import uuid4

from app.domain.checkers import (
    Piece,
    Player,
    all_moves,
    apply_move,
    create_initial_board,
    detect_winner,
    moves_for_piece,
)


@dataclass
class GameState:
    game_id: str
    board: list[list[Piece | None]]
    turn: Player
    winner: Player | None = None
    forced_piece: tuple[int, int] | None = None
    seats: dict[Player, str | None] = field(default_factory=lambda: {"white": None, "red": None})
    profiles: dict[str, dict[str, str | None]] = field(default_factory=dict)
    result_recorded: bool = False
    mode: str = "pvp"
    ai_elo: int | None = None
    ai_color: Player | None = None
    ranked: bool = False
    season_key: str | None = None
    time_control_minutes: int | None = None
    clock_enabled: bool = False
    white_time_ms: int | None = None
    red_time_ms: int | None = None
    last_turn_started_at: datetime | None = None
    winner_reason: str | None = None
    disconnected_at: dict[Player, datetime | None] = field(default_factory=lambda: {"white": None, "red": None})
    move_history: list[dict] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)


class GameStore:
    AI_PLAYER_ID = "ai-bot"

    def __init__(self) -> None:
        self._games: dict[str, GameState] = {}
        self._lock = RLock()

    def create_game(
        self,
        mode: str = "pvp",
        ai_elo: int = 1200,
        ai_color: Player = "red",
        ranked: bool = False,
        time_control_minutes: int | None = None,
        board: list[list[Piece | None]] | None = None,
        turn: Player = "white",
        forced_piece: tuple[int, int] | None = None,
    ) -> GameState:
        with self._lock:
            game_id = uuid4().hex[:10]
            clock_enabled = bool(time_control_minutes and time_control_minutes > 0)
            initial_time_ms = int(time_control_minutes * 60 * 1000) if clock_enabled else None

            if board is None:
                starting_board = create_initial_board()
            else:
                if len(board) != 8 or any(len(row) != 8 for row in board):
                    raise ValueError("Custom board must be an 8x8 grid")

                starting_board = []
                for row in board:
                    next_row: list[Piece | None] = []
                    for cell in row:
                        if cell is None:
                            next_row.append(None)
                            continue

                        # Handle both dicts and Pydantic models
                        if isinstance(cell, dict):
                            player = cell.get("player")
                            king = bool(cell.get("king", False))
                        else:
                            # Handle Pydantic PieceOut model
                            player = getattr(cell, "player", None)
                            king = bool(getattr(cell, "king", False))
                        
                        if player not in ("white", "red"):
                            raise ValueError("Custom board pieces must specify player as white or red")
                        next_row.append({"player": player, "king": king})
                    starting_board.append(next_row)

            game = GameState(
                game_id=game_id,
                board=starting_board,
                turn=turn,
                mode=mode,
                ai_elo=ai_elo if mode == "vs_ai" else None,
                ai_color=ai_color if mode == "vs_ai" else None,
                ranked=ranked if mode == "pvp" else False,
                season_key=self.current_season_key(),
                time_control_minutes=time_control_minutes if clock_enabled else None,
                clock_enabled=clock_enabled,
                white_time_ms=initial_time_ms,
                red_time_ms=initial_time_ms,
                last_turn_started_at=None,
            )

            if forced_piece is not None:
                game.forced_piece = forced_piece

            if mode == "vs_ai":
                game.seats[ai_color] = self.AI_PLAYER_ID
                game.profiles[self.AI_PLAYER_ID] = {
                    "nickname": "Arena AI",
                    "city": "Cloud",
                    "color": ai_color,
                }

            self._games[game_id] = game
            return game

    def _start_clock_if_ready(self, game: GameState) -> None:
        if not game.clock_enabled or game.winner is not None:
            return

        if game.last_turn_started_at is not None:
            return

        if game.seats.get("white") is None or game.seats.get("red") is None:
            return

        game.last_turn_started_at = datetime.utcnow()

    def _is_clock_ready(self, game: GameState) -> bool:
        return game.seats.get("white") is not None and game.seats.get("red") is not None

    def get_game(self, game_id: str) -> GameState | None:
        with self._lock:
            game = self._games.get(game_id)
            if game is not None:
                self._sync_clock(game)
            return game

    def join_game(
        self,
        game_id: str,
        nickname: str,
        city: str | None = None,
        preferred_color: Player | None = None,
        player_id: str | None = None,
        profile_id: str | None = None,
    ) -> tuple[GameState, dict]:
        with self._lock:
            game = self._games.get(game_id)
            if game is None:
                raise KeyError("Game not found")

            # Recover an existing seat by persistent profile_id when player_id is missing/stale.
            # This keeps the same logical user from being downgraded to spectator after reconnects.
            if profile_id and player_id:
                for existing_player_id, existing_profile in game.profiles.items():
                    if existing_profile.get("profile_id") != profile_id:
                        continue

                    color = existing_profile.get("color")
                    requested_color = preferred_color if preferred_color in ("white", "red") else None
                    if (
                        requested_color
                        and requested_color != color
                        and not game.move_history
                        and game.seats.get(requested_color) is None
                    ):
                        if color in ("white", "red") and game.seats.get(color) == existing_player_id:
                            game.seats[color] = None
                            game.disconnected_at[color] = None

                        existing_profile["color"] = requested_color
                        game.seats[requested_color] = existing_player_id
                        game.disconnected_at[requested_color] = None
                        color = requested_color

                    if color in ("white", "red") and game.seats.get(color) == existing_player_id:
                        existing_profile["nickname"] = nickname or existing_profile.get("nickname") or "Guest"
                        existing_profile["city"] = city or existing_profile.get("city")
                        existing_profile["profile_id"] = profile_id
                        game.disconnected_at[color] = None
                        self._start_clock_if_ready(game)
                        return game, {
                            "player_id": existing_player_id,
                            "color": color,
                            "nickname": existing_profile["nickname"],
                            "city": existing_profile["city"],
                            "profile_id": existing_profile.get("profile_id"),
                        }

            if player_id and player_id in game.profiles:
                profile = game.profiles[player_id]
                profile["nickname"] = nickname or profile["nickname"] or "Guest"
                profile["city"] = city or profile["city"]
                profile["profile_id"] = profile_id or profile.get("profile_id")
                color = profile.get("color")
                requested_color = preferred_color if preferred_color in ("white", "red") else None
                if (
                    requested_color
                    and requested_color != color
                    and not game.move_history
                    and game.seats.get(requested_color) is None
                ):
                    if color in ("white", "red") and game.seats.get(color) == player_id:
                        game.seats[color] = None
                        game.disconnected_at[color] = None

                    profile["color"] = requested_color
                    game.seats[requested_color] = player_id
                    game.disconnected_at[requested_color] = None
                    color = requested_color

                if color in ("white", "red"):
                    game.disconnected_at[color] = None
                self._start_clock_if_ready(game)
                return game, {
                    "player_id": player_id,
                    "color": profile["color"],
                    "nickname": profile["nickname"],
                    "city": profile["city"],
                    "profile_id": profile.get("profile_id"),
                }

            assigned_color: Player | None = None
            choices: list[Player]
            if preferred_color == "red":
                choices = ["red", "white"]
            elif preferred_color == "white":
                choices = ["white", "red"]
            else:
                choices = ["white", "red"]

            for color in choices:
                if game.seats[color] is None:
                    assigned_color = color
                    break

            new_player_id = uuid4().hex[:12]

            if assigned_color is not None:
                game.seats[assigned_color] = new_player_id

            game.profiles[new_player_id] = {
                "nickname": nickname or "Guest",
                "city": city,
                "color": assigned_color,
                "profile_id": profile_id,
            }
            if assigned_color is not None:
                game.disconnected_at[assigned_color] = None

            self._start_clock_if_ready(game)

            return game, {
                "player_id": new_player_id,
                "color": assigned_color,
                "nickname": game.profiles[new_player_id]["nickname"],
                "city": game.profiles[new_player_id]["city"],
                "profile_id": profile_id,
            }

    def current_candidate_moves(self, game_id: str) -> list[dict]:
        with self._lock:
            game = self._games.get(game_id)
            if game is None:
                return []

            self._sync_clock(game)
            if game.winner is not None:
                return []

            if game.forced_piece is not None:
                row, col = game.forced_piece
                return moves_for_piece(game.board, row, col, game.turn, True)

            return all_moves(game.board, game.turn)

    def is_ai_turn(self, game_id: str) -> bool:
        with self._lock:
            game = self._games.get(game_id)
            if game is None:
                return False

            self._sync_clock(game)
            return game.mode == "vs_ai" and game.ai_color == game.turn and game.winner is None

    def serialize_game(self, game: GameState) -> dict:
        with self._lock:
            self._sync_clock(game)
            legal_moves = [] if game.winner is not None else all_moves(game.board, game.turn)

            players_public: dict[str, dict | None] = {"white": None, "red": None}
            for color in ("white", "red"):
                player_id = game.seats[color]
                if player_id is None:
                    continue

                profile = game.profiles.get(player_id, {})
                players_public[color] = {
                    "player_id": player_id,
                    "nickname": profile.get("nickname"),
                    "city": profile.get("city"),
                    "color": color,
                    "profile_id": profile.get("profile_id"),
                }

            active_deadline_at = None
            if game.clock_enabled and game.last_turn_started_at and game.winner is None and self._is_clock_ready(game):
                turn_ms = game.white_time_ms if game.turn == "white" else game.red_time_ms
                if turn_ms is not None:
                    active_deadline_at = game.last_turn_started_at + timedelta(milliseconds=turn_ms)

            return {
                "game_id": game.game_id,
                "board": game.board,
                "turn": game.turn,
                "winner": game.winner,
                "forced_piece": list(game.forced_piece) if game.forced_piece else None,
                "mode": game.mode,
                "ai_elo": game.ai_elo,
                "ai_color": game.ai_color,
                "ranked": game.ranked,
                "season_key": game.season_key,
                "time_control_minutes": game.time_control_minutes,
                "clock_enabled": game.clock_enabled,
                "white_time_ms": game.white_time_ms,
                "red_time_ms": game.red_time_ms,
                "active_deadline_at": active_deadline_at,
                "winner_reason": game.winner_reason,
                "players": players_public,
                "legal_moves": [
                    {
                        "from": [move["from_"][0], move["from_"][1]],
                        "to": [move["to"][0], move["to"][1]],
                        "capture": [move["capture"][0], move["capture"][1]] if move["capture"] else None,
                    }
                    for move in legal_moves
                ],
                "move_history": game.move_history,
            }

    def apply_player_move(
        self,
        game_id: str,
        from_pos: tuple[int, int],
        to_pos: tuple[int, int],
        player_id: str,
    ) -> GameState:
        game, _, _, _ = self.apply_player_move_detailed(game_id, from_pos, to_pos, player_id)
        return game

    def apply_player_move_detailed(
        self,
        game_id: str,
        from_pos: tuple[int, int],
        to_pos: tuple[int, int],
        player_id: str,
    ) -> tuple[GameState, dict, list[dict], list[list[Piece | None]]]:
        with self._lock:
            game = self._games.get(game_id)
            if game is None:
                raise KeyError("Game not found")

            self._sync_clock(game)

            board_before = deepcopy(game.board)

            profile = game.profiles.get(player_id)
            if profile is None:
                raise ValueError("Unknown player")

            player_color: Player | None = profile.get("color")  # type: ignore[assignment]
            if player_color is None:
                raise ValueError("Spectators cannot make moves")

            if player_color != game.turn:
                raise ValueError("It is not your turn")

            if game.winner is not None:
                raise ValueError("Game already finished")

            if game.forced_piece is not None and game.forced_piece != from_pos:
                raise ValueError("Must continue capture with the same piece")

            candidate_moves = (
                moves_for_piece(game.board, from_pos[0], from_pos[1], game.turn, True)
                if game.forced_piece
                else all_moves(game.board, game.turn)
            )

            candidate_moves_before = [
                {
                    "from_": move["from_"],
                    "to": move["to"],
                    "capture": move["capture"],
                }
                for move in candidate_moves
            ]

            selected_move = None
            for move in candidate_moves:
                if move["from_"] == from_pos and move["to"] == to_pos:
                    selected_move = move
                    break

            if selected_move is None:
                raise ValueError("Illegal move")

            self._apply_selected_move(game, selected_move, to_pos)
            return game, selected_move, candidate_moves_before, board_before

    def apply_system_move(
        self,
        game_id: str,
        from_pos: tuple[int, int],
        to_pos: tuple[int, int],
        expected_color: Player,
    ) -> GameState:
        with self._lock:
            game = self._games.get(game_id)
            if game is None:
                raise KeyError("Game not found")

            self._sync_clock(game)

            if game.winner is not None:
                raise ValueError("Game already finished")

            if game.turn != expected_color:
                raise ValueError("It is not this side's turn")

            if game.forced_piece is not None and game.forced_piece != from_pos:
                raise ValueError("Must continue capture with the same piece")

            candidate_moves = (
                moves_for_piece(game.board, from_pos[0], from_pos[1], game.turn, True)
                if game.forced_piece
                else all_moves(game.board, game.turn)
            )

            selected_move = None
            for move in candidate_moves:
                if move["from_"] == from_pos and move["to"] == to_pos:
                    selected_move = move
                    break

            if selected_move is None:
                raise ValueError("Illegal move")

            self._apply_selected_move(game, selected_move, to_pos)
            return game

    def undo_last_training_turn(self, game_id: str, player_id: str) -> GameState:
        with self._lock:
            game = self._games.get(game_id)
            if game is None:
                raise KeyError("Game not found")

            profile = game.profiles.get(player_id)
            if profile is None:
                raise ValueError("Unknown player")

            if game.mode not in {"vs_ai", "training"}:
                raise ValueError("Undo is allowed only in training mode")

            if not game.move_history:
                raise ValueError("No moves to undo")

            rewind_count = 1
            if game.mode == "vs_ai" and game.move_history[-1].get("by_ai"):
                rewind_count = 2 if len(game.move_history) >= 2 else 1

            next_history = deepcopy(game.move_history[:-rewind_count])
            self._rebuild_from_history(game, next_history)
            return game

    def _apply_selected_move(self, game: GameState, selected_move: dict, to_pos: tuple[int, int]) -> None:
        mover = game.turn
        game.board = apply_move(game.board, selected_move)

        game.move_history.append(
            {
                "player": mover,
                "by_ai": game.mode == "vs_ai" and game.ai_color == mover,
                "from": [selected_move["from_"][0], selected_move["from_"][1]],
                "to": [selected_move["to"][0], selected_move["to"][1]],
                "capture": [selected_move["capture"][0], selected_move["capture"][1]] if selected_move["capture"] else None,
            }
        )

        if selected_move["capture"] is not None:
            continuation = moves_for_piece(game.board, to_pos[0], to_pos[1], game.turn, True)
            if continuation:
                game.forced_piece = to_pos
                return

        game.forced_piece = None
        next_turn: Player = "red" if game.turn == "white" else "white"
        game.winner = detect_winner(game.board, next_turn)
        game.winner_reason = "normal" if game.winner is not None else None
        game.turn = next_turn
        if game.clock_enabled and game.winner is None:
            game.last_turn_started_at = datetime.utcnow()

    def _rebuild_from_history(self, game: GameState, move_history: list[dict]) -> None:
        game.board = create_initial_board()
        game.turn = "white"
        game.winner = None
        game.winner_reason = None
        game.forced_piece = None
        game.result_recorded = False
        game.move_history = []

        for entry in move_history:
            from_pos = tuple(entry.get("from", [0, 0]))
            to_pos = tuple(entry.get("to", [0, 0]))
            capture = tuple(entry["capture"]) if entry.get("capture") is not None else None
            selected_move = {
                "from_": from_pos,
                "to": to_pos,
                "capture": capture,
            }
            self._apply_selected_move(game, selected_move, to_pos)

    def consume_finished_summary(self, game_id: str) -> dict | None:
        with self._lock:
            game = self._games.get(game_id)
            if game is None or game.winner is None or game.result_recorded:
                return None

            winner_id = game.seats.get(game.winner)
            loser_color: Player = "red" if game.winner == "white" else "white"
            loser_id = game.seats.get(loser_color)

            winner_city = game.profiles.get(winner_id, {}).get("city") if winner_id else None
            loser_city = game.profiles.get(loser_id, {}).get("city") if loser_id else None

            game.result_recorded = True
            return {
                "game_id": game.game_id,
                "mode": game.mode,
                "winner": game.winner,
                "ai_elo": game.ai_elo,
                "ai_color": game.ai_color,
                "ranked": game.ranked,
                "season_key": game.season_key,
                "time_control_minutes": game.time_control_minutes,
                "winner_reason": game.winner_reason,
                "players": {
                    "white": self._public_profile(game, "white"),
                    "red": self._public_profile(game, "red"),
                },
                "move_history": deepcopy(game.move_history),
                "winner_city": winner_city,
                "loser_city": loser_city,
                "created_at": game.created_at,
                "finished_at": datetime.utcnow(),
            }

    def _public_profile(self, game: GameState, color: Player) -> dict[str, str | None]:
        player_id = game.seats.get(color)
        profile = game.profiles.get(player_id or "", {})
        return {
            "nickname": profile.get("nickname"),
            "city": profile.get("city"),
            "profile_id": profile.get("profile_id"),
        }

    def mark_player_connected(self, game_id: str, player_id: str) -> None:
        with self._lock:
            game = self._games.get(game_id)
            if game is None:
                return

            profile = game.profiles.get(player_id)
            color = profile.get("color") if profile else None
            if color in ("white", "red"):
                game.disconnected_at[color] = None

    def mark_player_disconnected(self, game_id: str, player_id: str) -> None:
        with self._lock:
            game = self._games.get(game_id)
            if game is None or game.winner is not None:
                return

            profile = game.profiles.get(player_id)
            color = profile.get("color") if profile else None
            if color in ("white", "red"):
                game.disconnected_at[color] = datetime.utcnow()

    def forfeit_if_still_disconnected(self, game_id: str, player_id: str, grace_seconds: int = 20) -> bool:
        with self._lock:
            game = self._games.get(game_id)
            if game is None or game.winner is not None:
                return False

            profile = game.profiles.get(player_id)
            color = profile.get("color") if profile else None
            if color not in ("white", "red"):
                return False

            disconnected_at = game.disconnected_at[color]
            if disconnected_at is None:
                return False

            elapsed = (datetime.utcnow() - disconnected_at).total_seconds()
            if elapsed < grace_seconds:
                return False

            winner: Player = "red" if color == "white" else "white"
            game.winner = winner
            game.winner_reason = "abandon"
            game.forced_piece = None
            return True

    def _sync_clock(self, game: GameState) -> None:
        if not game.clock_enabled or game.winner is not None or game.last_turn_started_at is None:
            return

        # In private rooms, keep timer paused until both players are seated.
        if not self._is_clock_ready(game):
            game.last_turn_started_at = None
            return

        now = datetime.utcnow()
        elapsed_ms = int((now - game.last_turn_started_at).total_seconds() * 1000)
        if elapsed_ms <= 0:
            return

        if game.turn == "white":
            current = game.white_time_ms or 0
            remaining = current - elapsed_ms
            game.white_time_ms = max(0, remaining)
            if remaining <= 0:
                game.winner = "red"
                game.winner_reason = "timeout"
                game.forced_piece = None
        else:
            current = game.red_time_ms or 0
            remaining = current - elapsed_ms
            game.red_time_ms = max(0, remaining)
            if remaining <= 0:
                game.winner = "white"
                game.winner_reason = "timeout"
                game.forced_piece = None

        game.last_turn_started_at = now

    def current_season_key(self) -> str:
        now = datetime.utcnow()
        half = 1 if now.month <= 6 else 2
        return f"{now.year}-S{half}"


store = GameStore()
