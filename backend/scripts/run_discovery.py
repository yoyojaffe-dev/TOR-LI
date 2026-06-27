"""Standalone Discovery Agent runner.

Usage (from /backend):
    python -m scripts.run_discovery                                 # Tel Aviv default
    python -m scripts.run_discovery --lat 31.7938 --lng 35.2134    # Jerusalem
    python -m scripts.run_discovery --lat 32.0853 --lng 34.7818 --radius 10000

Logs each shop upserted at DEBUG level; set LOG_LEVEL=DEBUG to see detail.
"""

import argparse
import asyncio
import logging
import os
import sys

# Ensure /backend is on the path when run as `python -m scripts.run_discovery`.
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

from app.agents.discovery_agent import DiscoveryAgent  # noqa: E402
from scripts._cli import (  # noqa: E402
    add_version,
    latitude,
    longitude,
    positive_int,
    run_safely,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Tor-li Discovery Agent once.")
    add_version(parser)
    parser.add_argument("--lat", type=latitude, default=32.0853, help="Centre latitude")
    parser.add_argument("--lng", type=longitude, default=34.7818, help="Centre longitude")
    parser.add_argument("--radius", type=positive_int, default=5000, help="Search radius in metres")
    args = parser.parse_args()

    print(f"Discovery: lat={args.lat}, lng={args.lng}, radius={args.radius}m")
    count = asyncio.run(DiscoveryAgent().discover(args.lat, args.lng, args.radius))
    print(f"Done — {count} barbershops upserted.")


if __name__ == "__main__":
    run_safely(main)
