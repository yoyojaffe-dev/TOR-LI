"""Application configuration loaded from environment / .env.

Values are read from the repo-root ``.env`` (shared with the Supabase CLI and
the frontend). Secrets must never be hard-coded here.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# .env lives at the repository root, one level above /backend.
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    """Typed application settings."""

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Supabase ---
    supabase_url: str
    supabase_key: str

    # --- External integrations ---
    google_maps_api_key: str = ""
    openai_api_key: str = ""
    payment_api_key: str = "mock_key_for_now"

    # --- Twilio (notifications) ---
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""

    # --- Server ---
    environment: str = "development"
    port: int = 8000

    # --- Booking ---
    slot_lock_ttl_seconds: int = 90  # pessimistic lock window (1-2 min per spec)


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (single read of the environment)."""
    return Settings()  # type: ignore[call-arg]
