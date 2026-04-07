"""Markdown report builder for cross-model snapshot comparison."""

from __future__ import annotations

import datetime
import json
import sys
from pathlib import Path

from _diff import FieldDiff, SIMILARITY_THRESHOLD, count_leaf_nodes, lenient_diff, short

PROJECT_ROOT = Path(__file__).parent.parent
SNAPSHOTS_BASE_DIR = Path(__file__).parent / "snapshots"
REPORTS_DIR = Path(__file__).parent / "reports"


def _snapshots_dir(model: str) -> Path:
    return SNAPSHOTS_BASE_DIR / model


def _classify(diffs: list[FieldDiff]) -> str:
    if not diffs:
        return "exact"
    if all(d.status in ("case_match", "similar") for d in diffs):
        return "soft"
    return "hard"


def _pct(n: int, total: int) -> str:
    return f"{100 * n / total:.0f}%" if total else "—"


def _tag(d: FieldDiff) -> str:
    if d.status == "missing":
        return "✗ MISSING"
    if d.status == "extra":
        return "✗ EXTRA"
    if d.status == "diff":
        return "✗ DIFF"
    if d.status == "case_match":
        return "≈ CASE"
    sim = f"{d.similarity:.1f}%" if d.similarity is not None else ""
    return f"~ {sim}"


def _cell(val: object) -> str:
    """Format a value for a Markdown table cell — escapes pipes and newlines."""
    s = short(val)
    # Pipes break table structure; newlines collapse the row
    return s.replace("|", "&#124;").replace("\n", " ").replace("\r", "")


def _table(headers: list[str], rows: list[list[str]]) -> list[str]:
    """Return lines for a valid GFM table (blank line before already handled by caller)."""
    sep = "|".join("-" * max(3, len(h)) for h in headers)
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + sep + "|",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return lines


def _diff_rows(diffs: list[FieldDiff]) -> list[list[str]]:
    return [
        [f"`{d.path}`", _cell(d.baseline_val), _cell(d.candidate_val), _tag(d)]
        for d in diffs
    ]


def build_report(baseline_model: str, candidate_model: str) -> tuple[Path, list]:
    """Diff two model snapshot dirs and write a Markdown report. Returns (path, hard)."""
    baseline_dir = _snapshots_dir(baseline_model)
    candidate_dir = _snapshots_dir(candidate_model)

    for model, d in [(baseline_model, baseline_dir), (candidate_model, candidate_dir)]:
        if not d.exists() or not any(d.glob("*.json")):
            print(
                f"No snapshots found for {model!r}.\n"
                f"Run: uv run python evals/snapshot.py --model {model} approve --all",
                file=sys.stderr,
            )
            sys.exit(1)

    baseline_snaps = {p.stem: p for p in baseline_dir.glob("*.json")}
    candidate_snaps = {p.stem: p for p in candidate_dir.glob("*.json")}
    all_stems = sorted(baseline_snaps.keys() | candidate_snaps.keys())

    results: list[tuple[str, list[FieldDiff], str, int]] = []
    for stem in all_stems:
        if stem not in baseline_snaps or stem not in candidate_snaps:
            results.append((stem, [], "skipped", 0))
            continue
        b = json.loads(baseline_snaps[stem].read_text())
        c = json.loads(candidate_snaps[stem].read_text())
        diffs = lenient_diff(b, c, "")
        total_fields = count_leaf_nodes(b)
        results.append((stem, diffs, _classify(diffs), total_fields))

    exact = [(s, tf) for s, _, st, tf in results if st == "exact"]
    soft = [(s, d, tf) for s, d, st, tf in results if st == "soft"]
    hard = [(s, d, tf) for s, d, st, tf in results if st == "hard"]
    skipped = [s for s, _, st, _ in results if st == "skipped"]
    compared = len(exact) + len(soft) + len(hard)

    today = datetime.date.today().isoformat()
    safe_b = baseline_model.replace("/", "_")
    safe_c = candidate_model.replace("/", "_")
    report_path = REPORTS_DIR / f"{today}_{safe_b}_vs_{safe_c}.md"
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # Build as a list of paragraphs; each paragraph is a list of lines.
    # We join paragraphs with a blank line between them to guarantee proper spacing.
    paras: list[list[str]] = []

    def section(lines: list[str]) -> None:
        paras.append(lines)

    # ------------------------------------------------------------------ header
    section(["# Cross-Model Comparison Report"])
    section(
        _table(
            ["Property", "Value"],
            [
                ["Baseline", f"`{baseline_model}` ({len(baseline_snaps)} snapshots)"],
                [
                    "Candidate",
                    f"`{candidate_model}` ({len(candidate_snaps)} snapshots)",
                ],
                ["Generated", today],
                ["Similarity threshold", f"{SIMILARITY_THRESHOLD}%"],
            ],
        )
    )

    # ----------------------------------------------------------------- summary
    section(["## Summary"])
    section(
        _table(
            ["Status", "Count", "%"],
            [
                ["Exact match", str(len(exact)), _pct(len(exact), compared)],
                [
                    "Soft match _(case / similar only)_",
                    str(len(soft)),
                    _pct(len(soft), compared),
                ],
                ["Hard diff", str(len(hard)), _pct(len(hard), compared)],
                ["Skipped", str(len(skipped)), "—"],
                ["**Total compared**", f"**{compared}**", ""],
            ],
        )
    )

    # ------------------------------------------------------------ hard diffs
    if hard:
        section(["## Hard Differences"])
        section(
            [
                "> Fields with genuine value differences (not just casing or minor wording)."
            ]
        )
        for stem, diffs, total_fields in hard:
            hard_diffs = [d for d in diffs if d.status in ("diff", "missing", "extra")]
            matched_fields = total_fields - len(hard_diffs)
            accuracy = _pct(matched_fields, total_fields)
            section(
                [
                    f"### {stem} — {accuracy} Match ({matched_fields}/{total_fields} fields)"
                ]
            )

            section(
                _table(
                    ["Field", "Baseline", "Candidate", "Match"],
                    _diff_rows(hard_diffs),
                )
            )

    # ---------------------------------------------------------- soft matches
    if soft:
        section(["## Soft Matches"])
        section(["> Only casing or minor wording differences — factually equivalent."])
        for stem, diffs, total_fields in soft:
            section([f"### {stem} — 100% Match ({total_fields}/{total_fields} fields)"])
            section(
                _table(
                    ["Field", "Baseline", "Candidate", "Match"],
                    _diff_rows(diffs),
                )
            )

    # --------------------------------------------------------- exact matches
    section(["## Exact Matches"])
    section(
        [f"- {stem} — 100% Match ({tf}/{tf} fields)" for stem, tf in exact]
        or ["_None_"]
    )

    # ---------------------------------------------------------------- skipped
    if skipped:
        section(["## Skipped"])
        section([f"- {stem}" for stem in skipped])

    # Join paragraphs with blank lines between them
    output = "\n\n".join("\n".join(para) for para in paras) + "\n"
    report_path.write_text(output)
    return report_path, hard
