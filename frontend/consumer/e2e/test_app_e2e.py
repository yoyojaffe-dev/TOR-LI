"""Full E2E of the Tor-li consumer app, driving real flows in Chromium.

Page Object Model + web-first assertions (auto-waiting, no arbitrary timeouts).
Run: venv/bin/python -m pytest frontend/consumer/e2e -q
"""

import base64

from playwright.sync_api import expect

from conftest import BASE_URL, assert_no_console_errors, shot
from pages import BarberPage, BookingsPage, HomePage, NavSheet, ProfilePage

# 1x1 transparent PNG for the avatar upload test.
PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


def test_home_loads_shops(page) -> None:
    home = HomePage(page, BASE_URL)
    home.goto()
    expect(home.shop_cards.first).to_be_visible()
    assert home.shop_cards.count() > 0
    shot(page, "01-home")
    assert_no_console_errors(page)


def test_search_filters_shops(page) -> None:
    home = HomePage(page, BASE_URL)
    home.goto()
    before = home.shop_cards.count()

    home.filter("zzzznomatch")
    expect(home.shop_cards).to_have_count(0)  # auto-waits for the live filter

    home.filter("")
    expect(home.shop_cards).to_have_count(before)
    assert_no_console_errors(page)


def test_funnel_constraints(page) -> None:
    home = HomePage(page, BASE_URL)
    home.goto()
    funnel = home.open_funnel()
    expect(funnel.title).to_be_visible()

    funnel.open_panel("budget")
    funnel.set_slider("budget-slider", "0")

    funnel.open_panel("rating")
    expect(funnel.panel("budget")).to_be_hidden()  # accordion: one panel at a time
    funnel.set_slider("rating-slider", "4")

    funnel.open_panel("date")
    funnel.pick_first_day()

    shot(page, "02-funnel")
    funnel.apply_filters()
    assert_no_console_errors(page)


def test_map_eta_and_nav(page) -> None:
    home = HomePage(page, BASE_URL)
    home.goto()
    home.show_map()
    home.open_map_preview_for_first_shop()
    shot(page, "03-map-eta")

    home.nav_from_map.click()
    NavSheet(page).assert_open_with_all_modes()
    shot(page, "03b-map-nav")
    assert_no_console_errors(page)


def test_barber_profile_share(page) -> None:
    home = HomePage(page, BASE_URL)
    home.goto()
    home.open_first_shop()
    barber = BarberPage(page)
    barber.wait_loaded()
    shot(page, "04-barber")
    barber.open_share().assert_open_with_all_channels()
    shot(page, "05-share")
    assert_no_console_errors(page)


def test_barber_profile_nav(page) -> None:
    home = HomePage(page, BASE_URL)
    home.goto()
    home.open_first_shop()
    barber = BarberPage(page)
    barber.wait_loaded()
    barber.open_nav().assert_open_with_all_modes()
    shot(page, "06-nav")
    assert_no_console_errors(page)


def test_booking_then_book_again_and_review(page) -> None:
    home = HomePage(page, BASE_URL)
    home.goto()
    home.open_first_shop()

    barber = BarberPage(page)
    barber.wait_loaded()
    confirm = barber.book_first_slot()
    confirm.wait_open()
    confirm.accept_and_confirm()
    expect(page.locator("#view-success")).to_be_visible()
    shot(page, "07-success")

    # The just-booked (past-dated) slot shows as a past appointment.
    bookings = BookingsPage(page, BASE_URL)
    bookings.goto()
    expect(bookings.rate.first).to_be_visible()
    expect(bookings.book_again.first).to_be_visible()
    shot(page, "08-bookings")

    bookings.open_review_for_first().rate(5, "שירות מצוין, בדיקת E2E")
    shot(page, "09-review-submitted")
    assert_no_console_errors(page)


def test_profile_photo_and_payments(page) -> None:
    profile = ProfilePage(page, BASE_URL)
    profile.goto()

    profile.upload_photo(PNG_1PX)
    avatar = page.evaluate("() => localStorage.getItem('torli_avatar')")
    assert avatar and avatar.startswith("data:image")
    shot(page, "10-profile-avatar")

    profile.select_payment("visa")
    expect(page.locator("#toast")).to_be_visible()
    assert page.evaluate("() => localStorage.getItem('torli_pay_method')") == "visa"
    shot(page, "11-payments")
    assert_no_console_errors(page)
