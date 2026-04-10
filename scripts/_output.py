"""Shared stderr output helpers.

stdout is reserved for JSON output — all human-readable messages go to stderr.
"""

from __future__ import annotations

import sys


_quiet: bool = False


def set_quiet(quiet: bool) -> None:
    """Set the quiet flag (suppresses progress messages)."""
    global _quiet
    _quiet = quiet


def print_err(msg: str) -> None:
    """Print to stderr (stdout is reserved for JSON output)."""
    print(msg, file=sys.stderr)


def print_progress(msg: str) -> None:
    """Print progress info to stderr, suppressed when quiet mode is set."""
    if not _quiet:
        print(msg, file=sys.stderr)
