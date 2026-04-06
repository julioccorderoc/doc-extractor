"""Snapshot eval framework for doc-extractor.

Usage:
    uv run python evals/snapshot.py approve <file>
    uv run python evals/snapshot.py approve --all
    uv run python evals/snapshot.py compare
    uv run python evals/snapshot.py compare <file>

Commands:
    approve <file>   Run extraction, save output as approved snapshot.
    approve --all    Batch-approve all docs in test_docs/ (seed the corpus).
    compare          Re-run all approved docs, diff vs snapshots, report pass/fail.
    compare <file>   Single-doc diff.

Diff strategy:
    - Exact match on scalar fields.
    - Order-insensitive match on array fields (test_results, line_items, etc.).
    - `extracted_date` and `confidence` are always ignored (they vary per run).
    - `document_type` is also checked against test_docs/manifest.json when present.

Exit codes:
    0 - All comparisons passed (or approve completed without errors).
    1 - One or more comparisons failed, or approve encountered errors.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
TEST_DOCS_DIR = PROJECT_ROOT / "test_docs"
SNAPSHOTS_DIR = Path(__file__).parent / "snapshots"
MANIFEST_PATH = TEST_DOCS_DIR / "manifest.json"
PARSE_SCRIPT = PROJECT_ROOT / "scripts" / "parse_vision.py"

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}

# Top-level fields excluded from every diff (they legitimately change each run).
IGNORED_TOP_LEVEL = {"extracted_date", "confidence"}


# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------


def run_extraction(file_path: Path) -> dict:
    """Run parse_vision.py on a file and return parsed JSON.

    Uses sys.executable so the same venv/uv-managed Python is used.
    stdout → JSON, stderr → forwarded to our stderr.
    """
    result = subprocess.run(
        [sys.executable, str(PARSE_SCRIPT), str(file_path)],
        capture_output=True,
        text=True,
    )
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    if result.returncode != 0:
        raise RuntimeError(
            f"Extraction failed (exit {result.returncode}) for: {file_path.name}"
        )
    return json.loads(result.stdout)


def snapshot_path(file_path: Path) -> Path:
    """Return the snapshot path for a given test doc (keyed by stem)."""
    return SNAPSHOTS_DIR / f"{file_path.stem}.json"


# ---------------------------------------------------------------------------
# approve
# ---------------------------------------------------------------------------


def approve(file_path: Path) -> None:
    """Run extraction on file and save output as approved snapshot."""
    file_path = file_path.resolve()
    print(f"Approving: {file_path.name} ...", file=sys.stderr)
    data = run_extraction(file_path)
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    snap = snapshot_path(file_path)
    snap.write_text(json.dumps(data, indent=2) + "\n")
    print(f"  -> saved {snap.relative_to(PROJECT_ROOT)}", file=sys.stderr)


def approve_all() -> None:
    """Batch-approve all docs in test_docs/."""
    docs = sorted(
        f
        for f in TEST_DOCS_DIR.iterdir()
        if f.is_file() and f.suffix.lower() in ALLOWED_EXTENSIONS
    )
    if not docs:
        print("No documents found in test_docs/", file=sys.stderr)
        sys.exit(1)

    errors: list[str] = []
    for doc in docs:
        try:
            approve(doc)
        except Exception as e:
            print(f"  ERROR: {e}", file=sys.stderr)
            errors.append(doc.name)

    total = len(docs)
    ok = total - len(errors)
    print(f"\nApproved {ok}/{total} snapshots.", file=sys.stderr)
    if errors:
        print(f"Errors ({len(errors)}): {', '.join(errors)}", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Diff logic
# ---------------------------------------------------------------------------


def _normalize(val: object) -> object:
    """Recursively normalize a value for order-insensitive comparison.

    Lists are sorted by canonical JSON so array order doesn't matter.
    Dicts have keys sorted for a stable canonical form.
    """
    if isinstance(val, list):
        normalized_items = [_normalize(item) for item in val]
        return sorted(normalized_items, key=lambda x: json.dumps(x, sort_keys=True))
    if isinstance(val, dict):
        return {k: _normalize(v) for k, v in sorted(val.items())}
    return val


def _diff(expected: object, actual: object, path: str) -> list[str]:
    """Recursively diff two values, returning human-readable failure lines."""
    failures: list[str] = []

    if isinstance(expected, dict) and isinstance(actual, dict):
        all_keys = set(expected) | set(actual)
        for key in sorted(all_keys):
            child_path = f"{path}.{key}" if path else key
            if key in IGNORED_TOP_LEVEL and not path:
                continue
            if key not in actual:
                failures.append(f"  MISSING  {child_path}: expected {expected[key]!r}")
            elif key not in expected:
                failures.append(f"  EXTRA    {child_path}: got {actual[key]!r}")
            else:
                failures.extend(_diff(expected[key], actual[key], child_path))
    elif isinstance(expected, list) and isinstance(actual, list):
        # Order-insensitive: compare sorted canonical forms
        norm_exp = _normalize(expected)
        norm_act = _normalize(actual)
        if norm_exp != norm_act:
            failures.append(
                f"  MISMATCH {path}:\n"
                f"    expected: {json.dumps(norm_exp, indent=6)}\n"
                f"    actual:   {json.dumps(norm_act, indent=6)}"
            )
    else:
        if expected != actual:
            failures.append(
                f"  MISMATCH {path}:\n"
                f"    expected: {expected!r}\n"
                f"    actual:   {actual!r}"
            )

    return failures


# ---------------------------------------------------------------------------
# compare
# ---------------------------------------------------------------------------


def compare_file(file_path: Path, manifest: dict[str, str]) -> bool:
    """Compare current extraction against snapshot. Returns True if passed."""
    snap = snapshot_path(file_path)
    if not snap.exists():
        print(f"  SKIP (no snapshot): {file_path.name}")
        return True  # Not a failure — just not yet approved

    print(f"Comparing: {file_path.name} ... ", end="", flush=True)

    try:
        actual = run_extraction(file_path)
    except Exception as e:
        print("ERROR")
        print(f"  {e}")
        return False

    expected = json.loads(snap.read_text())
    failures: list[str] = []

    # Manifest classification check (catches misclassifications cheaply)
    expected_type = manifest.get(file_path.name)
    if expected_type and actual.get("document_type") != expected_type:
        failures.append(
            f"  MISCLASSIFIED: manifest expects {expected_type!r}, "
            f"got {actual.get('document_type')!r}"
        )

    # Field-level diff
    failures.extend(_diff(expected, actual, ""))

    if failures:
        print("FAIL")
        for line in failures:
            print(line)
        return False

    print("PASS")
    return True


def compare(file_path: Path | None = None) -> None:
    """Run compare for one file or all approved snapshots."""
    manifest: dict[str, str] = {}
    if MANIFEST_PATH.exists():
        manifest = json.loads(MANIFEST_PATH.read_text())

    if file_path is not None:
        ok = compare_file(file_path.resolve(), manifest)
        sys.exit(0 if ok else 1)

    approved = sorted(SNAPSHOTS_DIR.glob("*.json"))
    if not approved:
        print("No snapshots found. Run `approve --all` first.", file=sys.stderr)
        sys.exit(1)

    # Build stem → Path map of all test docs
    doc_map: dict[str, Path] = {
        f.stem: f
        for f in TEST_DOCS_DIR.iterdir()
        if f.is_file() and f.suffix.lower() in ALLOWED_EXTENSIONS
    }

    passed = failed = skipped = 0
    for snap in approved:
        doc = doc_map.get(snap.stem)
        if doc is None:
            print(f"  SKIP (doc not in test_docs/): {snap.name}")
            skipped += 1
            continue
        if compare_file(doc, manifest):
            passed += 1
        else:
            failed += 1

    print(f"\nResults: {passed} passed, {failed} failed, {skipped} skipped")
    sys.exit(0 if failed == 0 else 1)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)

    cmd = args[0]

    if cmd == "approve":
        if len(args) < 2:
            print("Usage: snapshot.py approve <file> | --all", file=sys.stderr)
            sys.exit(1)
        if args[1] == "--all":
            approve_all()
        else:
            approve(Path(args[1]))

    elif cmd == "compare":
        if len(args) >= 2:
            compare(Path(args[1]))
        else:
            compare()

    else:
        print(f"Unknown command: {cmd!r}. Use approve or compare.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
