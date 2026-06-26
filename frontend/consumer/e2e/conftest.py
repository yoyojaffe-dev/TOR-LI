"""Playwright E2E harness for the Tor-li consumer app.

Drives the real static frontend (http.server :3001) against the real FastAPI
backend (:8000). Servers are started if not already up. Each test gets a fresh
browser context with:
  - geolocation granted + set to Tel Aviv (where the slot-bearing shop lives),
  - localStorage preset to skip onboarding and use a known user token,
  - a console-error collector exposed as page.console_errors.
"""

import socket
import subprocess
import time
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[3]  # repo root
CONSUMER_DIR = Path(__file__).resolve().parents[1]  # frontend/consumer
ARTIFACTS = Path(__file__).resolve().parent / "artifacts"
ARTIFACTS.mkdir(exist_ok=True)

FRONTEND_PORT = 3001
BACKEND_PORT = 8000
BASE_URL = f"http://localhost:{FRONTEND_PORT}"

TLV = {"latitude": 32.0853, "longitude": 34.7818}
E2E_TOKEN = "e2e-fixed-token-0001"

# Console messages we tolerate (3rd-party / environmental, not app bugs).
BENIGN = (
    "favicon",
    "maps.googleapis",  # Maps billing/deprecation noise
    "Google Maps",
    "DistanceMatrix",
    "net::ERR_",  # blocked 3rd-party in headless
    "ResizeObserver",
)


def _port_up(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _wait_port(port: int, timeout: float = 20.0) -> None:
    end = time.time() + timeout
    while time.time() < end:
        if _port_up(port):
            return
        time.sleep(0.3)
    raise RuntimeError(f"port {port} never came up")


@pytest.fixture(scope="session", autouse=True)
def servers():
    procs = []
    if not _port_up(BACKEND_PORT):
        procs.append(
            subprocess.Popen(
                [
                    str(ROOT / "venv/bin/uvicorn"),
                    "app.main:app",
                    "--port",
                    str(BACKEND_PORT),
                ],
                cwd=str(ROOT / "backend"),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        )
    if not _port_up(FRONTEND_PORT):
        procs.append(
            subprocess.Popen(
                ["python3", "-m", "http.server", str(FRONTEND_PORT)],
                cwd=str(CONSUMER_DIR),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        )
    _wait_port(BACKEND_PORT)
    _wait_port(FRONTEND_PORT)
    yield
    for p in procs:
        p.terminate()


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True)
        yield b
        b.close()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):  # type: ignore[no-untyped-def]
    """Expose each test's call-phase result so the page fixture can save a trace
    only when the test failed."""
    outcome = yield
    setattr(item, f"rep_{call.when}", outcome.get_result())


@pytest.fixture()
def page(browser, request):
    context = browser.new_context(
        geolocation=TLV,
        permissions=["geolocation"],
        locale="he-IL",
        viewport={"width": 430, "height": 900},
    )
    # Trace every test; keep the zip only on failure (Playwright best practice).
    context.tracing.start(screenshots=True, snapshots=True, sources=True)
    context.add_init_script(f"""
        localStorage.setItem('torli_onboarded', '1');
        localStorage.setItem('torli_user_token', '{E2E_TOKEN}');
        localStorage.setItem('torli_customer_name', 'בודק אוטומטי');
        localStorage.setItem('torli_customer_phone', '0501234567');
        """)
    pg = context.new_page()
    pg.console_errors = []
    pg.on(
        "console",
        lambda m: pg.console_errors.append(m.text) if m.type == "error" else None,
    )
    pg.on("pageerror", lambda e: pg.console_errors.append(f"PAGEERROR: {e}"))
    yield pg

    failed = (
        getattr(request.node, "rep_call", None) is not None
        and request.node.rep_call.failed
    )
    if failed:
        trace_path = ARTIFACTS / f"trace-{request.node.name}.zip"
        context.tracing.stop(path=str(trace_path))
        pg.screenshot(path=str(ARTIFACTS / f"FAIL-{request.node.name}.png"))
    else:
        context.tracing.stop()
    context.close()


def assert_no_console_errors(page):
    real = [e for e in page.console_errors if not any(b in e for b in BENIGN)]
    assert not real, f"console errors: {real}"


def shot(page, name):
    page.screenshot(path=str(ARTIFACTS / f"{name}.png"))
