"""Full E2E of the Tor-li consumer app, driving real flows in Chromium.

Run: venv/bin/python -m pytest frontend/consumer/e2e -q
"""

import base64

from conftest import BASE_URL, assert_no_console_errors, shot

# 1x1 transparent PNG for the avatar upload test.
PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


def _goto_home(page):
    page.goto(f"{BASE_URL}/#/home", wait_until="domcontentloaded")
    # Wait for shop cards to render (data-driven; the radius search runs on init).
    page.wait_for_selector("#barbershop-list [data-id]", timeout=15000)


def test_home_loads_shops(page):
    _goto_home(page)
    cards = page.locator("#barbershop-list [data-id]")
    assert cards.count() > 0
    shot(page, "01-home")
    assert_no_console_errors(page)


def test_search_filters(page):
    _goto_home(page)
    before = page.locator("#barbershop-list [data-id]").count()
    page.fill("#search-input", "zzzznomatch")
    page.wait_for_timeout(300)
    assert page.locator("#barbershop-list [data-id]").count() == 0
    page.fill("#search-input", "")
    page.wait_for_timeout(300)
    assert page.locator("#barbershop-list [data-id]").count() == before
    assert_no_console_errors(page)


def test_funnel(page):
    _goto_home(page)
    page.click("#btn-filter")
    page.wait_for_selector("#filter-sheet", state="visible")
    assert "מה אתה מחפש?" in page.inner_text("#filter-sheet")

    # Accordion: open budget panel, move slider.
    page.click('.funnel-pill[data-pill="budget"]')
    page.wait_for_selector('.funnel-panel[data-panel="budget"]:not(.hidden)')
    page.eval_on_selector("#budget-slider", "el => { el.value = el.min; el.dispatchEvent(new Event('input')); }")

    # Rating panel.
    page.click('.funnel-pill[data-pill="rating"]')
    page.wait_for_selector('.funnel-panel[data-panel="rating"]:not(.hidden)')
    # budget panel should now be hidden (one-at-a-time accordion)
    assert page.locator('.funnel-panel[data-panel="budget"]').get_attribute("class").find("hidden") != -1
    page.eval_on_selector("#rating-slider", "el => { el.value = '4'; el.dispatchEvent(new Event('input')); }")

    # Date panel + a quick chip.
    page.click('.funnel-pill[data-pill="date"]')
    page.wait_for_selector('.funnel-panel[data-panel="date"]:not(.hidden)')
    page.locator(".date-chip").first.click()

    shot(page, "02-funnel")
    page.click("#filter-apply")
    page.wait_for_selector("#filter-sheet", state="hidden")
    assert_no_console_errors(page)


def test_map_eta_and_nav(page):
    _goto_home(page)
    page.click("#btn-map-view")
    page.wait_for_selector("#map", state="visible")
    page.wait_for_timeout(4000)  # allow Maps SDK + tiles

    # Open the preview via the real code path (marker.onSelect -> showMapPreview),
    # driven through the debug hook since gmaps markers aren't DOM-clickable.
    page.evaluate(
        "() => window.__torli.showMapPreview(window.__torli.store.get().barbershops[0])"
    )
    page.wait_for_selector("#map-preview:not(.pointer-events-none)")
    # ETA row renders 4 mode cells (values may be '—' if Distance Matrix is denied).
    page.wait_for_function("() => document.querySelectorAll('#mp-eta > div').length === 4", timeout=15000)
    shot(page, "03-map-eta")

    # Nav sheet from the preview.
    page.click("#mp-nav")
    page.wait_for_selector("text=מעולה, איך אתה מתכנן להגיע?")
    for label in ("רגלי", "רכב", "תחבורה ציבורית"):
        assert page.locator(f"text={label}").count() >= 1
    shot(page, "03b-map-nav")
    assert_no_console_errors(page)


