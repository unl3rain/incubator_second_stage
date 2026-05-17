from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import AliasChoices, Field


class Settings(BaseSettings):
    app_name: str = "Checkers API"
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    frontend_origin: str = "http://localhost:5173"
    database_url: str = "postgresql+psycopg://checkers:checkers@localhost:5432/checkers_db"
    coach_engine_provider: str = "py-draughts"
    coach_engine_depth: int = 6
    coach_engine_time_limit: float = 0.25
    stripe_secret_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("STRIPE_SECRET_KEY", "STRIPE_SECRET"),
    )
    stripe_webhook_secret: str | None = None
    stripe_price_pro_monthly: str | None = None
    stripe_price_pro_yearly: str | None = None
    stripe_success_url: str = "http://localhost:5173/?billing=success"
    stripe_cancel_url: str = "http://localhost:5173/?billing=cancel"
    billing_mock_mode: bool = True
    secret_key: str = "dev-secret-key-change-in-production"
    access_token_minutes: int = 30
    refresh_token_days: int = 30
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_use_tls: bool = True
    smtp_from_email: str = "no-reply@checkers.local"
    google_oauth_client_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("GOOGLE_OAUTH_CLIENT_ID", "OAUTH_GOOGLE_CLIENT_ID"),
    )
    google_oauth_client_secret: str | None = Field(
        default=None,
        validation_alias=AliasChoices("GOOGLE_OAUTH_CLIENT_SECRET", "OAUTH_GOOGLE_CLIENT_SECRET"),
    )
    google_oauth_redirect_uri: str = Field(
        default="http://localhost:8000/api/auth/google/callback",
        validation_alias=AliasChoices("GOOGLE_OAUTH_REDIRECT_URI", "OAUTH_GOOGLE_REDIRECT_URI"),
    )
    github_oauth_client_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("GITHUB_OAUTH_CLIENT_ID", "OAUTH_GITHUB_CLIENT_ID"),
    )
    github_oauth_client_secret: str | None = Field(
        default=None,
        validation_alias=AliasChoices("GITHUB_OAUTH_CLIENT_SECRET", "OAUTH_GITHUB_CLIENT_SECRET"),
    )
    github_oauth_redirect_uri: str = Field(
        default="http://localhost:8000/api/auth/github/callback",
        validation_alias=AliasChoices("GITHUB_OAUTH_REDIRECT_URI", "OAUTH_GITHUB_REDIRECT_URI"),
    )
    gemini_api_key: str | None = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
