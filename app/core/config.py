from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_ignore_empty=True,
    )

    app_name: str = "Couple API"
    app_version: str = "0.1.0"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    api_server_url: str = ""

    database_url: str = "postgresql+asyncpg://couple:couple@localhost:5432/couple"

    jwt_secret: str = "dev-secret-change-me-with-at-least-32-bytes"
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 30
    refresh_token_ttl_days: int = 30
    oauth_state_ttl_minutes: int = 10

    fernet_key: str = ""

    google_client_id: str = ""
    google_client_secret: str = ""
    google_oauth_redirect_uri: str = "http://localhost:8000/api/v1/google/callback"
    google_calendar_api_base: str = "https://www.googleapis.com/calendar/v3"
    frontend_redirect_url: str = "http://localhost:3000/google/callback"

    invitation_ttl_days: int = 7

    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
