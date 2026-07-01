"""Unit tests for the nationwide discovery grid city selection (pure logic)."""

from scripts.run_national_discovery import CITIES, _select_cities


def test_grid_covers_ten_core_cities() -> None:
    # The grid has since grown beyond these; assert the original 10 core
    # cities remain a subset of the current grid rather than an exact match.
    core_cities = {
        "kiryat_shmona",
        "tiberias",
        "tel_aviv",
        "jerusalem",
        "haifa",
        "beer_sheva",
        "rishon_lezion",
        "ashdod",
        "netanya",
        "eilat",
    }
    keys = {c["key"] for c in CITIES}
    assert core_cities <= keys


def test_select_none_returns_all_cities() -> None:
    assert _select_cities(None) == CITIES


def test_select_empty_string_returns_all_cities() -> None:
    assert _select_cities("") == CITIES


def test_select_subset_by_key() -> None:
    selected = _select_cities("haifa,eilat")
    assert {c["key"] for c in selected} == {"haifa", "eilat"}


def test_select_is_case_and_whitespace_insensitive() -> None:
    selected = _select_cities(" HAIFA , Eilat ")
    assert {c["key"] for c in selected} == {"haifa", "eilat"}


def test_select_ignores_unknown_keys() -> None:
    # "atlantis" is unknown; only the valid key survives.
    selected = _select_cities("haifa,atlantis")
    assert {c["key"] for c in selected} == {"haifa"}


def test_select_all_unknown_returns_empty() -> None:
    assert _select_cities("atlantis,gotham") == []


def test_every_city_has_valid_coordinates() -> None:
    for c in CITIES:
        assert -90 <= c["lat"] <= 90
        assert -180 <= c["lng"] <= 180
        assert c["name"]
