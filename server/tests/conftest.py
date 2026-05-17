from __future__ import annotations

import os
from pathlib import Path
from tempfile import gettempdir

# Configure a local SQLite database before importing app modules.
TEST_DB_PATH = Path(gettempdir()) / "checkers_test_api.sqlite3"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"
os.environ["BILLING_MOCK_MODE"] = "true"
os.environ["COACH_ENGINE_PROVIDER"] = "heuristic"
os.environ["GOOGLE_OAUTH_CLIENT_ID"] = "test-google-client-id"
os.environ["GOOGLE_OAUTH_CLIENT_SECRET"] = "test-google-client-secret"
os.environ["GOOGLE_OAUTH_REDIRECT_URI"] = "http://localhost:8000/api/auth/google/callback"

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.db import Base, engine

# Ensure model tables are registered in metadata.
from app.models.completed_game import CompletedGame  # noqa: F401
from app.models.daily_puzzle_attempt import DailyPuzzleAttempt  # noqa: F401
from app.models.leaderboard import CityStat  # noqa: F401
from app.models.player_profile import PlayerProfile  # noqa: F401
from app.models.profile_match import ProfileMatch  # noqa: F401
from app.models.puzzle_bank_entry import PuzzleBankEntry  # noqa: F401


@pytest.fixture()
def client() -> TestClient:
    app.router.on_startup.clear()
    app.router.on_shutdown.clear()

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as test_client:
        yield test_client
