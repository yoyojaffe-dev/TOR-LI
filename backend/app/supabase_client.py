"""Singleton Supabase client.

Acts as the shared "message board" all three agents and the API read from and
write to. The client is created lazily and cached so the whole process reuses a
single connection pool.
"""

from functools import lru_cache
from typing import Any

from supabase import Client, create_client

from app.config import get_settings

# A decoded JSON object row as returned by PostgREST/Supabase.
Row = dict[str, Any]


def one_row(data: Any) -> Row:
    """Normalise a Supabase ``execute().data`` payload to a single row dict.

    PostgREST returns either a list of rows or a bare object depending on the
    call; RPCs that ``returns table`` yield a list. This collapses both to one
    dict (empty dict when there is no data), giving callers a typed ``.get``.

    Args:
        data: The raw ``response.data`` value (loosely typed by the SDK).

    Returns:
        The first row as a dict, or an empty dict.
    """
    if isinstance(data, list):
        return data[0] if data else {}
    return data if isinstance(data, dict) else {}


def all_rows(data: Any) -> list[Row]:
    """Normalise a Supabase ``execute().data`` payload to a list of row dicts.

    Args:
        data: The raw ``response.data`` value (loosely typed by the SDK).

    Returns:
        A list of row dicts (empty when there is no data).
    """
    if isinstance(data, list):
        return [r for r in data if isinstance(r, dict)]
    return [data] if isinstance(data, dict) else []


@lru_cache
def get_supabase() -> Client:
    """Return a cached anon Supabase client.

    Uses the anon key — fine for public read paths and RLS-guarded RPCs. This is
    what the API request handlers use.
    """
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_key)


@lru_cache
def get_supabase_admin() -> Client:
    """Return a cached service-role Supabase client.

    Uses the service-role key, which **bypasses RLS**. Restricted to trusted
    server-side background agents (Discovery/Scraping/Booking) that write
    directly to the tables. Never expose this client or its key to clients.
    """
    settings = get_settings()
    if not settings.supabase_service_role_key:
        raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY is not set; admin client unavailable.")
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


# Eagerly accessible singletons for callers that prefer a module-level handle.
# `supabase_admin` is lazy: it is only constructed on first attribute use via a
# proxy so importing this module never fails when the service-role key is absent.
class _LazyAdminProxy:
    """Defers admin client creation until first use."""

    def __getattr__(self, name: str) -> Any:
        return getattr(get_supabase_admin(), name)


supabase_admin = _LazyAdminProxy()
