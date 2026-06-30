"""Standalone legacy re-classification runner.

Re-verifies legacy barbershops (inserted before the men's-barbershop classifier
existed) through that same classifier, backfilling ``google_types`` and demoting
non-barbers to ``place_type='non_barber'``. Resumable: only rows with
``google_types IS NULL`` are processed, so a re-run picks up where it left off.

Cost: one cheap Place Details (type field only) + one ``gpt-4o-mini`` call per
row. Hits live Google + OpenAI and writes to Supabase.

Usage (from /backend):
    python -m scripts.run_reclassify              # all pending rows
    python -m scripts.run_reclassify --limit 50   # small batch
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

from app.agents.reclassify_agent import ReclassifyAgent  # noqa: E402
from scripts._cli import add_version, positive_int, run_safely  # noqa: E402


async def _main(limit: int | None) -> None:
    stats = await ReclassifyAgent().run(limit)
    print(f"Done — {stats}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Re-classify legacy barbershops (men's filter + google_types backfill)."
    )
    add_version(parser)
    parser.add_argument(
        "--limit",
        type=positive_int,
        default=None,
        help="Max rows to process this pass (default: all pending)",
    )
    args = parser.parse_args()
    asyncio.run(_main(args.limit))


if __name__ == "__main__":
    run_safely(main)
