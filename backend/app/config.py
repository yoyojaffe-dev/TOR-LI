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
    supabase_key: str  # anon key (public read paths, RLS-guarded RPCs)
    supabase_service_role_key: str = ""  # bypasses RLS; background agents only
    # Optional: the project's JWT signing secret. Unset by default — the auth
    # dependency validates tokens by calling GoTrue (auth.get_user). Set this only
    # if/when switching to faster local HS256 verification without a network hop.
    supabase_jwt_secret: str = ""

    # --- External integrations ---
    google_maps_api_key: str = ""
    openai_api_key: str = ""
    payment_api_key: str = "mock_key_for_now"

    # --- Twilio (notifications only) ---
    # NOTE: client SMS-OTP login does NOT read these. Phone OTP runs through
    # Supabase Auth, whose Twilio credentials live in the Supabase dashboard
    # (Auth > Phone provider) and never touch this process. These fields are for
    # the separate, parked SMS-confirmation feature.
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""

    # --- Server ---
    environment: str = "development"
    port: int = 8000
    # Comma-separated allowed CORS origins. "*" (default) = open, for local dev.
    # In production set CORS_ALLOW_ORIGINS to the deployed frontend origin(s),
    # e.g. "https://app.tor-li.co.il".
    cors_allow_origins: str = "*"

    # --- Booking ---
    # Pessimistic lock window: the slot is held for the booker (and blocked for
    # everyone else) while they complete checkout. 5 min matches the Stitch UX.
    slot_lock_ttl_seconds: int = 300
    # Kill-switch for the Booking Agent's final submit click. False (default) =
    # the agent fills the form but skips the submit click (dry run) — no real
    # appointment is made. Set BOOKING_LIVE=true only once the form-mapping has
    # been validated against real sites, since a live submit is irreversible.
    booking_live: bool = False

    # --- Agents ---
    # When True, the FastAPI lifespan launches the Scraping loop as a background
    # task on boot. Off by default — agents bill Google/OpenAI continuously.
    agents_autostart: bool = False


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (single read of the environment)."""
    return Settings()
