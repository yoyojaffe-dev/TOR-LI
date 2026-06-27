"""Standalone Enrichment Agent runner.

Loads barbershop booking pages and extracts staff + services into the DB.
Stalest / never-enriched shops first, so repeated runs work through the backlog.

Usage (from /backend):
    python -m scripts.run_enrichment                 # one pass (default limit)
    python -m scripts.run_enrichment --limit 3       # small smoke
    python -m scripts.run_enrichment --limit 100

Cost warning: hits live booking pages + OpenAI and writes to Supabase. Use
--limit to scope test runs. Set LOG_LEVEL=DEBUG for per-shop detail.
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

from app.agents.enrichment_agent import DEFAULT_LIMIT, EnrichmentAgent  # noqa: E402
from scripts._cli import add_version, positive_int, run_safely  # noqa: E402


async def _main(limit: int) -> None:
    stats = await EnrichmentAgent().run_once(limit)
    print(f"Done — {stats}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Tor-li Enrichment Agent (staff + services).")
    add_version(parser)
    parser.add_argument(
        "--limit", type=positive_int, default=DEFAULT_LIMIT, help="Max shops to enrich this pass"
    )
    args = parser.parse_args()
    asyncio.run(_main(args.limit))


if __name__ == "__main__":
    run_safely(main)
