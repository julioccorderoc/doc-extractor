"""Shared stderr output helpers.

stdout is reserved for JSON output — all human-readable messages go to stderr.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


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


def write_json_atomic(payload: object, destination: str | Path) -> Path:
    """Write JSON so a reader never sees a partial file.

    The write happens AFTER the billed model call, so a crash mid-write costs the
    call and leaves a file that parses as truncated JSON. Writing to a sibling
    temp file and renaming makes the result either wholly present or wholly
    absent, which is what lets a caller use "output exists" as a resume marker.
    Parent directories are created — the alternative is losing a paid extraction
    to a missing folder.
    """
    dest = Path(destination)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(json.dumps(payload, indent=2))
        f.flush()
        os.fsync(f.fileno())
    tmp.replace(dest)
    return dest


def write_output(
    results: list[dict], summaries: list[str], output_path: str | None,
) -> None:
    """Serialize extraction results to stdout or a file, then print summaries."""
    payload = results[0] if len(results) == 1 else results

    if output_path:
        write_json_atomic(payload, output_path)
        print_progress(f"Output written to {output_path}")
    else:
        print(json.dumps(payload, indent=2))

    for s in summaries:
        print_err(s)
