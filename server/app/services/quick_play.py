from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from threading import Lock
from uuid import uuid4

from app.domain.checkers import Player
from app.services.game_store import store


WAITING_TICKET_TTL_SECONDS = 180


@dataclass
class QueueEntry:
    ticket_id: str
    player_id: str
    nickname: str
    city: str | None
    preferred_color: Player | None
    profile_id: str | None
    ranked: bool
    time_control_minutes: int
    enqueued_at: datetime
    status: str = "waiting"
    game_id: str | None = None
    color: Player | None = None
    opponent_nickname: str | None = None


class QuickPlayQueue:
    def __init__(self) -> None:
        self._entries: dict[str, QueueEntry] = {}
        self._lock = Lock()

    def enqueue(
        self,
        nickname: str,
        city: str | None,
        preferred_color: Player | None,
        profile_id: str | None,
        ranked: bool,
        time_control_minutes: int,
    ) -> dict:
        with self._lock:
            self._prune_waiting_locked()

            # Return existing waiting ticket for this profile instead of enqueuing duplicates.
            if profile_id:
                for existing in self._entries.values():
                    if existing.status == "waiting" and existing.profile_id == profile_id:
                        return self._serialize(existing)

            entry = QueueEntry(
                ticket_id=uuid4().hex[:12],
                player_id=uuid4().hex[:12],
                nickname=nickname,
                city=city,
                preferred_color=preferred_color,
                profile_id=profile_id,
                ranked=ranked,
                time_control_minutes=time_control_minutes,
                enqueued_at=datetime.utcnow(),
            )

            for other in self._entries.values():
                if other.status != "waiting":
                    continue
                if other.ticket_id == entry.ticket_id:
                    continue
                if profile_id and other.profile_id == profile_id:
                    continue
                if other.ranked != entry.ranked:
                    continue
                if other.time_control_minutes != entry.time_control_minutes:
                    continue

                colors = self._choose_colors(entry.preferred_color, other.preferred_color)
                if colors is None:
                    continue

                entry_color, other_color = colors
                game = store.create_game(
                    mode="pvp",
                    ranked=entry.ranked,
                    time_control_minutes=entry.time_control_minutes,
                )

                game, joined_entry = store.join_game(
                    game_id=game.game_id,
                    nickname=entry.nickname,
                    city=entry.city,
                    preferred_color=entry_color,
                    player_id=entry.player_id,
                    profile_id=entry.profile_id,
                )
                _, joined_other = store.join_game(
                    game_id=game.game_id,
                    nickname=other.nickname,
                    city=other.city,
                    preferred_color=other_color,
                    player_id=other.player_id,
                    profile_id=other.profile_id,
                )

                entry.status = "matched"
                entry.game_id = game.game_id
                entry.color = joined_entry["color"]
                entry.opponent_nickname = joined_other["nickname"]

                other.status = "matched"
                other.game_id = game.game_id
                other.color = joined_other["color"]
                other.opponent_nickname = joined_entry["nickname"]

                self._entries[entry.ticket_id] = entry
                return self._serialize(entry)

            self._entries[entry.ticket_id] = entry
            return self._serialize(entry)

    def get_status(self, ticket_id: str) -> dict | None:
        with self._lock:
            self._prune_waiting_locked()

            entry = self._entries.get(ticket_id)
            if entry is None:
                return None

            return self._serialize(entry)

    def cancel(self, ticket_id: str) -> bool:
        with self._lock:
            self._prune_waiting_locked()

            entry = self._entries.get(ticket_id)
            if entry is None:
                return False

            if entry.status != "waiting":
                return False

            del self._entries[ticket_id]
            return True

    def _prune_waiting_locked(self) -> None:
        cutoff = datetime.utcnow() - timedelta(seconds=WAITING_TICKET_TTL_SECONDS)
        expired_ticket_ids = [
            ticket_id
            for ticket_id, entry in self._entries.items()
            if entry.status == "waiting" and entry.enqueued_at < cutoff
        ]

        for ticket_id in expired_ticket_ids:
            del self._entries[ticket_id]

    def _serialize(self, entry: QueueEntry) -> dict:
        game = store.get_game(entry.game_id) if entry.game_id else None
        return {
            "status": entry.status,
            "ticket_id": entry.ticket_id,
            "queue_size": sum(1 for item in self._entries.values() if item.status == "waiting"),
            "game": store.serialize_game(game) if game is not None else None,
            "player_id": entry.player_id if entry.status == "matched" else None,
            "color": entry.color,
            "nickname": entry.nickname,
            "city": entry.city,
            "profile_id": entry.profile_id,
            "opponent_nickname": entry.opponent_nickname,
        }

    def _choose_colors(self, first: Player | None, second: Player | None) -> tuple[Player, Player] | None:
        # Preferences are treated as soft constraints: if both request the same
        # side, still match by assigning opposite colors.
        if first is not None and second is not None and first == second:
            if second == "white":
                return "red", "white"
            return "white", "red"

        if first == "white":
            return "white", "red"
        if first == "red":
            return "red", "white"

        if second == "white":
            return "red", "white"
        if second == "red":
            return "white", "red"

        return "white", "red"


quick_play_queue = QuickPlayQueue()
