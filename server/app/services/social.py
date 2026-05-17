from __future__ import annotations

import secrets
from datetime import datetime

from sqlalchemy import and_, or_, select

from app.core.db import SessionLocal
from app.models.auth_user import AuthUser
from app.models.chat_message import ChatMessage
from app.models.chat_report import ChatReport
from app.models.friendship import Friendship
from app.models.player_profile import PlayerProfile
from app.models.profile_mute import ProfileMute
from app.services.game_store import store


def _friend_filter(profile_id: str):
    return or_(
        and_(Friendship.requester_profile_id == profile_id, Friendship.status == "accepted"),
        and_(Friendship.addressee_profile_id == profile_id, Friendship.status == "accepted"),
    )


def get_friends(profile_id: str) -> list[dict]:
    with SessionLocal() as session:
        rows = session.execute(select(Friendship).where(_friend_filter(profile_id))).scalars().all()
        friends: list[dict] = []
        for row in rows:
            friend_profile_id = row.addressee_profile_id if row.requester_profile_id == profile_id else row.requester_profile_id
            profile = session.execute(
                select(PlayerProfile).where(PlayerProfile.profile_id == friend_profile_id)
            ).scalar_one_or_none()
            if profile is None:
                continue
            friends.append(
                {
                    "profile_id": profile.profile_id,
                    "nickname": profile.nickname,
                    "city": profile.city,
                    "status": "accepted",
                    "friendship_id": row.friendship_id,
                    "created_at": row.created_at,
                }
            )
        return sorted(friends, key=lambda item: (item["nickname"] or "").lower())


def get_pending_friend_requests(profile_id: str) -> list[dict]:
    with SessionLocal() as session:
        rows = session.execute(
            select(Friendship).where(
                Friendship.addressee_profile_id == profile_id,
                Friendship.status == "pending",
            )
        ).scalars().all()
        requests: list[dict] = []
        for row in rows:
            requester = session.execute(
                select(PlayerProfile).where(PlayerProfile.profile_id == row.requester_profile_id)
            ).scalar_one_or_none()
            requests.append(
                {
                    "friendship_id": row.friendship_id,
                    "requester_profile_id": row.requester_profile_id,
                    "requester_nickname": requester.nickname if requester else "Unknown",
                    "requester_city": requester.city if requester else None,
                    "created_at": row.created_at,
                }
            )
        return requests


def _resolve_target_profile_id(session, target_identifier: str) -> str | None:
    target_identifier = target_identifier.strip()
    if not target_identifier:
        return None

    profile = session.execute(
        select(PlayerProfile).where(PlayerProfile.profile_id == target_identifier)
    ).scalar_one_or_none()
    if profile is not None:
        return profile.profile_id

    auth_user = session.execute(
        select(AuthUser).where(AuthUser.profile_id == target_identifier)
    ).scalar_one_or_none()
    if auth_user is not None:
        return auth_user.profile_id

    if target_identifier.isdigit():
        auth_user = session.execute(
            select(AuthUser).where(AuthUser.id == int(target_identifier))
        ).scalar_one_or_none()
        if auth_user is not None:
            return auth_user.profile_id

    auth_user = session.execute(
        select(AuthUser).where(AuthUser.social_provider_user_id == target_identifier)
    ).scalar_one_or_none()
    if auth_user is not None:
        return auth_user.profile_id

    return None


