from __future__ import annotations

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(settings.database_url, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app.models.analytics_event import AnalyticsEvent
    from app.models.auth_session import AuthSession
    from app.models.auth_token_revocation import AuthTokenRevocation
    from app.models.auth_user import AuthUser
    from app.models.completed_game import CompletedGame
    from app.models.daily_puzzle_attempt import DailyPuzzleAttempt
    from app.models.friendship import Friendship
    from app.models.chat_message import ChatMessage
    from app.models.chat_report import ChatReport
    from app.models.leaderboard import CityStat
    from app.models.profile_match import ProfileMatch
    from app.models.profile_mute import ProfileMute
    from app.models.player_profile import PlayerProfile
    from app.models.puzzle_bank_entry import PuzzleBankEntry
    from app.models.user_achievement import UserAchievement
    from app.models.user_mission import UserMission
    from app.models.user_notification import UserNotification

    Base.metadata.create_all(bind=engine)

    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE player_profiles ADD COLUMN IF NOT EXISTS elo_rating INTEGER NOT NULL DEFAULT 1200"))
        connection.execute(text("ALTER TABLE player_profiles ADD COLUMN IF NOT EXISTS ranked_games INTEGER NOT NULL DEFAULT 0"))
        connection.execute(text("ALTER TABLE player_profiles ADD COLUMN IF NOT EXISTS ranked_wins INTEGER NOT NULL DEFAULT 0"))
        connection.execute(text("ALTER TABLE player_profiles ADD COLUMN IF NOT EXISTS ranked_losses INTEGER NOT NULL DEFAULT 0"))
        connection.execute(text("ALTER TABLE player_profiles ADD COLUMN IF NOT EXISTS season_key VARCHAR(20) NOT NULL DEFAULT '2026-S1'"))
        connection.execute(text("ALTER TABLE player_profiles ADD COLUMN IF NOT EXISTS ranked_placement_remaining INTEGER NOT NULL DEFAULT 10"))
        connection.execute(text("ALTER TABLE player_profiles ADD COLUMN IF NOT EXISTS last_ranked_at TIMESTAMP"))
        connection.execute(text("ALTER TABLE player_profiles ADD COLUMN IF NOT EXISTS last_decay_at TIMESTAMP"))
        connection.execute(text("ALTER TABLE player_profiles ADD COLUMN IF NOT EXISTS pro_active BOOLEAN NOT NULL DEFAULT FALSE"))
        connection.execute(text("ALTER TABLE player_profiles ADD COLUMN IF NOT EXISTS pro_plan VARCHAR(30)"))
        connection.execute(text("ALTER TABLE player_profiles ADD COLUMN IF NOT EXISTS pro_expires_at TIMESTAMP"))
        connection.execute(text("ALTER TABLE player_profiles ADD COLUMN IF NOT EXISTS owned_board_skins JSON NOT NULL DEFAULT '[]'"))
        connection.execute(text("ALTER TABLE player_profiles ADD COLUMN IF NOT EXISTS owned_piece_skins JSON NOT NULL DEFAULT '[]'"))
        connection.execute(text("ALTER TABLE player_profiles ADD COLUMN IF NOT EXISTS equipped_board_skin VARCHAR(30) NOT NULL DEFAULT 'classic'"))
        connection.execute(text("ALTER TABLE player_profiles ADD COLUMN IF NOT EXISTS equipped_piece_skin VARCHAR(30) NOT NULL DEFAULT 'marble'"))

        connection.execute(text("ALTER TABLE completed_games ADD COLUMN IF NOT EXISTS ranked BOOLEAN NOT NULL DEFAULT FALSE"))
        connection.execute(text("ALTER TABLE completed_games ADD COLUMN IF NOT EXISTS season_key VARCHAR(20)"))
        connection.execute(text("ALTER TABLE completed_games ADD COLUMN IF NOT EXISTS winner_reason VARCHAR(20)"))
        connection.execute(text("ALTER TABLE completed_games ADD COLUMN IF NOT EXISTS time_control_minutes INTEGER"))

        connection.execute(text("ALTER TABLE auth_users ADD COLUMN IF NOT EXISTS email_verified BOOLEAN NOT NULL DEFAULT FALSE"))
        connection.execute(text("ALTER TABLE auth_users ADD COLUMN IF NOT EXISTS verification_code VARCHAR(64)"))
        connection.execute(text("ALTER TABLE auth_users ADD COLUMN IF NOT EXISTS reset_code VARCHAR(64)"))
        connection.execute(text("ALTER TABLE auth_users ADD COLUMN IF NOT EXISTS reset_code_expires_at TIMESTAMP"))
        connection.execute(text("ALTER TABLE auth_users ADD COLUMN IF NOT EXISTS social_provider VARCHAR(30)"))
        connection.execute(text("ALTER TABLE auth_users ADD COLUMN IF NOT EXISTS social_provider_user_id VARCHAR(200)"))
        connection.execute(text("ALTER TABLE auth_users ADD COLUMN IF NOT EXISTS social_display_name VARCHAR(120)"))

        connection.execute(text("ALTER TABLE auth_sessions ADD COLUMN IF NOT EXISTS user_agent VARCHAR(300)"))
        connection.execute(text("ALTER TABLE auth_sessions ADD COLUMN IF NOT EXISTS ip_address VARCHAR(64)"))
        connection.execute(text("ALTER TABLE auth_sessions ADD COLUMN IF NOT EXISTS device_label VARCHAR(100)"))
        connection.execute(text("ALTER TABLE auth_sessions ADD COLUMN IF NOT EXISTS revoked BOOLEAN NOT NULL DEFAULT FALSE"))
        connection.execute(text("ALTER TABLE auth_sessions ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMP NOT NULL DEFAULT NOW()"))
