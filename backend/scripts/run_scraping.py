"""Standalone Scraping Agent runner.

Usage (from /backend):
    python -m scripts.run_scraping               # one pass, then exit
    python -m scripts.run_scraping --loop        # continuous loop (300s interval)
    python -m scripts.run_scraping --loop --interval 60

Set LOG_LEVEL=DEBUG to see per-shop detail.
"""

import argparse
import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

from app.agents.scraping_agent import ScrapingAgent  # noqa: E402


async def _main(loop: bool, interval: int) -> None:
    agent = ScrapingAgent()
    if loop:
        await agent.run(interval=interval)
    else:
        stats = await agent.run_once()
        print(f"Done — {stats}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Tor-li Scraping Agent.")
    parser.add_argument("--loop", action="store_true", help="Run continuously")
    parser.add_argument(
        "--interval", type=int, default=300, help="Seconds between passes (loop mode)"
    )
    args = parser.parse_args()

    asyncio.run(_main(args.loop, args.interval))


if __name__ == "__main__":
    main()
