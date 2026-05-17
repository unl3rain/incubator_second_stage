from pydantic_settings import BaseSettings, SettingsConfigDict


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
    stripe_secret_key: str | None = None
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
    google_oauth_client_id: str | None = None
    google_oauth_client_secret: str | None = None
    google_oauth_redirect_uri: str = "http://localhost:8000/api/auth/google/callback"
    github_oauth_client_id: str | None = None
    github_oauth_client_secret: str | None = None
    github_oauth_redirect_uri: str = "http://localhost:8000/api/auth/github/callback"
    gemini_api_key: str | None = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
