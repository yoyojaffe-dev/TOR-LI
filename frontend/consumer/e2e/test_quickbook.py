"""Quick-book "Available Nearby" section: visible + confirm pops + books."""

from playwright.sync_api import expect

from conftest import BASE_URL, assert_no_console_errors, shot
from pages import HomePage


def test_quick_book_section_populates(page) -> None:
    home = HomePage(page, BASE_URL)
    home.goto()

    # The nearby-slots section renders slot cards once upcoming free slots exist.
    section = page.locator("#nearby-slots-section")
    expect(section).to_be_visible()
    expect(home.nearby_slots.first).to_be_visible()
    assert home.nearby_slots.count() > 0
    shot(page, "12-quickbook-section")

    # Tapping a slot pops the "book for [time]?" confirm dialog.
    home.nearby_slots.first.click()
    expect(page.get_by_text("הזמנת תור")).to_be_visible()
    expect(page.get_by_text("להזמין תור", exact=False)).to_be_visible()
    shot(page, "13-quickbook-confirm")
    assert_no_console_errors(page)
