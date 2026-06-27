"""Page Object Model for the Tor-li consumer app.

Each page object owns its locators (role/text-based where possible, stable
data-* / id hooks for custom widgets) and exposes intent-level actions. Tests
read as user flows, not selector soup. All waits are web-first (`expect` /
locator state) — no arbitrary `wait_for_timeout`.
"""

from __future__ import annotations

import re

from playwright.sync_api import Locator, Page, expect

# Data loads (radius search, slots) can take a few seconds against the real API.
DATA_TIMEOUT = 15_000


class HomePage:
    def __init__(self, page: Page, base_url: str) -> None:
        self.page = page
        self.base_url = base_url
        self.search = page.get_by_placeholder("חפש ספרים, שירותים...")
        self.filter_button = page.locator("#btn-filter")
        self.location_button = page.locator("#location-btn")
        self.map_toggle = page.get_by_role("button", name="מפה")
        self.list_toggle = page.get_by_role("button", name="רשימה")
        self.shop_cards = page.locator("#barbershop-list [data-id]")
        self.nearby_slots = page.locator("#nearby-slots-list [data-slot-id]")
        self.map = page.locator("#map")
        self.map_preview = page.locator("#map-preview")
        self.eta_cells = page.locator("#mp-eta > div")
        self.nav_from_map = page.locator("#mp-nav")

    def goto(self) -> None:
        self.page.goto(f"{self.base_url}/#/home", wait_until="domcontentloaded")
        expect(self.shop_cards.first).to_be_visible(timeout=DATA_TIMEOUT)

    def open_first_shop(self) -> None:
        self.shop_cards.first.click()

    def filter(self, query: str) -> None:
        self.search.fill(query)

    def open_funnel(self) -> "FunnelSheet":
        self.filter_button.click()
        return FunnelSheet(self.page)

    def show_map(self) -> None:
        self.map_toggle.click()
        expect(self.map).to_be_visible()
        # Markers are populated once the map + shop data are both ready.
        self.page.wait_for_function(
            "() => window.__torli && (window.__torli.store.get().markers || []).length > 0",
            timeout=DATA_TIMEOUT,
        )

    def open_map_preview_for_first_shop(self) -> None:
        # gmaps markers aren't DOM-clickable headless; drive the real handler.
        self.page.evaluate(
            "() => window.__torli.showMapPreview(window.__torli.store.get().barbershops[0])"
        )
        # Preview uses opacity/transform (not display:none), so assert the class
        # that gates interaction is removed rather than relying on visibility.
        expect(self.map_preview).not_to_have_class(re.compile(r"pointer-events-none"))
        expect(self.eta_cells).to_have_count(4, timeout=DATA_TIMEOUT)


class FunnelSheet:
    def __init__(self, page: Page) -> None:
        self.page = page
        self.sheet = page.locator("#filter-sheet")
        self.title = page.get_by_text("מה אתה מחפש?")
        self.apply = page.locator("#filter-apply")

    def pill(self, name: str) -> Locator:
        return self.page.locator(f'.funnel-pill[data-pill="{name}"]')

    def panel(self, name: str) -> Locator:
        return self.page.locator(f'.funnel-panel[data-panel="{name}"]')

    def open_panel(self, name: str) -> None:
        # `hidden` is Tailwind display:none, so visibility is the robust signal.
        self.pill(name).click()
        expect(self.panel(name)).to_be_visible()

    def set_slider(self, slider_id: str, value: str) -> None:
        self.page.eval_on_selector(
            f"#{slider_id}",
            "(el, v) => { el.value = v; el.dispatchEvent(new Event('input')); }",
            value,
        )

    def pick_first_day(self) -> None:
        self.page.locator(".date-chip").first.click()

    def apply_filters(self) -> None:
        self.apply.click()
        expect(self.sheet).to_be_hidden()


class BarberPage:
    def __init__(self, page: Page) -> None:
        self.page = page
        self.view = page.locator("#view-barber")
        self.share_button = page.locator("#bp-share")
        self.nav_button = page.locator("#bp-nav")
        self.slots = page.locator("#bp-services [data-id]")

    def wait_loaded(self) -> None:
        expect(self.view).to_be_visible()
        expect(self.share_button).to_be_visible()

    def open_share(self) -> "ShareSheet":
        self.share_button.click()
        return ShareSheet(self.page)

    def open_nav(self) -> "NavSheet":
        self.nav_button.click()
        return NavSheet(self.page)

    def book_first_slot(self) -> "ConfirmSheet":
        expect(self.slots.first).to_be_visible(timeout=DATA_TIMEOUT)
        self.slots.first.click()
        return ConfirmSheet(self.page)


