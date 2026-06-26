"""Tor-li FastAPI application entrypoint.

Wires the API routers and exposes /health. The Discovery cron and Scraping loop
workers are started from the lifespan hook in a later phase (left commented so
the foundation boots without running the not-yet-implemented agents).
"""

import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.routers import admin, barbershops, bookings, reviews, slots

settings = get_settings()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("torli.api")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup/shutdown hooks for background agents."""
    # TODO (Playwright phase): start Discovery APScheduler cron + Scraping loop here.
    #   scheduler = AsyncIOScheduler(); scheduler.add_job(discovery_agent.run, "cron", ...)
    #   asyncio.create_task(scraping_agent.run())
    yield
    # TODO (Playwright phase): graceful shutdown of scheduler / workers.


app = FastAPI(title="Tor-li API", version="0.1.0", lifespan=lifespan)

# Dev CORS: open. Tighten to the deployed frontend origin before production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Log each request's method/path/status/duration and convert any unhandled
    exception into a safe 500 (the internal error is logged, never leaked)."""
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.exception(
            "unhandled error: %s %s (%.1fms)", request.method, request.url.path, elapsed_ms
        )
        return JSONResponse(status_code=500, content={"detail": "internal server error"})
    elapsed_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "%s %s -> %d (%.1fms)",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )
    return response


app.include_router(barbershops.router)
app.include_router(slots.router)
app.include_router(bookings.router)
app.include_router(reviews.router)

# Admin/ops endpoints trigger billed Google/OpenAI work — keep them out of
# production until auth is added. Mounted only in non-production environments.
if settings.environment != "production":
    app.include_router(admin.router)


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok", "service": "tor-li", "environment": settings.environment}
