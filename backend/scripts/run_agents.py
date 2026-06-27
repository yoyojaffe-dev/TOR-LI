"""Pipeline orchestrator — runs the agents together.

Runs one Discovery pass to seed/refresh barbershops, then enters the Scraping
loop so freshly discovered shops get their open slots populated continuously.
The Booking Agent is on-demand (POST /bookings/confirm) and is not part of this
loop.

Usage (from /backend):
    python -m scripts.run_agents                                 # Tel Aviv discovery, then scrape loop
    python -m scripts.run_agents --lat 32.7922 --lng 35.5312 --radius 3000
    python -m scripts.run_agents --national                      # full 10-city grid, then scrape loop
    python -m scripts.run_agents --national --cities haifa,eilat # grid subset, then scrape loop
    python -m scripts.run_agents --interval 120                  # scrape every 120s
    python -m scripts.run_agents --no-scrape                     # discovery only, then exit

Cost warning: this hits live Google / OpenAI / Supabase and bills per call. The
scrape loop runs until Ctrl+C. Scope with --radius / --cities for test runs.
"""

import argparse
import asyncio
import logging
import os
import sys

# Ensure /backend is on the path when run as `python -m scripts.run_agents`.
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

from app.agents.discovery_agent import DiscoveryAgent  # noqa: E402
from app.agents.scraping_agent import LOOP_INTERVAL_SECONDS, ScrapingAgent  # noqa: E402
from scripts._cli import (  # noqa: E402
    add_version,
    latitude,
    longitude,
    positive_int,
    run_safely,
)
from scripts.run_national_discovery import _select_cities  # noqa: E402

logger = logging.getLogger("run_agents")


async def _discover(args: argparse.Namespace) -> int:
    """Run the discovery stage (single point or national grid)."""
    agent = DiscoveryAgent()
    if not args.national:
        logger.info("Discovery: (%s, %s) r=%dm", args.lat, args.lng, args.radius)
        return await agent.discover(args.lat, args.lng, args.radius)

    cities = _select_cities(args.cities)
    total = 0
    for i, city in enumerate(cities):
        logger.info("[%d/%d] Discovering %s", i + 1, len(cities), city["name"])
        total += await agent.discover(city["lat"], city["lng"], args.radius)
        if i < len(cities) - 1:
            await asyncio.sleep(args.sleep)
    return total


async def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Tor-li agent pipeline.")
    add_version(parser)
    parser.add_argument("--lat", type=latitude, default=32.0853, help="Discovery centre latitude")
    parser.add_argument("--lng", type=longitude, default=34.7818, help="Discovery centre longitude")
    parser.add_argument(
        "--radius", type=positive_int, default=5000, help="Discovery radius in metres"
    )
    parser.add_argument(
        "--national", action="store_true", help="Sweep the national city grid instead of one point"
    )
    parser.add_argument(
        "--cities", type=str, default=None, help="With --national: comma-separated city subset"
    )
    parser.add_argument(
        "--sleep", type=positive_int, default=3, help="With --national: seconds between cities"
    )
    parser.add_argument(
        "--interval",
        type=positive_int,
        default=LOOP_INTERVAL_SECONDS,
        help="Seconds between scraping passes",
    )
    parser.add_argument("--no-scrape", action="store_true", help="Run discovery only, then exit")
    args = parser.parse_args()

    discovered = await _discover(args)
    logger.info("Discovery stage complete: %d barbershops upserted", discovered)

    if args.no_scrape:
        return

    logger.info("Starting Scraping loop (interval=%ds) — Ctrl+C to stop", args.interval)
    await ScrapingAgent().run(args.interval)


if __name__ == "__main__":
    run_safely(lambda: asyncio.run(main()))
