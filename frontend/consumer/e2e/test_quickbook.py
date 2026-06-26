"""Quick-book "Available Nearby" section: visible + confirm pops + books."""

from conftest import BASE_URL, assert_no_console_errors, shot


def test_quick_book_section_populates(page):
    page.goto(f"{BASE_URL}/#/home", wait_until="domcontentloaded")
    page.wait_for_selector("#barbershop-list [data-id]", timeout=15000)

    # The nearby-slots section should now be visible with slot cards.
    page.wait_for_selector("#nearby-slots-section:not(.hidden)", timeout=15000)
    page.wait_for_selector("#nearby-slots-list [data-slot-id]", timeout=15000)
    assert page.locator("#nearby-slots-list [data-slot-id]").count() > 0
    shot(page, "12-quickbook-section")

    # Tapping a slot pops the "book for [time]?" confirm dialog.
    page.locator("#nearby-slots-list [data-slot-id]").first.click()
    page.wait_for_selector("text=הזמנת תור")
    assert page.locator("text=להזמין תור").count() >= 1
    shot(page, "13-quickbook-confirm")
    assert_no_console_errors(page)
