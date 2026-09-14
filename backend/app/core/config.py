import json

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://tutoros:tutoros@localhost:5432/tutoros"
    redis_url: str = "redis://localhost:6379/0"

    @field_validator("database_url", mode="before")
    @classmethod
    def _normalize_database_url(cls, v: str) -> str:
        # Managed Postgres providers (Render, Heroku, Railway) hand back a
        # plain postgres://... or postgresql://... connection string -- our
        # SQLAlchemy engine needs the psycopg driver named explicitly. Lets
        # you paste their connection string directly with no manual editing.
        if v.startswith("postgres://"):
            v = "postgresql://" + v[len("postgres://") :]
        if v.startswith("postgresql://"):
            v = "postgresql+psycopg://" + v[len("postgresql://") :]
        return v

    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24

    # Read as a plain string (not list[str]) so pydantic-settings never tries
    # to JSON-decode it itself -- `cors_origins` below accepts EITHER a JSON
    # array (the .env file's own format, e.g. ["http://localhost:3000"]) OR a
    # plain comma-separated string (easier to paste into a host's env var UI,
    # e.g. Render/Vercel), with no manual reformatting needed either way.
    cors_origins_raw: str = Field(default='["http://localhost:3000"]', alias="CORS_ORIGINS")

    @property
    def cors_origins(self) -> list[str]:
        raw = self.cors_origins_raw.strip()
        if raw.startswith("["):
            return json.loads(raw)
        return [origin.strip() for origin in raw.split(",") if origin.strip()]

    log_level: str = "INFO"

    storage_backend: str = "local"
    upload_dir: str = "./uploads"
    max_upload_size_bytes: int = 10 * 1024 * 1024

    # Only used when storage_backend == "s3" (an S3-compatible endpoint, e.g.
    # the MinIO container in docker-compose.yml, or real AWS S3/R2 in prod).
    s3_endpoint_url: str | None = "http://localhost:9000"
    s3_access_key: str = "tutoros"
    s3_secret_key: str = "tutoros123"
    s3_bucket: str = "tutoros-uploads"
    s3_region: str = "us-east-1"

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

    # No default: AI features raise a clear error at call time (not at import
    # time) if this isn't set, rather than silently using a placeholder key.
    anthropic_api_key: str | None = None
    ai_model: str = "claude-sonnet-5"

    # A topic is "weak" (spec section 19) when mastery_score is below this.
    # Matches the "Needs Improvement"/"Critical" boundary from section 17's bands.
    weak_topic_mastery_threshold: float = 60.0

    # Default easy/medium/hard mix for a generated practice set (section 19's
    # own example). The generate-practice endpoint can override these per call.
    practice_set_easy_count: int = 5
    practice_set_medium_count: int = 3
    practice_set_hard_count: int = 2

    # Rate limit for expensive AI-backed endpoints (question generation, PDF
    # extraction, regeneration, insights, practice generation) -- per user,
    # per minute. See app/core/rate_limit.py.
    ai_rate_limit_per_minute: int = 10

    # How long a teacher-generated parent/student link invite code stays valid.
    link_invite_code_expiry_hours: int = 24

    # Google Sign-In (OpenID Connect). No defaults for the client id/secret --
    # Google auth raises a clear error at call time if these aren't set, same
    # pattern as anthropic_api_key. Never commit real values; see .env.example.
    google_client_id: str | None = None
    google_client_secret: str | None = None
    # Must exactly match a redirect URI registered in the Google Cloud Console
    # for this OAuth client, including scheme/host/port/path.
    google_redirect_uri: str = "http://localhost:8050/auth/google/callback"
    # Where browser-redirect steps of the OAuth flow (success, error, choose-role)
    # send the user back to. The SPA's origin, not the API's.
    frontend_url: str = "http://localhost:3000"
    # How long the signed OAuth `state` (CSRF nonce) and the pending-signup
    # token stay valid -- both are single-use, short-lived by design.
    google_oauth_state_expire_minutes: int = 10

    # Rate limit for unauthenticated auth endpoints particularly exposed to
    # abuse (currently just the Google OAuth callback) -- per source IP, per
    # minute. See app/core/rate_limit.py::rate_limit_by_ip.
    auth_rate_limit_per_minute: int = 20


settings = Settings()
