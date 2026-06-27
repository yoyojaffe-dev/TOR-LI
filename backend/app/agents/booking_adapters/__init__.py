"""Per-platform booking adapters.

Recognise the booking platform from the URL and route to a dedicated adapter;
fall back to AI form-mapping for unknown/custom sites.
"""

from app.agents.booking_adapters.base import BookingAdapter, fill_and_submit
from app.agents.booking_adapters.detect import detect_platform, get_adapter
from app.agents.booking_adapters.generic_ai import BOOKING_FORM_TOOL, GenericAIAdapter
from app.agents.booking_adapters.glamera import GlameraAdapter
from app.agents.booking_adapters.tor4you import Tor4YouAdapter

__all__ = [
    "BOOKING_FORM_TOOL",
    "BookingAdapter",
    "GenericAIAdapter",
    "GlameraAdapter",
    "Tor4YouAdapter",
    "detect_platform",
    "fill_and_submit",
    "get_adapter",
]
