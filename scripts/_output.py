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


def write_output(
    results: list[dict], summaries: list[str], output_path: str | None,
) -> None:
    """Serialize extraction results to stdout or a file, then print summaries."""
    import json

    output_json = json.dumps(results[0] if len(results) == 1 else results, indent=2)

    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(output_json)
        print_progress(f"Output written to {output_path}")
    else:
        print(output_json)

    for s in summaries:
        print_err(s)
