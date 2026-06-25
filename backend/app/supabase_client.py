"""Singleton Supabase client.

Acts as the shared "message board" all three agents and the API read from and
write to. The client is created lazily and cached so the whole process reuses a
single connection pool.
"""

from functools import lru_cache

from supabase import Client, create_client

from app.config import get_settings


@lru_cache
def get_supabase() -> Client:
    """Return a cached Supabase client built from settings.

    Note: this uses the configured key from ``.env``. The anon key is fine for
    read paths and RLS-guarded RPCs; the background agents that write directly
    should later be switched to a service-role key.
    """
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_key)
