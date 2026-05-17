from __future__ import annotations

import secrets
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.user_mission import UserMission
from app.models.user_achievement import UserAchievement
from app.models.player_profile import PlayerProfile


def issue_daily_missions(profile_id: str) -> list[str]:
    """Issue today's daily missions for a profile."""
    db: Session = next(get_db())
    now = datetime.utcnow()
    tomorrow = now + timedelta(days=1)

    mission_templates = [
        {
            "type": "daily_puzzle",
            "title": "Daily Puzzle Master",
            "description": "Solve 1 daily puzzle",
            "target": 1,
            "reward_xp": 50,
        },
        {
            "type": "game_win",
            "title": "Victory Rush",
            "description": "Win 1 game (any mode)",
            "target": 1,
            "reward_xp": 75,
        },
        {
            "type": "accuracy",
            "title": "Precision Striker",
            "description": "Achieve 80%+ accuracy in 1 game",
            "target": 80,
            "reward_xp": 60,
        },
    ]

    issued_mission_ids = []
    for template in mission_templates:
        mission_id = f"daily_{profile_id}_{secrets.token_hex(4)}"
        mission = UserMission(
            mission_id=mission_id,
            profile_id=profile_id,
            mission_type="daily",
            title=template["title"],
            description=template["description"],
            target_value=template["target"],
            current_value=0,
            reward_xp=template["reward_xp"],
            issued_at=now,
            expires_at=tomorrow,
            mission_metadata={"template_type": template["type"]},
        )
        db.add(mission)
        issued_mission_ids.append(mission_id)

    db.commit()
    return issued_mission_ids


def issue_weekly_missions(profile_id: str) -> list[str]:
    """Issue this week's weekly missions for a profile."""
    db: Session = next(get_db())
    now = datetime.utcnow()
    next_week = now + timedelta(days=7)

    mission_templates = [
        {
            "type": "weekly_games",
            "title": "Weekly Warrior",
            "description": "Play 5 games this week",
            "target": 5,
            "reward_xp": 150,
        },
        {
            "type": "weekly_streak",
            "title": "Streak Keeper",
            "description": "Maintain a 3-game win streak",
            "target": 3,
            "reward_xp": 200,
        },
        {
            "type": "puzzle_rush",
            "title": "Puzzle Rush Champion",
            "description": "Complete 1 Puzzle Rush session",
            "target": 1,
            "reward_xp": 100,
        },
    ]

    issued_mission_ids = []
    for template in mission_templates:
        mission_id = f"weekly_{profile_id}_{secrets.token_hex(4)}"
        mission = UserMission(
            mission_id=mission_id,
            profile_id=profile_id,
            mission_type="weekly",
            title=template["title"],
            description=template["description"],
            target_value=template["target"],
            current_value=0,
            reward_xp=template["reward_xp"],
            issued_at=now,
            expires_at=next_week,
            mission_metadata={"template_type": template["type"]},
        )
        db.add(mission)
        issued_mission_ids.append(mission_id)

    db.commit()
    return issued_mission_ids


def update_mission_progress(profile_id: str, mission_type: str, increment_by: int = 1) -> list[UserMission]:
    """Update progress for missions matching a type."""
    db: Session = next(get_db())
    now = datetime.utcnow()

    active_missions = db.execute(
        select(UserMission).where(
            UserMission.profile_id == profile_id,
            UserMission.completed == False,
            UserMission.expires_at > now,
            UserMission.mission_metadata["template_type"].astext == mission_type,
        )
    ).scalars().all()

    for mission in active_missions:
        mission.current_value = min(mission.current_value + increment_by, mission.target_value)
        if mission.current_value >= mission.target_value and not mission.completed:
            mission.completed = True
            mission.completed_at = now
            award_achievement_for_mission(profile_id, mission)

    db.commit()
    return active_missions


