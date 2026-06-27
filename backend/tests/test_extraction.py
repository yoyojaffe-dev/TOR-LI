"""Tests for the profile-extraction foundation (models + tool schema + parsers)."""

import pytest
from pydantic import ValidationError

from app.agents.extraction import (
    PROFILE_EXTRACTION_TOOL,
    build_profile_messages,
    external_reviews_from_place,
    parse_profile,
)
from app.models.schemas import ExternalReview, ExtractedService, ShopEnrichment

# ── Tool schema ──────────────────────────────────────────────────────────────


def test_profile_extraction_tool_shape() -> None:
    fn = PROFILE_EXTRACTION_TOOL["function"]
    assert fn["name"] == "extract_shop_profile"
    props = fn["parameters"]["properties"]
    assert {"staff", "services", "reviews"} <= props.keys()
    assert fn["parameters"]["required"] == ["staff", "services", "reviews"]


# ── Prompt builder ───────────────────────────────────────────────────────────


def test_build_profile_messages_includes_name_text_and_instruction() -> None:
    msgs = build_profile_messages("מספרת גברים", 'תספורת 60 ש"ח')
    assert msgs[0]["role"] == "system"
    assert "extract_shop_profile" in msgs[0]["content"]
    assert "מספרת גברים" in msgs[1]["content"]
    assert "תספורת 60" in msgs[1]["content"]


# ── parse_profile ────────────────────────────────────────────────────────────


def test_parse_profile_full_payload() -> None:
    args = {
        "staff": [{"name": "יוסי"}, {"name": "דני", "is_active": False}],
        "services": [
            {
                "name": "תספורת",
                "category": "haircut",
                "price": 60,
                "duration_mins": 30,
                "staff_name": "יוסי",
            },
            {"name": "זקן", "category": "beard"},
        ],
        "reviews": [{"author": "אבי", "rating": 5, "text": "מעולה"}],
    }
    result = parse_profile(args)
    assert isinstance(result, ShopEnrichment)
    assert [s.name for s in result.staff] == ["יוסי", "דני"]
    assert result.staff[1].is_active is False
    assert result.services[0].staff_name == "יוסי"
    assert result.services[1].price is None  # shop-level, partial data
    assert result.reviews[0].rating == 5


def test_parse_profile_empty_defaults_to_empty_lists() -> None:
    result = parse_profile({})
    assert result.staff == []
    assert result.services == []
    assert result.reviews == []


def test_parse_profile_rejects_malformed_row() -> None:
    # A service with no name is invalid (name is required).
    with pytest.raises(ValidationError):
        parse_profile({"services": [{"price": 50}]})


# ── external_reviews_from_place ──────────────────────────────────────────────


def test_external_reviews_from_place_maps_google_fields() -> None:
    place = {
        "reviews": [
            {
                "author_name": "Avi",
                "rating": 5,
                "text": "Great fade",
                "relative_time_description": "a week ago",
            },
            {"author_name": "Dana", "rating": 4, "text": "Good"},
        ]
    }
    reviews = external_reviews_from_place(place)
    assert len(reviews) == 2
    assert reviews[0].author == "Avi"
    assert reviews[0].source == "google"
    assert reviews[0].reviewed_at == "a week ago"
    assert reviews[1].rating == 4


def test_external_reviews_from_place_handles_missing_reviews() -> None:
    assert external_reviews_from_place({}) == []
    assert external_reviews_from_place({"reviews": None}) == []


# ── Model validation ─────────────────────────────────────────────────────────


def test_extracted_service_accepts_nulls_for_shop_level() -> None:
    svc = ExtractedService(name="תספורת")
    assert svc.category is None
    assert svc.staff_name is None
    assert svc.duration_mins is None


def test_external_review_rating_bounds() -> None:
    ExternalReview(rating=5)  # ok
    with pytest.raises(ValidationError):
        ExternalReview(rating=9)  # out of 0..5
