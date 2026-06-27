"""Shared CLI helpers for the Tor-li agent runner scripts.

Centralises the version string, argparse value validators (clear errors, fail
early), and a SIGINT-safe entrypoint wrapper so every runner behaves the same.
"""

import argparse
import logging
import sys
from collections.abc import Callable

VERSION = "tor-li-agents 0.1.0"

logger = logging.getLogger("torli.cli")


def add_version(parser: argparse.ArgumentParser) -> None:
    """Add a standard ``--version`` flag."""
    parser.add_argument("--version", action="version", version=VERSION)


def positive_int(value: str) -> int:
    """argparse type: a strictly-positive integer."""
    try:
        ivalue = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{value!r} is not an integer") from None
    if ivalue <= 0:
        raise argparse.ArgumentTypeError(f"must be > 0, got {ivalue}")
    return ivalue


def nonneg_float(value: str) -> float:
    """argparse type: a non-negative float."""
    try:
        fvalue = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{value!r} is not a number") from None
    if fvalue < 0:
        raise argparse.ArgumentTypeError(f"must be >= 0, got {fvalue}")
    return fvalue


def latitude(value: str) -> float:
    """argparse type: a WGS84 latitude in [-90, 90]."""
    try:
        fvalue = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{value!r} is not a number") from None
    if not -90.0 <= fvalue <= 90.0:
        raise argparse.ArgumentTypeError(f"latitude must be in [-90, 90], got {fvalue}")
    return fvalue


def longitude(value: str) -> float:
    """argparse type: a WGS84 longitude in [-180, 180]."""
    try:
        fvalue = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{value!r} is not a number") from None
    if not -180.0 <= fvalue <= 180.0:
        raise argparse.ArgumentTypeError(f"longitude must be in [-180, 180], got {fvalue}")
    return fvalue


def run_safely(func: Callable[[], None]) -> None:
    """Run ``func`` translating Ctrl+C into a clean exit (code 130) instead of a
    traceback. Diagnostics go to stderr via logging so piped stdout stays clean."""
    try:
        func()
    except KeyboardInterrupt:
        logger.warning("interrupted — exiting")
        sys.exit(130)
