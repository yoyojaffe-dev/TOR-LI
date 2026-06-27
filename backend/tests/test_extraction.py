"""Tests for the profile-extraction foundation (models + tool schema + parsers)."""

import pytest
from pydantic import ValidationError

from app.agents.extraction import (
    MIN_CONTENT_LENGTH,
    PROFILE_EXTRACTION_TOOL,
    build_profile_messages,
    external_reviews_from_place,
    filter_reviews,
    is_content_sufficient,
    is_pricing_source,
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


# ── Guards ───────────────────────────────────────────────────────────────────


def test_hard_negative_in_tool_and_prompt() -> None:
    assert "fabricated" in PROFILE_EXTRACTION_TOOL["function"]["description"].lower()
    sys_msg = build_profile_messages("x", "y")[0]["content"].lower()
    assert "never invent" in sys_msg


def test_is_content_sufficient_boundary() -> None:
    assert is_content_sufficient("x" * MIN_CONTENT_LENGTH) is True
    assert is_content_sufficient("x" * (MIN_CONTENT_LENGTH - 1)) is False
    assert is_content_sufficient("  " + "x" * (MIN_CONTENT_LENGTH - 1) + "  ") is False  # stripped


def test_is_pricing_source() -> None:
    assert is_pricing_source("https://book.tor4you.co.il/x") is True
    assert is_pricing_source("https://app.glamera.com/x") is True
    assert is_pricing_source("https://my-barber.example/book") is False
    assert is_pricing_source("https://booksy.com/x") is False  # no static adapter -> not trusted
    assert is_pricing_source(None) is False


def test_filter_reviews_drops_low_quality() -> None:
    reviews = [
        ExternalReview(author="Avi", rating=5, text="Great fade"),  # keep
        ExternalReview(author="Anonymous", rating=5, text="good"),  # drop: generic author
        ExternalReview(author="אנונימי", rating=4, text="טוב"),  # drop: generic (Hebrew)
        ExternalReview(author="Dana", rating=5, text="   "),  # drop: empty text
        ExternalReview(author="Moshe", rating=4, text=None),  # drop: rating only
        ExternalReview(author="A Google user", rating=5, text="ok"),  # drop: generic
        ExternalReview(author=None, rating=5, text="anon"),  # drop: blank author
    ]
    kept = filter_reviews(reviews)
    assert [r.author for r in kept] == ["Avi"]