def award_achievement_for_mission(profile_id: str, mission: UserMission) -> UserAchievement | None:
    """Award an achievement badge when a mission is completed."""
    db: Session = next(get_db())

    badge_map = {
        "daily_puzzle": {"icon": "🧩", "tier": 1},
        "game_win": {"icon": "🏆", "tier": 1},
        "accuracy": {"icon": "🎯", "tier": 1},
        "weekly_games": {"icon": "🎮", "tier": 2},
        "weekly_streak": {"icon": "⚡", "tier": 2},
        "puzzle_rush": {"icon": "⏱️", "tier": 2},
    }

    template_type = mission.mission_metadata.get("template_type")
    badge_info = badge_map.get(template_type)

    if not badge_info:
        return None

    achievement_id = f"achievement_{profile_id}_{secrets.token_hex(4)}"
    achievement = UserAchievement(
        achievement_id=achievement_id,
        profile_id=profile_id,
        badge_type=template_type,
        badge_name=mission.title,
        badge_icon=badge_info["icon"],
        description=mission.description,
        tier=badge_info["tier"],
    )
    db.add(achievement)
    db.commit()
    return achievement


def check_streak_at_risk(profile_id: str) -> bool:
    """Check if a profile's streak is at risk (no game in past 48 hours)."""
    # This is a placeholder for streak tracking logic
    # In a real system, you'd query the CompletedGame table for recency
    return False


def get_active_missions(profile_id: str) -> list[dict]:
    """Get all active missions for a profile."""
    db: Session = next(get_db())
    now = datetime.utcnow()

    active = db.execute(
        select(UserMission).where(
            UserMission.profile_id == profile_id,
            UserMission.expires_at > now,
        )
    ).scalars().all()

    return [
        {
            "mission_id": m.mission_id,
            "title": m.title,
            "description": m.description,
            "progress": m.current_value,
            "target": m.target_value,
            "completed": m.completed,
            "reward_xp": m.reward_xp,
            "mission_type": m.mission_type,
            "expires_in_hours": (m.expires_at - now).total_seconds() / 3600,
        }
        for m in active
    ]


def get_achievements(profile_id: str, limit: int = 10) -> list[dict]:
    """Get recent achievements for a profile."""
    db: Session = next(get_db())

    achievements = db.execute(
        select(UserAchievement).where(UserAchievement.profile_id == profile_id).order_by(
            UserAchievement.earned_at.desc()
        ).limit(limit)
    ).scalars().all()

    return [
        {
            "achievement_id": a.achievement_id,
            "badge_type": a.badge_type,
            "badge_name": a.badge_name,
            "badge_icon": a.badge_icon,
            "description": a.description,
            "tier": a.tier,
            "earned_at": a.earned_at.isoformat(),
        }
        for a in achievements
    ]


def check_and_create_streak_notification(profile_id: str, last_game_time: datetime) -> bool:
    """Check if streak is at risk and create notification if needed."""
    from app.models.user_notification import UserNotification
    
    db: Session = next(get_db())
    now = datetime.utcnow()
    hours_since_game = (now - last_game_time).total_seconds() / 3600

    if hours_since_game >= 48:
        notification_id = f"streak_{profile_id}_{secrets.token_hex(4)}"
        notification = UserNotification(
            notification_id=notification_id,
            profile_id=profile_id,
            notification_type="streak_at_risk",
            title="Your Streak Is At Risk!",
            message="You haven't played in 48 hours. Come back to keep your win streak alive!",
            read=False,
        )
        db.add(notification)
        db.commit()
        return True

    return False


def get_pending_notifications(profile_id: str) -> list[dict]:
    """Get unread notifications for a profile."""
    from app.models.user_notification import UserNotification
    
    db: Session = next(get_db())
    notifications = db.execute(
        select(UserNotification).where(
            UserNotification.profile_id == profile_id,
            UserNotification.read == False,
        ).order_by(UserNotification.created_at.desc())
    ).scalars().all()

    return [
        {
            "notification_id": n.notification_id,
            "notification_type": n.notification_type,
            "title": n.title,
            "message": n.message,
            "created_at": n.created_at.isoformat(),
        }
        for n in notifications
    ]


def mark_notification_as_read(notification_id: str) -> bool:
    """Mark a notification as read."""
    from app.models.user_notification import UserNotification
    
    db: Session = next(get_db())
    notification = db.query(UserNotification).filter(
        UserNotification.notification_id == notification_id
    ).first()
    
    if not notification:
        return False
    
    notification.read = True
    db.commit()
    return True

