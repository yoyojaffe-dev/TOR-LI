"""Booking platform detection + adapter routing.

``detect_platform`` maps a booking URL to a known platform key by domain.
``get_adapter`` returns the matching static adapter, or the generic AI adapter
as the fallback for unknown/custom sites.
"""

from urllib.parse import urlparse

from openai import AsyncOpenAI

from app.agents.booking_adapters.base import BookingAdapter
from app.agents.booking_adapters.generic_ai import GenericAIAdapter
from app.agents.booking_adapters.glamera import GlameraAdapter
from app.agents.booking_adapters.tor4you import Tor4YouAdapter

# Substrings matched against the URL host → platform key. Order doesn't matter
# (hosts are distinct). Keep keys in sync with _REGISTRY below.
_DOMAIN_MARKERS: dict[str, tuple[str, ...]] = {
    "tor4you": ("tor4you.", "tor4u.", "tor-4-you."),
    "glamera": ("glamera.",),
    "booksy": ("booksy.",),
}

# Platforms with a dedicated static adapter. Detected platforms not listed here
# (e.g. "booksy", "custom") fall back to the generic AI adapter.
_REGISTRY: dict[str, type[BookingAdapter]] = {
    "tor4you": Tor4YouAdapter,
    "glamera": GlameraAdapter,
}


def detect_platform(url: str | None) -> str:
    """Return the platform key for ``url`` (``"custom"`` if unrecognised)."""
    if not url:
        return "custom"
    host = (urlparse(url).hostname or "").lower()
    if not host:
        return "custom"
    for platform, markers in _DOMAIN_MARKERS.items():
        if any(marker.rstrip(".") in host for marker in markers):
            return platform
    return "custom"


def get_adapter(url: str | None, openai: AsyncOpenAI) -> BookingAdapter:
    """Return the adapter for ``url`` — static if registered, else AI fallback."""
    platform = detect_platform(url)
    adapter_cls = _REGISTRY.get(platform)
    if adapter_cls is not None:
        return adapter_cls()
    return GenericAIAdapter(openai)
