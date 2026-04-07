# Snapshot Eval Framework

`evals/snapshot.py` is the evaluation harness for doc-extractor. It has two jobs:

1. **Regression testing** — re-run extraction on known documents and flag any output that changed.
2. **Cross-model comparison** — diff saved snapshots from two different models and produce a readable Markdown report.

---

## Concepts

| Term | Meaning |
| --- | --- |
| **Snapshot** | Approved JSON output for a single document, stored in `evals/snapshots/`. |
| **Baseline model** | The reference model whose snapshots are treated as ground truth for comparison. |
| **Candidate model** | The model being evaluated against the baseline. |
| **Hard diff** | A field value genuinely disagrees (e.g. wrong number, missing field). |
| **Soft match** | Only casing or minor wording differs — considered factually equivalent. |
| **Exact match** | Outputs are identical after ignoring `extracted_date` and `confidence`. |

---

## Setup

```bash
# Required for Gemini models
export GEMINI_DOC_EXTRACTOR_KEY="your-key"

# Required for Gemma models (free-tier accounts only — paid accounts are blocked by Google)
export GEMMA_FREE_API="your-free-key"
```

---

## Commands

### `approve` — seed or update a snapshot

```bash
# Approve a single document
uv run python evals/snapshot.py approve test_docs/my_doc.pdf

# Approve all documents in test_docs/ (initial seed or full refresh)
uv run python evals/snapshot.py approve --all
```

Runs extraction and saves the output to `evals/snapshots/<stem>.json`.

---

### `compare` — regression test against saved snapshots

```bash
# Compare all approved snapshots (re-runs extraction on every doc)
uv run python evals/snapshot.py compare

# Compare a single document
uv run python evals/snapshot.py compare test_docs/my_doc.pdf
```

Diffs current extraction output against saved snapshots. Exits 1 if any field changed.

**Diff rules:**

- Scalar fields: exact match required.
- Array fields (`test_results`, `line_items`, etc.): order-insensitive.
- `extracted_date` and `confidence` are always ignored (legitimately change each run).
- `document_type` is cross-checked against `test_docs/manifest.json` when present.

---

### `--model` — run any command against a specific model

```bash
# Seed snapshots for a different model
uv run python evals/snapshot.py --model gemini-2.5-pro-preview approve --all

# Regression-test that model's snapshots
uv run python evals/snapshot.py --model gemini-2.5-pro-preview compare
```

Snapshots are stored in `evals/snapshots/<model-name>/` when `--model` is set.
Without the flag, the default directory (`evals/snapshots/`) is used.

---

### `compare-models` — cross-model diff report

```bash
uv run python evals/snapshot.py compare-models <baseline-model> <candidate-model>
```

Compares saved snapshots from two models — **no re-extraction**. Both snapshot dirs must already exist.

```bash
# Example: how does Flash compare to Pro?
uv run python evals/snapshot.py compare-models gemini-2.5-pro-preview gemini-2.5-flash
```

Writes a Markdown report to `evals/reports/YYYY-MM-DD_<baseline>_vs_<candidate>.md` and prints a brief summary to stdout.

**Report sections:**

| Section | What it shows |
| --- | --- |
| **Summary** | Exact / soft / hard counts with percentages |
| **Hard Differences** | Table of fields that genuinely disagree, per document (excludes soft matches) |
| **Soft Matches** | Fields that differ only in casing, word order, or minor wording (≥85% similar via rapidfuzz) |
| **Exact Matches** | Documents with identical output |
| **Skipped** | Documents missing from one or both snapshot dirs |

**Match classification:**

| Label | Meaning |
| --- | --- |
| `✗ DIFF` | Values are genuinely different |
| `✗ MISSING` | Field present in baseline, absent in candidate |
| `✗ EXTRA` | Field present in candidate, absent in baseline |
| `≈ CASE` | Same value, different capitalisation |
| `~ 85%` | Strings are highly similar despite word reordering (rapidfuzz `token_set_ratio` ≥ 85%) |

The similarity threshold is `SIMILARITY_THRESHOLD = 85.0` in `_diff.py`.

---

## Directory layout

```text
evals/
├── snapshot.py               # Entry point — approve, compare, main
├── _diff.py                  # Diff primitives (strict + lenient, SIMILARITY_THRESHOLD)
├── _report.py                # Markdown report builder for compare-models
├── usage.md                  # You are here
├── snapshots/                # Default snapshots (gemini-2.5-flash baseline)
│   ├── my_doc.json
│   └── ...
├── snapshots/<model-name>/   # Per-model snapshots when --model is used
│   └── ...
└── reports/                  # Markdown reports from compare-models
    └── 2026-04-06_gemini-2.5-pro-preview_vs_gemini-2.5-flash.md
```

---

## Typical workflows

### Initial setup

```bash
uv run python evals/snapshot.py approve --all
```

### After changing the prompt or schema

```bash
uv run python evals/snapshot.py compare
# Review any failures, then re-approve if the new output is correct:
uv run python evals/snapshot.py approve test_docs/affected_doc.pdf
```

### Evaluating a new model

```bash
# 1. Seed the new model's snapshots
uv run python evals/snapshot.py --model gemini-2.5-pro-preview approve --all

# 2. Generate the comparison report
uv run python evals/snapshot.py compare-models gemini-2.5-pro-preview gemini-2.5-flash

# 3. Open the report
open evals/reports/$(ls -t evals/reports/ | head -1)
```
