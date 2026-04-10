# Execution Plan: Autoresearch Integration (EPICs 012–013)

This document captures the full execution strategy derived from re-evaluating
[karpathy/autoresearch](https://github.com/karpathy/autoresearch) on 2026-04-10.
It serves as a ready-to-execute reference for the sessions that implement these
EPICs.

## Architecture Mapping

| autoresearch concept | doc-extractor equivalent |
| -------------------- | ------------------------ |
| `prepare.py` (immutable evaluation harness) | `evals/score.py` + `scripts/schemas/` + `scripts/parse_vision.py` |
| `train.py` (the thing being optimized) | `scripts/prompts.py` |
| `program.md` (human steering interface) | `program.md` at repo root |
| `val_bpb` (scalar objective, lower = better) | F1 score (0.0–100.0, higher = better) |
| `results.tsv` (experiment log) | Same format, adapted columns |
| git branch + commit/revert | `autoresearch/<tag>` branch, revert-commits (not `checkout --`) |
| "NEVER STOP" autonomous loop | `MAX_ITERATIONS` budget (API cost constraint) |

## Key Design Decisions

1. **program.md-driven, not a Python orchestrator.** The agent session IS the
   researcher — it follows `program.md` instructions directly. No
   `scripts/autoresearch.py` needed.

2. **Single-file target space.** Only `scripts/prompts.py` is mutable during
   optimization. Schemas, the extraction engine, and the eval harness are
   immutable — just like `prepare.py` in autoresearch.

3. **Company-agnostic constraint.** The optimization loop must NOT hardcode
   company names, product names, or vendor-specific terms into prompts. The
   skill remains generic. The opinionated layer (e.g., "this company uses 'Run'
   to mean batch number") belongs to the calling agent, not this tool.

4. **Git traceability.** Every experiment is a commit on `autoresearch/<tag>`.
   Failed experiments get a revert-commit (not `git checkout --`), preserving
   full history for post-hoc analysis.

## Prerequisites (already done)

- `evals/source_of_truth/` — 32 human-verified JSON files, all document types.
- `evals/_diff.py` — `lenient_diff()` with rapidfuzz similarity scoring.
- `evals/snapshot.py` — `run_extraction()` function to invoke `parse_vision.py`.
- `evals/` is gitignored — source of truth lives outside version control.

## Step 1: EPIC-012 — Build `evals/score.py`

**Create** `evals/score.py` with this contract:

```text
Usage: uv run python evals/score.py [--verbose]

1. For each JSON in evals/source_of_truth/:
   a. Match to test doc in test_docs/ by stem.
   b. Run extraction via snapshot.run_extraction().
   c. Compare via _diff.lenient_diff(). Classify each FieldDiff:
      - No diff / case_match / similar → TP
      - diff → FP + FN (wrong value = missed truth + added wrong)
      - extra → FP (hallucination)
      - missing → FN (omission)
2. Compute global Precision, Recall, F1.
3. stdout: single float (e.g. "84.5").
4. --verbose: per-document P/R/F1 to stderr.
```

**Reuse (do not reimplement):**

- `_diff.lenient_diff()` — field comparison
- `_diff.count_leaf_nodes()` — field counting
- `_diff.IGNORED_TOP_LEVEL` — skip `extracted_date`, `confidence`
- `snapshot.run_extraction()` — subprocess invocation

## Step 2: EPIC-013 — Write `program.md`

**Create** `program.md` at repo root, structured after autoresearch's program.md:

**Setup section:**

1. Agree on a run tag (e.g., `apr10`). Branch `autoresearch/<tag>` must not
   already exist.
2. `git checkout -b autoresearch/<tag>` from main.
3. Read in-scope files: `prompts.py`, `evals/score.py`, `scripts/schemas/`,
   a few `evals/source_of_truth/` samples for context.
4. Run baseline: `uv run python evals/score.py` → record F1.
5. Initialize `results.tsv` with header + baseline row.

**Constraints section:**

- **CAN modify:** `scripts/prompts.py` — classification prompt, extraction
  rules, field normalization, conflict resolution instructions.
- **CANNOT modify:** `evals/`, `scripts/schemas/`, `scripts/parse_vision.py`.
- **CANNOT add:** company names, product names, vendor names, or any
  domain-specific vocabulary to prompts.
- **Budget:** `MAX_ITERATIONS` (default 10).

**Loop section:**

1. Propose a modification to `prompts.py`.
2. `git commit`.
3. `uv run python evals/score.py` → capture F1.
4. If F1 improved → keep, update `best_score`.
5. If F1 equal or worse → `git revert` (new revert commit).
6. Log to `results.tsv`: `commit\tf1_score\tstatus\tdescription`.
7. Repeat.

**results.tsv format** (tab-separated):

```text
commit f1_score status description
a1b2c3d 84.5 keep baseline
b2c3d4e 86.2 keep added explicit unit normalization for mg/g
c3d4e5f 85.1 discard relaxed date format matching
d4e5f6g 0.0 crash syntax error in prompt template
```

**Autonomy:** NEVER STOP. Run until `MAX_ITERATIONS` or manually interrupted.

## Step 3: Update supporting docs

- Update `CLAUDE.md` Key Commands to include `uv run python evals/score.py`.
- Update `docs/roadmap.md` Epic statuses once complete.
