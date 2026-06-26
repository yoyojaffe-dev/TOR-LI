"""Unit tests for the Supabase row-normalisation helpers + lazy admin proxy."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app import supabase_client
from app.supabase_client import all_rows, one_row

# ── one_row ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "data,expected",
    [
        ([{"a": 1}, {"a": 2}], {"a": 1}),  # list -> first
        ([], {}),  # empty list -> {}
        ({"a": 1}, {"a": 1}),  # bare dict -> itself
        (None, {}),  # None -> {}
        ("oops", {}),  # unexpected scalar -> {}
        (42, {}),
    ],
)
def test_one_row(data: object, expected: dict) -> None:
    assert one_row(data) == expected


# ── all_rows ─────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "data,expected",
    [
        ([{"a": 1}, {"a": 2}], [{"a": 1}, {"a": 2}]),
        ({"a": 1}, [{"a": 1}]),  # bare dict -> single-item list
        (None, []),
        ([], []),
        ([{"a": 1}, "junk", 3], [{"a": 1}]),  # non-dict items filtered out
        ("oops", []),
    ],
)
def test_all_rows(data: object, expected: list) -> None:
    assert all_rows(data) == expected


# ── admin client / lazy proxy ────────────────────────────────────────────────


def test_get_supabase_admin_raises_without_key() -> None:
    supabase_client.get_supabase_admin.cache_clear()
    fake_settings = SimpleNamespace(
        supabase_url="https://x.supabase.co",
        supabase_service_role_key="",  # missing
    )
    with patch.object(supabase_client, "get_settings", return_value=fake_settings):
        with pytest.raises(RuntimeError, match="SUPABASE_SERVICE_ROLE_KEY"):
            supabase_client.get_supabase_admin()
    supabase_client.get_supabase_admin.cache_clear()


def test_lazy_admin_proxy_delegates_attribute_access() -> None:
    sentinel = SimpleNamespace(table=lambda name: f"table:{name}")
    with patch.object(supabase_client, "get_supabase_admin", return_value=sentinel):
        # __getattr__ forwards to the underlying admin client.
        assert supabase_client.supabase_admin.table("barbershops") == "table:barbershops"
