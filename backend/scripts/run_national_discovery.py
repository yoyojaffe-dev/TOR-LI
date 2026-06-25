"""Nationwide Discovery Grid runner.

Sweeps the Discovery Agent across major Israeli cities to seed barbershops
nationwide. Reuses DiscoveryAgent — no agent changes.

Usage (from /backend):
    python -m scripts.run_national_discovery                    # full 8-city sweep, 12km
    python -m scripts.run_national_discovery --radius 15000     # wider sweep
    python -m scripts.run_national_discovery --cities haifa,eilat   # subset
    python -m scripts.run_national_discovery --cities haifa --radius 4000  # cheap smoke test
    python -m scripts.run_national_discovery --sleep 5          # longer rate-limit gap

Cost warning: a full sweep makes many billed Google Place Details calls and
writes hundreds of rows to the live Supabase project. Use --cities/--radius to
scope test runs.
"""

import argparse
import logging
import os
import sys
import time

# Ensure /backend is on the path when run as `python -m scripts.run_national_discovery`.
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

from app.agents.discovery_agent import DiscoveryAgent  # noqa: E402

logger = logging.getLogger("national_discovery")

# Core grid: major Israeli population centres. Keys are lowercase for --cities.
CITIES = [
    {"key": "tel_aviv",      "name": "Tel Aviv",      "lat": 32.0853, "lng": 34.7818},
    {"key": "jerusalem",     "name": "Jerusalem",     "lat": 31.7683, "lng": 35.2137},
    {"key": "haifa",         "name": "Haifa",         "lat": 32.7940, "lng": 34.9896},
    {"key": "beer_sheva",    "name": "Beer Sheva",    "lat": 31.2518, "lng": 34.7913},
    {"key": "rishon_lezion", "name": "Rishon LeZion", "lat": 31.9730, "lng": 34.7925},
    {"key": "ashdod",        "name": "Ashdod",        "lat": 31.8040, "lng": 34.6550},
    {"key": "netanya",       "name": "Netanya",       "lat": 32.3215, "lng": 34.8532},
    {"key": "eilat",         "name": "Eilat",         "lat": 29.5577, "lng": 34.9519},
]

DEFAULT_RADIUS_M = 12000
DEFAULT_SLEEP_S = 3


def _select_cities(filter_csv: str | None) -> list[dict]:
    """Return the cities to sweep. None/empty -> all. Accepts comma-separated keys."""
    if not filter_csv:
        return CITIES
    wanted = {c.strip().lower() for c in filter_csv.split(",") if c.strip()}
    selected = [c for c in CITIES if c["key"] in wanted]
    unknown = wanted - {c["key"] for c in CITIES}
    if unknown:
        logger.warning("Unknown city keys ignored: %s", ", ".join(sorted(unknown)))
    return selected


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Tor-li nationwide discovery grid.")
    parser.add_argument("--radius", type=int, default=DEFAULT_RADIUS_M,
                        help=f"Search radius per city in metres (default {DEFAULT_RADIUS_M})")
    parser.add_argument("--cities", type=str, default=None,
                        help="Comma-separated subset of city keys (e.g. haifa,eilat). Default: all")
    parser.add_argument("--sleep", type=float, default=DEFAULT_SLEEP_S,
                        help=f"Seconds to sleep between cities (default {DEFAULT_SLEEP_S})")
    args = parser.parse_args()

    cities = _select_cities(args.cities)
    if not cities:
        logger.error("No matching cities to run. Valid keys: %s",
                     ", ".join(c["key"] for c in CITIES))
        sys.exit(1)

    agent = DiscoveryAgent()
    grand_total = 0
    per_city: dict[str, int] = {}

    logger.info("Nationwide discovery: %d cities, radius=%dm, sleep=%ss",
                len(cities), args.radius, args.sleep)

    for i, city in enumerate(cities):
        logger.info("[%d/%d] Discovering %s (%s, %s) r=%dm",
                    i + 1, len(cities), city["name"], city["lat"], city["lng"], args.radius)
        try:
            count = agent.discover(city["lat"], city["lng"], args.radius)
        except Exception as exc:
            logger.error("City %s failed: %s", city["name"], exc)
            count = 0
        per_city[city["name"]] = count
        grand_total += count
        logger.info("[%d/%d] %s -> %d barbershops upserted",
                    i + 1, len(cities), city["name"], count)

        # Rate-limit gap between cities (skip after the last one).
        if i < len(cities) - 1 and args.sleep > 0:
            time.sleep(args.sleep)

    print("\n=== Nationwide discovery summary ===")
    for name, count in per_city.items():
        print(f"  {name:<16} {count:>4}")
    print(f"  {'TOTAL':<16} {grand_total:>4}")


if __name__ == "__main__":
    main()