def test_barber_profile_share_nav(page):
    _goto_home(page)
    page.locator("#barbershop-list [data-id]").first.click()
    page.wait_for_selector("#view-barber:not(.hidden)")
    page.wait_for_selector("#bp-share")
    shot(page, "04-barber")

    # Share sheet.
    page.click("#bp-share")
    page.wait_for_selector("text=שתף עם חברים")
    for label in ("WhatsApp", "Instagram", "Facebook", "SMS"):
        assert page.locator(f"text={label}").count() >= 1
    shot(page, "05-share")
    # close the share sheet by clicking the backdrop top
    page.keyboard.press("Escape")
    page.mouse.click(10, 10)
    page.wait_for_timeout(300)

    # Nav sheet.
    page.click("#bp-nav")
    page.wait_for_selector("text=מעולה, איך אתה מתכנן להגיע?")
    for label in ("רגלי", "רכב", "תחבורה ציבורית"):
        assert page.locator(f"text={label}").count() >= 1
    shot(page, "06-nav")
    assert_no_console_errors(page)


def test_booking_then_book_again_and_review(page):
    _goto_home(page)
    # Open the shop that has free slots ("Test Cuts E2E" at TLV is first/nearby).
    # Find it by name to be safe.
    page.locator("#barbershop-list [data-id]").first.click()
    page.wait_for_selector("#view-barber:not(.hidden)")
    page.wait_for_selector("#bp-services [data-id]", timeout=15000)

    # Tap first slot -> confirm sheet.
    page.locator("#bp-services [data-id]").first.click()
    page.wait_for_selector("#confirm-sheet", state="visible", timeout=15000)
    # name/phone prefilled from localStorage; tick terms; confirm.
    page.check("#cs-terms")
    page.wait_for_selector("#cs-confirm:not([disabled])")
    page.click("#cs-confirm")

    # Success view.
    page.wait_for_selector("#view-success:not(.hidden)", timeout=15000)
    shot(page, "07-success")

    # Go to bookings; the just-booked (past-dated) slot shows as a past appt.
    page.goto(f"{BASE_URL}/#/bookings", wait_until="domcontentloaded")
    page.wait_for_selector("#mb-list", timeout=15000)
    page.wait_for_selector("[data-rate-id]", timeout=15000)
    shot(page, "08-bookings")

    # Book Again present.
    assert page.locator("[data-again-id]").count() >= 1

    # Rate flow.
    page.locator("[data-rate-id]").first.click()
    page.wait_for_selector(".rv-star")
    page.locator(".rv-star").nth(4).click()  # 5 stars
    page.fill("#rv-comment", "שירות מצוין, בדיקת E2E")
    page.wait_for_selector("#rv-submit:not([disabled])")
    page.click("#rv-submit")
    page.wait_for_timeout(1500)
    shot(page, "09-review-submitted")
    assert_no_console_errors(page)


def test_profile_photo_and_payments(page):
    page.goto(f"{BASE_URL}/#/profile", wait_until="domcontentloaded")
    page.wait_for_selector("#pf-avatar")

    # Avatar -> photo sheet -> upload a tiny PNG via the hidden input.
    page.click("#pf-avatar")
    page.wait_for_selector("#ph-input", state="attached")
    page.set_input_files("#ph-input", files=[{"name": "a.png", "mimeType": "image/png", "buffer": PNG_1PX}])
    page.wait_for_timeout(500)
    # Avatar slot now holds an <img>, and localStorage has the data URL.
    assert page.locator('[data-avatar-slot] img').count() >= 1
    avatar = page.evaluate("() => localStorage.getItem('torli_avatar')")
    assert avatar and avatar.startswith("data:image")
    shot(page, "10-profile-avatar")

    # Payments sheet -> select Visa.
    page.click("#pf-pay")
    page.wait_for_selector("text=אמצעי תשלום")
    for label in ("Apple Pay", "כרטיס אשראי", "Visa"):
        assert page.locator(f"text={label}").count() >= 1
    page.locator('.pay-opt[data-val="visa"]').click()
    page.wait_for_timeout(400)
    assert page.evaluate("() => localStorage.getItem('torli_pay_method')") == "visa"
    shot(page, "11-payments")
    assert_no_console_errors(page)
