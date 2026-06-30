"""Shared FastAPI auth dependencies.

These bridge a GoTrue (Supabase Auth) bearer token to the request handlers:

* ``get_current_user`` validates the ``Authorization: Bearer <jwt>`` header and
  returns the caller's identity (raising 401 when the token is missing/invalid).
* ``get_authed_supabase`` yields a Supabase client carrying that JWT, so any RPC
  it runs executes **as the user** and ``auth.uid()`` is populated in Postgres.

The cached anon client from ``supabase_client`` must NOT be reused for this: it is
shared across the threadpool, and mutating its auth token per request would race.
A fresh client is created per authenticated request instead.
"""

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from supabase import Client, create_client

from app.config import get_settings
from app.supabase_client import get_supabase


@dataclass
class CurrentUser:
    """The authenticated caller, resolved from a validated GoTrue JWT."""

    id: str
    access_token: str


def _bearer_token(authorization: str | None) -> str:
    """Extract the raw JWT from an ``Authorization: Bearer <jwt>`` header."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing bearer token",
        )
    token = authorization[len("bearer ") :].strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing bearer token",
        )
    return token


def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
) -> CurrentUser:
    """Validate the bearer token via GoTrue and return the caller's identity."""
    token = _bearer_token(authorization)
    try:
        response = get_supabase().auth.get_user(token)
    except Exception as exc:  # gotrue raises on invalid/expired/revoked tokens
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or expired token",
        ) from exc
    user = getattr(response, "user", None)
    if user is None or not getattr(user, "id", None):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or expired token",
        )
    return CurrentUser(id=str(user.id), access_token=token)


def get_authed_supabase(
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> Client:
    """Return a Supabase client whose requests run as the authenticated user.

    Applying the JWT to PostgREST means ``auth.uid()`` resolves inside the
    booking/review RPCs, which is what scopes every lock/booking to its owner.
    """
    settings = get_settings()
    client = create_client(settings.supabase_url, settings.supabase_key)
    client.postgrest.auth(user.access_token)
    return client