class ShareSheet:
    def __init__(self, page: Page) -> None:
        self.page = page
        self.title = page.get_by_text("שתף עם חברים")

    def assert_open_with_all_channels(self) -> None:
        expect(self.title).to_be_visible()
        for label in ("WhatsApp", "Instagram", "Facebook", "SMS"):
            expect(self.page.get_by_text(label, exact=True)).to_be_visible()


class NavSheet:
    def __init__(self, page: Page) -> None:
        self.page = page
        self.title = page.get_by_text("מעולה, איך אתה מתכנן להגיע?")

    def assert_open_with_all_modes(self) -> None:
        expect(self.title).to_be_visible()
        for label in ("רגלי", "רכב", "תחבורה ציבורית"):
            expect(self.page.get_by_text(label, exact=True)).to_be_visible()


class ConfirmSheet:
    def __init__(self, page: Page) -> None:
        self.page = page
        self.sheet = page.locator("#confirm-sheet")
        self.terms = page.locator("#cs-terms")
        self.confirm = page.locator("#cs-confirm")

    def wait_open(self) -> None:
        expect(self.sheet).to_be_visible(timeout=DATA_TIMEOUT)

    def accept_and_confirm(self) -> None:
        self.terms.check()
        expect(self.confirm).to_be_enabled()
        self.confirm.click()


class BookingsPage:
    def __init__(self, page: Page, base_url: str) -> None:
        self.page = page
        self.base_url = base_url
        self.list = page.locator("#mb-list")
        self.book_again = page.locator("[data-again-id]")
        self.rate = page.locator("[data-rate-id]")

    def goto(self) -> None:
        self.page.goto(f"{self.base_url}/#/bookings", wait_until="domcontentloaded")
        expect(self.list).to_be_visible(timeout=DATA_TIMEOUT)

    def open_review_for_first(self) -> "ReviewSheet":
        expect(self.rate.first).to_be_visible(timeout=DATA_TIMEOUT)
        self.rate.first.click()
        return ReviewSheet(self.page)


class ReviewSheet:
    def __init__(self, page: Page) -> None:
        self.page = page
        self.stars = page.locator(".rv-star")
        self.comment = page.locator("#rv-comment")
        self.submit = page.locator("#rv-submit")

    def rate(self, stars: int, comment: str) -> None:
        expect(self.stars.first).to_be_visible()
        self.stars.nth(stars - 1).click()
        self.comment.fill(comment)
        expect(self.submit).to_be_enabled()
        self.submit.click()
        # On success the sheet is removed from the DOM.
        expect(self.submit).to_have_count(0, timeout=DATA_TIMEOUT)


class ProfilePage:
    def __init__(self, page: Page, base_url: str) -> None:
        self.page = page
        self.base_url = base_url
        self.avatar = page.locator("#pf-avatar")
        # Scope to the profile avatar (the home header has another avatar slot).
        self.avatar_img = page.locator("#pf-avatar img")
        self.photo_input = page.locator("#ph-input")
        self.pay_row = page.locator("#pf-pay")

    def goto(self) -> None:
        self.page.goto(f"{self.base_url}/#/profile", wait_until="domcontentloaded")
        expect(self.avatar).to_be_visible()

    def upload_photo(self, png_bytes: bytes) -> None:
        self.avatar.click()
        expect(self.photo_input).to_be_attached()
        self.photo_input.set_input_files(
            files=[{"name": "a.png", "mimeType": "image/png", "buffer": png_bytes}]
        )
        expect(self.avatar_img).to_be_visible()

    def select_payment(self, value: str) -> None:
        self.pay_row.click()
        # Role-based: the sheet heading (not the row label / add button with same text).
        expect(self.page.get_by_role("heading", name="אמצעי תשלום")).to_be_visible()
        self.page.locator(f'.pay-opt[data-val="{value}"]').click()
