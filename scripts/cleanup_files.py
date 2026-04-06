"""Delete all uploaded files from Google's temporary storage.

Useful to avoid hitting the per-project file limit when running many extractions.
Each extraction uploads a file; the script automatically cleans up after itself,
but files from crashed runs may accumulate.

Usage:
    uv run python scripts/cleanup_files.py          # list + delete all
    uv run python scripts/cleanup_files.py --dry-run  # list only, no deletion

Exit codes:
    0 - Success (or nothing to delete)
    1 - Missing GEMINI_DOC_EXTRACTOR_KEY
    2 - One or more deletions failed
"""

from __future__ import annotations

import os
import sys

from google import genai


def main() -> None:
    dry_run = "--dry-run" in sys.argv

    api_key = os.environ.get("GEMINI_DOC_EXTRACTOR_KEY")
    if not api_key:
        print(
            "Error: GEMINI_DOC_EXTRACTOR_KEY is not set.\n"
            "Get a key at https://aistudio.google.com/apikey and run:\n"
            "  export GEMINI_DOC_EXTRACTOR_KEY='your-key-here'",
            file=sys.stderr,
        )
        sys.exit(1)

    client = genai.Client(api_key=api_key)
    files = list(client.files.list())

    if not files:
        print("No files in Google storage. Nothing to do.", file=sys.stderr)
        return

    action = "Would delete" if dry_run else "Deleting"
    print(f"{action} {len(files)} file(s)...", file=sys.stderr)

    errors = 0
    for f in files:
        if dry_run:
            print(f"  {f.name}  ({getattr(f, 'display_name', '')})", file=sys.stderr)
        else:
            try:
                client.files.delete(name=f.name)
                print(f"  Deleted: {f.name}", file=sys.stderr)
            except Exception as e:
                print(f"  Failed:  {f.name} — {e}", file=sys.stderr)
                errors += 1

    if not dry_run:
        ok = len(files) - errors
        print(f"\nDone: {ok} deleted, {errors} errors.", file=sys.stderr)

    sys.exit(2 if errors else 0)


if __name__ == "__main__":
    main()
