"""Tor-li FastAPI application entrypoint.

Wires the API routers and exposes /health. The Discovery cron and Scraping loop
workers are started from the lifespan hook in a later phase (left commented so
the foundation boots without running the not-yet-implemented agents).
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import admin, barbershops, bookings, reviews, slots

settings = get_settings()


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

app.include_router(barbershops.router)
app.include_router(slots.router)
app.include_router(bookings.router)
app.include_router(reviews.router)

# Admin/ops endpoints — mounted in all environments for manual triggers.
# Add auth middleware here before going to production.
app.include_router(admin.router)


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok", "service": "tor-li", "environment": settings.environment}
