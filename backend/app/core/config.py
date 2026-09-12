from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://tutoros:tutoros@localhost:5432/tutoros"
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24

    cors_origins: list[str] = ["http://localhost:3000"]

    log_level: str = "INFO"

    storage_backend: str = "local"
    upload_dir: str = "./uploads"
    max_upload_size_bytes: int = 10 * 1024 * 1024

    # Mastery formula weights (section 17 of the product spec). Must sum to 1.0.
    mastery_weight_recent: float = 0.4
    mastery_weight_historical: float = 0.3
    mastery_weight_difficulty_adjusted: float = 0.2
    mastery_weight_consistency: float = 0.1

    # Number of most-recent attempts (per student per topic) treated as "recent"
    # for the recent/historical split and for trend detection. See docs/analytics.md.
    analytics_recent_window: int = 3
    # Minimum recent-vs-historical accuracy delta (as a fraction, e.g. 0.05 = 5
    # percentage points) to call a trend "improving"/"declining" rather than "stable".
    analytics_trend_threshold: float = 0.05


settings = Settings()
