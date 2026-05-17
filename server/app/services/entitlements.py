from __future__ import annotations

from datetime import datetime, timedelta

from app.core.db import SessionLocal
from app.models.player_profile import PlayerProfile

FREE_BOARD_SKINS = {"classic"}
PREMIUM_BOARD_SKINS = {"carbon", "sunset", "ocean", "ruby"}
FREE_PIECE_SKINS = {"marble", "wood"}
PREMIUM_PIECE_SKINS = {"neon", "gold", "crystal", "shadow"}


def _normalize_owned_skins(value: list[str] | None, defaults: set[str]) -> list[str]:
    owned = set(value or [])
    owned.update(defaults)
    return sorted(owned)


def ensure_profile_inventory(profile: PlayerProfile) -> None:
    profile.owned_board_skins = _normalize_owned_skins(profile.owned_board_skins, FREE_BOARD_SKINS)
    profile.owned_piece_skins = _normalize_owned_skins(profile.owned_piece_skins, FREE_PIECE_SKINS)

    if profile.pro_active and (profile.pro_expires_at is None or profile.pro_expires_at > datetime.utcnow()):
        profile.owned_board_skins = sorted(set(profile.owned_board_skins).union(PREMIUM_BOARD_SKINS))
        profile.owned_piece_skins = sorted(set(profile.owned_piece_skins).union(PREMIUM_PIECE_SKINS))

    if profile.equipped_board_skin not in set(profile.owned_board_skins):
        profile.equipped_board_skin = "classic"
    if profile.equipped_piece_skin not in set(profile.owned_piece_skins):
        profile.equipped_piece_skin = "marble"


def get_profile_entitlements(profile_id: str) -> dict | None:
    with SessionLocal() as session:
        profile = session.get(PlayerProfile, profile_id)
        if profile is None:
            return None

        if profile.pro_expires_at and profile.pro_expires_at <= datetime.utcnow() and profile.pro_active:
            profile.pro_active = False

        ensure_profile_inventory(profile)
        session.commit()

        return {
            "profile_id": profile.profile_id,
            "pro_active": profile.pro_active,
            "pro_plan": profile.pro_plan,
            "pro_expires_at": profile.pro_expires_at,
            "owned_board_skins": profile.owned_board_skins,
            "owned_piece_skins": profile.owned_piece_skins,
            "equipped_board_skin": profile.equipped_board_skin,
            "equipped_piece_skin": profile.equipped_piece_skin,
        }


def activate_pro_entitlement(profile_id: str, plan: str) -> bool:
    with SessionLocal() as session:
        profile = session.get(PlayerProfile, profile_id)
        if profile is None:
            return False

        now = datetime.utcnow()
        extension = timedelta(days=30 if plan == "pro_monthly" else 365)
        if profile.pro_expires_at and profile.pro_expires_at > now:
            profile.pro_expires_at = profile.pro_expires_at + extension
        else:
            profile.pro_expires_at = now + extension

        profile.pro_active = True
        profile.pro_plan = plan
        ensure_profile_inventory(profile)
        session.commit()
        return True


def equip_skin(profile_id: str, kind: str, skin_id: str) -> dict | None:
    with SessionLocal() as session:
        profile = session.get(PlayerProfile, profile_id)
        if profile is None:
            return None

        if profile.pro_expires_at and profile.pro_expires_at <= datetime.utcnow() and profile.pro_active:
            profile.pro_active = False

        ensure_profile_inventory(profile)

        if kind == "board":
            if skin_id not in set(profile.owned_board_skins):
                raise ValueError("Board skin is not owned by profile")
            profile.equipped_board_skin = skin_id
        elif kind == "piece":
            if skin_id not in set(profile.owned_piece_skins):
                raise ValueError("Piece skin is not owned by profile")
            profile.equipped_piece_skin = skin_id
        else:
            raise ValueError("Unknown skin kind")

        session.commit()
        return {
            "equipped_board_skin": profile.equipped_board_skin,
            "equipped_piece_skin": profile.equipped_piece_skin,
        }
