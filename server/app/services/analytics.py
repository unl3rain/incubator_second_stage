from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import distinct, func, select

from app.core.db import SessionLocal
from app.models.analytics_event import AnalyticsEvent


ALLOWED_EVENTS = {
    "app_opened",
    "game_created",
    "game_joined",
    "first_move_made",
    "game_completed",
    "pro_cta_clicked",
    "checkout_started",
    "checkout_completed",
    "quick_play_enqueued",
    "quick_play_matched",
    "reconnect_started",
    "reconnect_recovered",
}


def track_event(
    event_name: str,
    profile_id: str | None = None,
    game_id: str | None = None,
    source: str = "web",
    properties: dict | None = None,
) -> dict:
    normalized_name = (event_name or "").strip().lower()
    if not normalized_name:
        raise ValueError("event_name is required")
    if normalized_name not in ALLOWED_EVENTS:
        raise ValueError("event_name is not allowed")

    row = AnalyticsEvent(
        event_name=normalized_name,
        profile_id=(profile_id or None),
        game_id=(game_id or None),
        source=(source or "web")[:30],
        properties=properties or {},
    )

    with SessionLocal() as session:
        session.add(row)
        session.commit()
        session.refresh(row)

    return {
        "ok": True,
        "event_id": row.id,
    }


def get_analytics_summary(period_days: int = 14) -> dict:
    days = max(1, min(90, int(period_days)))
    since = datetime.utcnow() - timedelta(days=days)

    with SessionLocal() as session:
        total_events = session.execute(
            select(func.count()).select_from(AnalyticsEvent).where(AnalyticsEvent.created_at >= since)
        ).scalar_one()

        unique_profiles = session.execute(
            select(func.count(distinct(AnalyticsEvent.profile_id)))
            .where(AnalyticsEvent.created_at >= since)
            .where(AnalyticsEvent.profile_id.is_not(None))
        ).scalar_one()

        event_rows = session.execute(
            select(AnalyticsEvent.event_name, func.count())
            .where(AnalyticsEvent.created_at >= since)
            .group_by(AnalyticsEvent.event_name)
            .order_by(func.count().desc())
        ).all()
        event_counts = {name: int(count) for name, count in event_rows}

        day_rows = session.execute(
            select(
                func.date(AnalyticsEvent.created_at).label("day"),
                func.count().label("events"),
                func.count(distinct(AnalyticsEvent.profile_id)).label("profiles"),
            )
            .where(AnalyticsEvent.created_at >= since)
            .group_by(func.date(AnalyticsEvent.created_at))
            .order_by(func.date(AnalyticsEvent.created_at).asc())
        ).all()

    funnel = {
        "app_opened": int(event_counts.get("app_opened", 0)),
        "game_created": int(event_counts.get("game_created", 0)),
        "first_move_made": int(event_counts.get("first_move_made", 0)),
        "game_completed": int(event_counts.get("game_completed", 0)),
        "pro_cta_clicked": int(event_counts.get("pro_cta_clicked", 0)),
        "checkout_started": int(event_counts.get("checkout_started", 0)),
        "checkout_completed": int(event_counts.get("checkout_completed", 0)),
    }

    daily = [
        {
            "date": str(day),
            "events": int(events),
            "unique_profiles": int(profiles),
        }
        for day, events, profiles in day_rows
    ]

    return {
        "period_days": days,
        "total_events": int(total_events),
        "unique_profiles": int(unique_profiles),
        "event_counts": event_counts,
        "funnel": funnel,
        "daily": daily,
    }