def send_friend_request(requester_profile_id: str, target_profile_id: str) -> dict:
    if requester_profile_id == target_profile_id:
        raise ValueError("Cannot add yourself as a friend")

    with SessionLocal() as session:
        resolved_target_profile_id = _resolve_target_profile_id(session, target_profile_id)
        if resolved_target_profile_id is None:
            raise ValueError("Target profile not found")

        if requester_profile_id == resolved_target_profile_id:
            raise ValueError("Cannot add yourself as a friend")

        existing = session.execute(
            select(Friendship).where(
                or_(
                    and_(
                        Friendship.requester_profile_id == requester_profile_id,
                        Friendship.addressee_profile_id == resolved_target_profile_id,
                    ),
                    and_(
                        Friendship.requester_profile_id == resolved_target_profile_id,
                        Friendship.addressee_profile_id == requester_profile_id,
                    ),
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            if existing.status == "accepted":
                raise ValueError("Already friends")
            raise ValueError("Friend request already pending")

        friendship = Friendship(
            friendship_id=f"friend_{secrets.token_hex(8)}",
            requester_profile_id=requester_profile_id,
            addressee_profile_id=resolved_target_profile_id,
            status="pending",
        )
        session.add(friendship)
        session.commit()
        return {
            "friendship_id": friendship.friendship_id,
            "status": friendship.status,
        }


def accept_friend_request(profile_id: str, friendship_id: str) -> bool:
    with SessionLocal() as session:
        row = session.execute(
            select(Friendship).where(
                Friendship.friendship_id == friendship_id,
                Friendship.addressee_profile_id == profile_id,
                Friendship.status == "pending",
            )
        ).scalar_one_or_none()
        if row is None:
            return False

        row.status = "accepted"
        row.accepted_at = datetime.utcnow()
        session.commit()
        return True


def remove_friend(profile_id: str, target_profile_id: str) -> bool:
    with SessionLocal() as session:
        row = session.execute(
            select(Friendship).where(
                or_(
                    and_(
                        Friendship.requester_profile_id == profile_id,
                        Friendship.addressee_profile_id == target_profile_id,
                    ),
                    and_(
                        Friendship.requester_profile_id == target_profile_id,
                        Friendship.addressee_profile_id == profile_id,
                    ),
                ),
                Friendship.status.in_(["accepted", "pending"]),
            )
        ).scalar_one_or_none()
        if row is None:
            return False

        session.delete(row)
        session.commit()
        return True


def list_mutes(profile_id: str) -> list[str]:
    with SessionLocal() as session:
        rows = session.execute(
            select(ProfileMute).where(ProfileMute.profile_id == profile_id)
        ).scalars().all()
        return [row.muted_profile_id for row in rows]


def set_mute(profile_id: str, muted_profile_id: str, muted: bool) -> bool:
    with SessionLocal() as session:
        resolved_target_profile_id = _resolve_target_profile_id(session, muted_profile_id)
        if resolved_target_profile_id is None:
            raise ValueError("Target profile not found")

        if profile_id == resolved_target_profile_id:
            raise ValueError("Cannot mute yourself")

        row = session.execute(
            select(ProfileMute).where(
                ProfileMute.profile_id == profile_id,
                ProfileMute.muted_profile_id == resolved_target_profile_id,
            )
        ).scalar_one_or_none()

        if muted:
            if row is not None:
                return False
            session.add(
                ProfileMute(
                    mute_id=f"mute_{secrets.token_hex(8)}",
                    profile_id=profile_id,
                    muted_profile_id=resolved_target_profile_id,
                )
            )
            session.commit()
            return True

        if row is None:
            return False
        session.delete(row)
        session.commit()
        return True


def _is_participant(game_id: str, profile_id: str) -> bool:
    game = store.get_game(game_id)
    if game is None:
        return False
    for info in game.profiles.values():
        if info.get("profile_id") == profile_id:
            return True
    return False


def list_chat_messages(game_id: str, viewer_profile_id: str | None = None, limit: int = 60) -> list[dict]:
    safe_limit = max(1, min(200, limit))
    muted_ids = set(list_mutes(viewer_profile_id)) if viewer_profile_id else set()

    with SessionLocal() as session:
        rows = session.execute(
            select(ChatMessage).where(ChatMessage.game_id == game_id).order_by(ChatMessage.created_at.desc()).limit(safe_limit)
        ).scalars().all()

        items: list[dict] = []
        for row in reversed(rows):
            if row.sender_profile_id in muted_ids:
                continue
            items.append(
                {
                    "message_id": row.message_id,
                    "game_id": row.game_id,
                    "sender_profile_id": row.sender_profile_id,
                    "sender_nickname": row.sender_nickname,
                    "text": row.text,
                    "message_type": row.message_type,
                    "created_at": row.created_at,
                }
            )
        return items


def create_chat_message(game_id: str, sender_profile_id: str, text: str, message_type: str = "text") -> dict:
    if not _is_participant(game_id, sender_profile_id):
        raise ValueError("Only game participants can chat")

    clean_text = (text or "").strip()
    if not clean_text:
        raise ValueError("Message cannot be empty")
    if len(clean_text) > 500:
        raise ValueError("Message too long")

    if message_type not in {"text", "emoji"}:
        message_type = "text"

    with SessionLocal() as session:
        profile = session.execute(
            select(PlayerProfile).where(PlayerProfile.profile_id == sender_profile_id)
        ).scalar_one_or_none()
        nickname = profile.nickname if profile else "Player"

        message = ChatMessage(
            message_id=f"msg_{secrets.token_hex(8)}",
            game_id=game_id,
            sender_profile_id=sender_profile_id,
            sender_nickname=nickname,
            text=clean_text,
            message_type=message_type,
        )
        session.add(message)
        session.commit()

        return {
            "message_id": message.message_id,
            "game_id": message.game_id,
            "sender_profile_id": message.sender_profile_id,
            "sender_nickname": message.sender_nickname,
            "text": message.text,
            "message_type": message.message_type,
            "created_at": message.created_at,
        }


def report_chat_message(reporter_profile_id: str, message_id: str, reason: str) -> bool:
    clean_reason = (reason or "").strip()
    if not clean_reason:
        raise ValueError("Reason is required")
    if len(clean_reason) > 200:
        raise ValueError("Reason is too long")

    with SessionLocal() as session:
        message = session.execute(
            select(ChatMessage).where(ChatMessage.message_id == message_id)
        ).scalar_one_or_none()
        if message is None:
            return False

        existing = session.execute(
            select(ChatReport).where(
                ChatReport.message_id == message_id,
                ChatReport.reporter_profile_id == reporter_profile_id,
            )
        ).scalar_one_or_none()
        if existing is not None:
            return True

        report = ChatReport(
            report_id=f"report_{secrets.token_hex(8)}",
            message_id=message_id,
            reporter_profile_id=reporter_profile_id,
            reason=clean_reason,
        )
        session.add(report)
        session.commit()
        return True
