"""Diff primitives for the snapshot eval framework.

Two modes:
  _diff()       — strict, used by regression `compare` (exact match required)
  _model_diff() — lenient, used by `compare-models` (case + similarity aware)
"""

from __future__ import annotations

import dataclasses
import difflib
import json

from rapidfuzz import fuzz

# Top-level fields excluded from all diffs (legitimately change each run).
IGNORED_TOP_LEVEL = {"extracted_date", "confidence"}

# Strings with sequence similarity >= this are "similar", not "diff".
SIMILARITY_THRESHOLD = 85.0


# ---------------------------------------------------------------------------
# Shared normaliser
# ---------------------------------------------------------------------------


def _normalize(val: object) -> object:
    """Recursively sort lists and dict keys for order-insensitive comparison."""
    if isinstance(val, list):
        return sorted(
            [_normalize(item) for item in val],
            key=lambda x: json.dumps(x, sort_keys=True),
        )
    if isinstance(val, dict):
        return {k: _normalize(v) for k, v in sorted(val.items())}
    return val


# ---------------------------------------------------------------------------
# Strict diff  (regression testing)
# ---------------------------------------------------------------------------


def strict_diff(expected: object, actual: object, path: str) -> list[str]:
    """Return human-readable failure lines for any mismatch."""
    failures: list[str] = []

    if isinstance(expected, dict) and isinstance(actual, dict):
        for key in sorted(set(expected) | set(actual)):
            child = f"{path}.{key}" if path else key
            if key in IGNORED_TOP_LEVEL and not path:
                continue
            if key not in actual:
                failures.append(f"  MISSING  {child}: expected {expected[key]!r}")
            elif key not in expected:
                failures.append(f"  EXTRA    {child}: got {actual[key]!r}")
            else:
                failures.extend(strict_diff(expected[key], actual[key], child))

    elif isinstance(expected, list) and isinstance(actual, list):
        norm_e, norm_a = _normalize(expected), _normalize(actual)
        if norm_e != norm_a:
            failures.append(
                f"  MISMATCH {path}:\n"
                f"    expected: {json.dumps(norm_e, indent=6)}\n"
                f"    actual:   {json.dumps(norm_a, indent=6)}"
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
# Lenient diff  (cross-model comparison)
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class FieldDiff:
    path: str
    status: str  # "case_match" | "similar" | "diff" | "missing" | "extra"
    baseline_val: object
    candidate_val: object
    similarity: float | None = None


def _str_sim(a: str, b: str) -> float:
    return fuzz.token_set_ratio(a.lower(), b.lower())


def lenient_diff(baseline: object, candidate: object, path: str) -> list[FieldDiff]:
    """Structured diff with case-normalization and similarity scoring."""
    results: list[FieldDiff] = []

    if isinstance(baseline, dict) and isinstance(candidate, dict):
        for key in sorted(set(baseline) | set(candidate)):
            child = f"{path}.{key}" if path else key
            if key in IGNORED_TOP_LEVEL and not path:
                continue
            if key not in candidate:
                results.append(FieldDiff(child, "missing", baseline[key], None))
            elif key not in baseline:
                results.append(FieldDiff(child, "extra", None, candidate[key]))
            else:
                results.extend(lenient_diff(baseline[key], candidate[key], child))

    elif isinstance(baseline, list) and isinstance(candidate, list):
        norm_b, norm_c = _normalize(baseline), _normalize(candidate)
        if norm_b != norm_c:
            b_s = json.dumps(norm_b, sort_keys=True)
            c_s = json.dumps(norm_c, sort_keys=True)
            sim = _str_sim(b_s, c_s)
            results.append(
                FieldDiff(
                    path,
                    "similar" if sim >= SIMILARITY_THRESHOLD else "diff",
                    norm_b,
                    norm_c,
                    sim,
                )
            )

    elif isinstance(baseline, str) and isinstance(candidate, str):
        if baseline != candidate:
            if baseline.lower() == candidate.lower():
                results.append(
                    FieldDiff(path, "case_match", baseline, candidate, 100.0)
                )
            else:
                sim = _str_sim(baseline, candidate)
                results.append(
                    FieldDiff(
                        path,
                        "similar" if sim >= SIMILARITY_THRESHOLD else "diff",
                        baseline,
                        candidate,
                        sim,
                    )
                )

    else:
        if baseline != candidate:
            results.append(FieldDiff(path, "diff", baseline, candidate, None))

    return results


def count_leaf_nodes(obj: object, path: str = "") -> int:
    """Recursively count terminal values in a JSON structure."""
    if isinstance(obj, dict):
        count = 0
        for k, v in obj.items():
            if not path and k in IGNORED_TOP_LEVEL:
                continue
            # Skip empty lists since they don't contain leaf nodes themselves
            if isinstance(v, list) and not v:
                continue
            count += count_leaf_nodes(v, f"{path}.{k}" if path else k)
        return count
    elif isinstance(obj, list):
        if not obj:
            return 0
        return sum(count_leaf_nodes(item, path) for item in obj)
    else:
        return 1


def short(val: object, max_len: int = 55) -> str:
    """Compact display value for report table cells."""
    if val is None:
        return "null"
    if isinstance(val, bool):
        return "true" if val else "false"
    if isinstance(val, (int, float)):
        return str(val)
    if isinstance(val, list):
        n = len(val)
        return f"[{n} item{'s' if n != 1 else ''}]"
    s = str(val)
    return s[: max_len - 1] + "…" if len(s) > max_len else s
