"""Snapshot eval framework for doc-extractor.

See evals/usage.md for full documentation.

Exit codes:
    0 - All comparisons passed (or approve completed without errors).
    1 - One or more comparisons failed, or approve encountered errors.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from _diff import IGNORED_TOP_LEVEL, strict_diff

PROJECT_ROOT = Path(__file__).parent.parent
TEST_DOCS_DIR = PROJECT_ROOT / "test_docs"
SNAPSHOTS_BASE_DIR = Path(__file__).parent / "snapshots"
MANIFEST_PATH = TEST_DOCS_DIR / "manifest.json"
PARSE_SCRIPT = PROJECT_ROOT / "scripts" / "parse_vision.py"

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}


def _snapshots_dir(model: str | None, engine: str | None = None) -> Path:
    if engine == "datalab":
        return SNAPSHOTS_BASE_DIR / "datalab"
    return SNAPSHOTS_BASE_DIR / model if model else SNAPSHOTS_BASE_DIR


def _snapshot_path(file_path: Path, snapshots_dir: Path) -> Path:
    return snapshots_dir / f"{file_path.stem}.json"


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------


def run_extraction(
    file_path: Path, model: str | None = None, engine: str | None = None
) -> dict:
    env = {**os.environ, "GEMINI_MODEL": model} if model else dict(os.environ)
    script_path = (
        str(PROJECT_ROOT / "experiments" / "datalab_hybrid" / "parse_datalab.py")
        if engine == "datalab"
        else str(PARSE_SCRIPT)
    )
    cmd = [sys.executable, script_path, str(file_path)]
    if engine != "datalab":
        cmd.append("--use-liteparse")

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=env,
    )
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    if result.returncode != 0:
        raise RuntimeError(
            f"Extraction failed (exit {result.returncode}) for: {file_path.name}"
        )
    return json.loads(result.stdout)


# ---------------------------------------------------------------------------
# approve
# ---------------------------------------------------------------------------


def approve(
    file_path: Path, model: str | None = None, engine: str | None = None
) -> None:
    snapshots_dir = _snapshots_dir(model, engine)
    file_path = file_path.resolve()
    label = f"[{engine or model or 'default'}] "
    print(f"Approving: {label}{file_path.name} ...", file=sys.stderr)
    data = run_extraction(file_path, model=model, engine=engine)
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    snap = _snapshot_path(file_path, snapshots_dir)
    snap.write_text(json.dumps(data, indent=2) + "\n")
    print(f"  -> saved {snap.relative_to(PROJECT_ROOT)}", file=sys.stderr)


def approve_all(model: str | None = None, engine: str | None = None) -> None:
    docs = sorted(
        f for f in TEST_DOCS_DIR.iterdir() if f.suffix.lower() in ALLOWED_EXTENSIONS
    )
    if not docs:
        print("No documents found in test_docs/", file=sys.stderr)
        sys.exit(1)

    # Allow skipping existing snapshots to resume interrupted runs
    skip_existing = os.environ.get("SKIP_EXISTING_SNAPSHOTS") == "1"
    snapshots_dir = _snapshots_dir(model, engine)

    errors: list[str] = []
    for doc in docs:
        try:
            if skip_existing:
                snap = _snapshot_path(doc, snapshots_dir)
                if snap.exists():
                    print(f"Skipping (already exists): {snap.name}", file=sys.stderr)
                    continue
            approve(doc, model=model, engine=engine)
        except Exception as e:
            print(f"  ERROR: {e}", file=sys.stderr)
            errors.append(doc.name)

    ok = len(docs) - len(errors)
    print(f"\nApproved {ok}/{len(docs)} snapshots.", file=sys.stderr)
    if errors:
        print(f"Errors ({len(errors)}): {', '.join(errors)}", file=sys.stderr)
        sys.exit(1)

    errors: list[str] = []
    for doc in docs:
        try:
            approve(doc, model=model, engine=engine)
        except Exception as e:
            print(f"  ERROR: {e}", file=sys.stderr)
            errors.append(doc.name)

    ok = len(docs) - len(errors)
    print(f"\nApproved {ok}/{len(docs)} snapshots.", file=sys.stderr)
    if errors:
        print(f"Errors ({len(errors)}): {', '.join(errors)}", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# compare
# ---------------------------------------------------------------------------


def compare_file(
    file_path: Path,
    manifest: dict[str, str],
    model: str | None = None,
    engine: str | None = None,
) -> bool:
    snapshots_dir = _snapshots_dir(model, engine)
    snap = _snapshot_path(file_path, snapshots_dir)
    if not snap.exists():
        print(f"  SKIP (no snapshot): {file_path.name}")
        return True

    label = f"[{engine or model or 'default'}] "
    print(f"Comparing: {label}{file_path.name} ... ", end="", flush=True)

    try:
        actual = run_extraction(file_path, model=model, engine=engine)
    except Exception as e:
        print("ERROR")
        print(f"  {e}")
        return False

    expected = json.loads(snap.read_text())
    failures: list[str] = []

    expected_type = manifest.get(file_path.name)
    if expected_type and actual.get("document_type") != expected_type:
        failures.append(
            f"  MISCLASSIFIED: manifest expects {expected_type!r}, "
            f"got {actual.get('document_type')!r}"
        )
    failures.extend(strict_diff(expected, actual, ""))

    if failures:
        print("FAIL")
        for line in failures:
            print(line)
        return False

    print("PASS")
    return True


def compare(
    file_path: Path | None = None, model: str | None = None, engine: str | None = None
) -> None:
    snapshots_dir = _snapshots_dir(model, engine)
    manifest: dict[str, str] = (
        json.loads(MANIFEST_PATH.read_text()) if MANIFEST_PATH.exists() else {}
    )

    if file_path is not None:
        sys.exit(
            0
            if compare_file(file_path.resolve(), manifest, model=model, engine=engine)
            else 1
        )

    approved = sorted(snapshots_dir.glob("*.json"))
    if not approved:
        hint = f"--model {model} approve --all" if model else "approve --all"
        if engine:
            hint = f"--engine {engine} " + hint
        print(f"No snapshots found. Run `{hint}` first.", file=sys.stderr)
        sys.exit(1)

    doc_map = {
        f.stem: f
        for f in TEST_DOCS_DIR.iterdir()
        if f.suffix.lower() in ALLOWED_EXTENSIONS
    }
    passed = failed = skipped = 0
    for snap in approved:
        doc = doc_map.get(snap.stem)
        if doc is None:
            print(f"  SKIP (doc not in test_docs/): {snap.name}")
            skipped += 1
        elif compare_file(doc, manifest, model=model, engine=engine):
            passed += 1
        else:
            failed += 1

    print(f"\nResults: {passed} passed, {failed} failed, {skipped} skipped")
    sys.exit(0 if failed == 0 else 1)


# ---------------------------------------------------------------------------
# compare-models
# ---------------------------------------------------------------------------


def compare_models(baseline_model: str, candidate_model: str) -> None:
    from _report import build_report

    report_path, hard = build_report(baseline_model, candidate_model)
    rel = report_path.relative_to(PROJECT_ROOT)

    # brief stdout summary (full detail is in the report)
    import json as _json

    lines = report_path.read_text().splitlines()
    for line in lines:
        if (
            line.startswith("| Exact")
            or line.startswith("| Soft")
            or line.startswith("| Hard")
            or line.startswith("| Skipped")
        ):
            print(" ", line.strip("|").strip())

    print(f"\nReport: {rel}")
    sys.exit(0 if not hard else 1)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)

    # 1. First parse ALL global flags
    model: str | None = None
    engine: str | None = None

    # We need to process arguments while allowing flags to appear anywhere
    # before the command or after the command
    filtered_args = []
    i = 0
    while i < len(args):
        if args[i] == "--model":
            if i + 1 >= len(args):
                print("--model requires a model name", file=sys.stderr)
                sys.exit(1)
            model = args[i + 1]
            i += 2
        elif args[i] == "--engine":
            if i + 1 >= len(args):
                print("--engine requires an engine name", file=sys.stderr)
                sys.exit(1)
            engine = args[i + 1]
            i += 2
        else:
            filtered_args.append(args[i])
            i += 1

    if not filtered_args:
        print(__doc__)
        sys.exit(1)

    cmd = filtered_args[0]

    if cmd == "approve":
        if len(filtered_args) < 2:
            print("Usage: snapshot.py approve <file> | --all", file=sys.stderr)
            sys.exit(1)
        approve_all(model=model, engine=engine) if filtered_args[
            1
        ] == "--all" else approve(Path(filtered_args[1]), model=model, engine=engine)

    elif cmd == "compare":
        compare(
            Path(filtered_args[1]) if len(filtered_args) >= 2 else None,
            model=model,
            engine=engine,
        )

    elif cmd == "compare-models":
        if len(filtered_args) < 3:
            print(
                "Usage: snapshot.py compare-models <baseline> <candidate>",
                file=sys.stderr,
            )
            sys.exit(1)
        compare_models(filtered_args[1], filtered_args[2])

    else:
        print(f"Unknown command: {cmd!r}. See evals/usage.md.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
