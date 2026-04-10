# ROADMAP

- **Version:** 0.1.0
- **Last Updated:** 2026-04-06
- **Primary Human Owner:** Julio Cordero

## Operating Rules for Planner Agent

1. One active Epic at a time.
2. Verify all Success Criteria in main branch before marking `Complete`.
3. Don't start Epics with incomplete prerequisites.
4. After each Epic: update this file + `.ai/current-plan.md`.
5. Each Epic scoped to single session.

## Test Document Inventory

`test_docs/` contains comprehensive test corpus covering all supported doc types. Each Epic modifying schema support must test against these files.

*Document list removed — test runner dynamically discovers files in `test_docs/`.*

## Epic Ledger

### EPIC-001: Core Engine — Upload, Infer, Return JSON

- **Status:** `Complete`
- **Dependencies:** None
- **Objective:** Working end-to-end pipeline: file path → Gemini → structured JSON stdout. Skeleton for everything else.
- **Scope:**
  - Project setup: `pyproject.toml` with `google-genai` + `pydantic`
  - `scripts/parse_vision.py`: CLI arg parsing, API key validation, file upload + polling, inference with `gemini-3-flash-preview`, stdout JSON, file cleanup
  - `scripts/schemas.py`: `ExtractionResult` envelope + ONE payload (PRODUCT_SPEC_SHEET)
  - Single prompt: classify + extract in one call
  - Test: `(spec_sheet)(Clean_L-Lysine)(ProTab)(Rev1).pdf`
- **Done when:**
  - `python scripts/parse_vision.py "test_docs/(spec_sheet)(...).pdf"` prints valid JSON
  - JSON matches `ExtractionResult` envelope
  - `document_type` = `PRODUCT_SPEC_SHEET`
  - File deleted from Google storage
  - Exit codes: 0 success, 1 missing key, 2 bad file type

### EPIC-002: All Document Schemas + Classification

- **Status:** `Complete`
- **Dependencies:** EPIC-001
- **Objective:** Support all PRD doc types so agent handles any document.
- **Scope:**
  - Pydantic models for: COA, Invoice, Label, Packaging Spec Sheet
  - Master schema = discriminated union (all payload types)
  - Prompt handles classification across all types + UNKNOWN fallback
  - `raw_text_fallback` when extraction fails
  - Test against all docs in inventory
- **Done when:**
  - All test docs return valid JSON with correct `document_type`
  - Invoices extract `line_items`, `grand_total`
  - Spec sheets extract `product_formula`
  - Packaging specs extract `packaging_components`
  - Labels extract `supplements_fact_panel` (or UNKNOWN if unreadable)
  - Payment screenshots return `UNKNOWN` with `raw_text_fallback`

### EPIC-003: Error Handling + Retry Logic

- **Status:** `Complete`
- **Dependencies:** EPIC-001
- **Objective:** Production-resilient — agent doesn't crash on transient API failures or bad inputs.
- **Scope:**
  - Exponential backoff, 3 retries on 429, 500, 503
  - Exit codes: 0=success, 1=missing key, 2=bad file, 3=API failure after retries
  - Extension validation (`.pdf`, `.png`, `.jpg`, `.jpeg`, `.webp`)
  - Handle: file not found, upload failure, processing timeout
  - Cleanup in try/finally
- **Done when:**
  - No `GEMINI_DOC_EXTRACTOR_KEY` → exit 1 + actionable message
  - `.docx` → exit 2
  - Nonexistent path → exit 2
  - No orphaned files after any error path

### EPIC-004: Unit Tests

- **Status:** `Complete`
- **Dependencies:** EPIC-002, EPIC-003
- **Objective:** Fast offline test suite — validate schema changes and extraction logic without API key or real docs.
- **Scope:**
  - `pytest` in `pyproject.toml` dev deps
  - `tests/test_schemas.py`: 6 payload model fixtures, union dispatch (COA → COAPayload, packaging → PackagingSpecSheetPayload), UNKNOWN + null payload, confidence range validation
  - `tests/test_parse_vision.py` (mocked): `validate_file` exits, prompt date check, `with_retry` behavior, main exit 1 without key, cleanup on exception
- **Done when:**
  - `uv run pytest` passes without API key
  - All tests <5s
  - Coverage: all exit codes + union dispatch edge case

### EPIC-005: SKILL.md Integration

- **Status:** `Complete`
- **Dependencies:** EPIC-001, EPIC-002, EPIC-003, EPIC-004
- **Objective:** Package repo as agent-agnostic skill — any agent invokes `/doc-extractor <path>` for structured JSON.
- **Scope:**
  - `SKILL.md` at root — minimal frontmatter (`name`, `description`)
  - References `${SKILL_DIR}/scripts/parse_vision.py`
  - Instructions: run script, capture stdout, interpret exit codes, format response
  - Repo root IS publishable skill
- **Done when:**
  - `/doc-extractor test_docs/...` returns valid JSON in Claude Code session
  - Exit code errors → actionable agent messages
  - Skill appears in listing

### EPIC-006: Snapshot Eval Framework

- **Status:** `Complete`
- **Dependencies:** EPIC-004
- **Objective:** Snapshot-based regression suite — validate schema/prompt/model changes against known-good extractions. Foundation for autoresearch.
- **Scope:**
  - `evals/snapshot.py` — entry point (approve, compare, main); delegates to `_diff.py`, `_report.py`
  - `evals/_diff.py` — `strict_diff()` for regression, `lenient_diff()` for cross-model (case-insensitive + similarity via `difflib`)
  - `evals/_report.py` — Markdown report builder; writes to `evals/reports/`
  - `evals/usage.md` — full usage reference
  - Commands:
    - `approve <file>` / `approve --all` — run extraction, save to `evals/snapshots/<stem>.json`
    - `compare` / `compare <file>` — re-run, diff against snapshots
    - `--model <name> approve --all` — seed model-specific snapshots
    - `--model <name> compare` — regression against model snapshots
    - `compare-models <baseline> <candidate>` — cross-model report (no re-extraction)
  - `test_docs/manifest.json` — filename → expected `document_type`
  - Diff: exact scalars, order-insensitive arrays, ignore `extracted_date` + `confidence`
  - Cross-model: case-only = "soft match"; similarity >=75% = "soft match"; genuine change = "hard diff"
  - API key routing: Gemini → `GEMINI_DOC_EXTRACTOR_KEY`; Gemma → `GEMMA_FREE_API`
- **Done when:**
  - `approve --all` seeds without errors
  - `compare` passes with 0 regressions
  - New doc + approve + compare includes it automatically
  - `extracted_date` excluded from diffs
  - `compare-models` produces structured report

### EPIC-007: Gemma 4 Support

- **Status:** `Cancelled`
- **Note:** Deprecated — Gemma rejects structured output via response_schema, restricted to free-tier accounts. Incompatible with production pipeline.
- **Dependencies:** EPIC-006
- **Objective:** Gemma 4 as free-tier alternative to Gemini.
- **Blocker:** Gemma rejects `response_mime_type="application/json"` + `response_schema` (HTTP 400). Gemini-only feature. Gemma needs: prompt for JSON, parse text, validate against Pydantic. Also free-tier only — paid accounts get HTTP 400. `GEMMA_FREE_API` env var wired in `parse_vision.py`.
- **Scope:**
  - `_extract_gemma()` path: no `response_mime_type`/`response_schema`, explicit JSON instruction, strip markdown fences, validate with `ExtractionResult.model_validate_json()`
  - Route when `model.startswith("gemma")`; `_extract_gemini()` unchanged
  - Run `compare-models` against Flash/Pro baselines
- **Done when:**
  - `approve --all` with `--model gemma-4-26b-a4b-it` completes
  - `compare-models` shows >=85% field match
  - Zero misclassifications
  - `GEMMA_FREE_API` documented

### EPIC-008: Multi-Model Quality Baseline

- **Status:** `Pending`
- **Dependencies:** EPIC-006, EPIC-007
- **Objective:** Quality benchmark across target models — best cost/quality tradeoff.
- **Models:**
  1. `gemini-3.1-pro-preview` — highest quality, most expensive (baseline)
  2. `gemini-2.5-flash` — default, good quality, low cost
- **Scope:**
  - Seed snapshots for all models (`--model` flag)
  - `compare-models` for each against Pro baseline
  - Document field-match % and misclassification count per model
  - Record findings in `.ai/memory.md`
- **Done when:**
  - All model snapshot dirs exist
  - Comparison report generated + findings recorded
  - Recommended default documented with rationale

### EPIC-009: LABEL_ORDER_ACK Schema

- **Status:** `Complete`
- **Dependencies:** EPIC-002
- **Objective:** Support label vendor order acknowledgements — confirm PO receipt/acceptance. Distinct from `LABEL_PROOF` (artwork) and `INVOICE` (billing): confirms quantities, pricing, AND technical print specs.
- **Context:** Two test docs: `(order_acknowledgement)(423747)(BL6).pdf`, `(order_acknowledgement)(530476)(BL5-b).pdf`. Expected type in `test_docs/manifest.json`.
- **Scope:**
  - `LABEL_ORDER_ACK` in `DocumentType` enum
  - `LabelOrderAckPayload`: `date`, `vendor_name`, `doc_number`, `po_number`, `line_items[]` (description, quantity, quantity_unit, unit_price, total, label_size, substrate, inks), `grand_total`, `delivery_date` (optional)
  - Add to `PAYLOAD_SCHEMA_MAP`
  - Classification definition in `build_classification_prompt()`
  - Extraction rules in `_FIELD_RULES`
  - Seed snapshots
- **Done when:**
  - Both docs classify as `LABEL_ORDER_ACK` with confidence >=0.9
  - `line_items` extract with quantities + at least one technical spec
  - `uv run pytest` passes

### EPIC-010: Hybrid Extraction Pipeline (Liteparse + Gemini)

- **Status:** `Complete`
- **Dependencies:** EPIC-002, EPIC-003
- **Objective:** Kill numeric hallucinations and row skipping in dense tables by augmenting visual encoder with deterministic text.
- **Context:** `liteparse` runs locally before API call → deterministic Markdown table layout, bridging vision-language gap.
- **Scope:**
  - Add `liteparse` to `pyproject.toml`
  - `scripts/extract_text.py` — standalone liteparse → text stdout
  - `--use-liteparse` flag on `parse_vision.py` — process text in-memory
  - If flagged: append OCR text to `contents` alongside `uploaded_file`
  - Conflict resolution in prompt:
    - "Base structure/context on visual document."
    - "Base exact spellings, numbers, lot numbers on provided text."
    - "If text garbled/missing, trust image."
  - Update `SKILL.md` with hybrid command
- **Done when:**
  - `extract_text.py` runs independently, prints text
  - `parse_vision.py` accepts `--use-liteparse`
  - `approve --all` completes with new flag
  - `compare-models` shows zero degraded fields on COA/INVOICE

### EPIC-011: Quantitative Eval Reporting & Advanced Fuzzy Math

- **Status:** `Complete`
- **Dependencies:** EPIC-006
- **Objective:** Objective accuracy scores per doc (e.g., "98%") + eliminate false positives via token-based fuzzy matching.
- **Context:** Basic `difflib` penalizes word reordering. 3 field failures on 150-field COA ≠ 3 on 5-field invoice — need denominator.
- **Scope:**
  - Add `rapidfuzz` to `pyproject.toml`
  - Replace `difflib.SequenceMatcher` with `rapidfuzz.fuzz.token_set_ratio` (85% threshold)
  - `count_leaf_nodes()` → `total_fields` per snapshot (exclude `extracted_date`)
  - Separate diff types: Soft matches NOT in Hard Differences table
  - Accuracy in headers: `### COA_100X.pdf — 96.5% Match (112/116 fields)`
- **Done when:**
  - Reordered words → Soft Match
  - "Hard Differences" = genuine mismatches only
  - Every doc shows `(matches/total)` ratio + percentage

### EPIC-012: The Objective Function (F1 Score)

- **Status:** `Pending`
- **Dependencies:** EPIC-011
- **Objective:** Continuous scalar reward signal for autonomous optimization (Karpathy's "fixed metric"). Binary pass/fail insufficient for automated tuning.
- **Context:** F1 (0.0–100.0) vs human-verified Ground Truth, punishing hallucinations (FP) and omissions (FN).
- **Scope:**
  - `evals/source_of_truth/` — highest-quality snapshots, manually verified
  - `evals/score.py` — recursive dict traversal: TP (rapidfuzz), FP, FN
  - Run `parse_vision.py` over `test_docs/`, compare against source of truth
  - Output: single float to stdout (e.g., `84.5`)
- **Done when:**
  - `uv run python evals/score.py` runs
  - Output = single deterministic float
  - Hallucinated field → lower Precision
  - Deleted field → lower Recall

### EPIC-013: Autoresearch Orchestrator

- **Status:** `Pending`
- **Dependencies:** EPIC-012
- **Objective:** Close autonomous optimization loop. LLM rewrites prompts, runs objective function, commits or reverts based on metric.
- **Context:** Port of `karpathy/autoresearch`. Target: `scripts/prompts.py` + `scripts/schemas/`. Loop: modify → evaluate → decide.
- **Scope:**
  - `program.md` at root — human steering interface
  - `scripts/autoresearch.py` orchestrator
  - Loop:
    1. Read `program.md`, `prompts.py`, schemas
    2. Invoke Gemini/Claude API ("Propose diffs to increase F1")
    3. Apply mods to `prompts.py` or schemas
    4. Run `evals/score.py`
    5. `new > best` → log, update. Else → `git checkout -- scripts/` + feedback
  - `MAX_ITERATIONS = 10` cost budget
- **Done when:**
  - Runs uninterrupted loop
  - Modifies `prompts.py`
  - Reverts when F1 drops
  - Terminates at max iterations, repo in best state

### EPIC-014: Datalab.to Hybrid Extraction Sandbox

- **Status:** `Complete`
- **Dependencies:** EPIC-006
- **Objective:** Evaluate Datalab.to fidelity (especially dense tables) vs pure Gemini. Parallel sandbox without touching production.
- **Context:** Datalab.to = purpose-built layout parsing with citations. Two-Pass: Gemini classify → Datalab extract via Pydantic JSON Schema.
- **Scope:**
  - `experiments/datalab_hybrid/` directory
  - Sandbox `requirements.txt` with `datalab-python-sdk`
  - `parse_datalab.py`: Gemini classify → Pydantic schema → Datalab `/extract` → Pydantic rehydrate
  - `evals/snapshot.py` supports `--engine datalab` flag
  - Seed snapshots, run `compare-models`
- **Done when:**
  - `parse_datalab.py` imports shared schemas, extracts JSON
  - `--engine datalab approve --all` seeds snapshots
  - `compare-models gemini-2.5-flash datalab` generates report
  - Production `parse_vision.py` untouched

### EPIC-015: Agentic Ergonomics & CLI Expansion

- **Status:** `Complete`
- **Dependencies:** EPIC-010
- **Objective:** Agent-friendly — URLs, page slicing, file output bypassing stdout limits.
- **Scope:**
  - `--url`: download to temp dir
  - `--output <file.json>`: write JSON to file
  - `--pages "1-3"`: PDF slice via pypdf
  - `--debug`: raw LLM response on validation failure
  - Update `SKILL.md`
- **Done when:**
  - `--url` downloads + extracts from public URL
  - `--output` writes valid JSON
  - `--pages` slices + extracts target pages only
  - `--debug` prints raw text on failure

### EPIC-016: Format Preprocessing (.xlsx/.docx to .pdf)

- **Status:** `Complete`
- **Dependencies:** EPIC-015
- **Objective:** Support Office documents (Excel, Word) — common in supply chain.
- **Context:** Gemini Vision can't natively process `.xlsx`/`.docx`. Need local conversion.
- **Scope:**
  - Detect `.xlsx`/`.docx` → convert to `.pdf` or extract layout text
  - Remove strict extension blocking for these types
- **Done when:**
  - `.xlsx` → valid JSON
  - `.docx` → valid JSON
  - Temp files cleaned up

### EPIC-017: Batch Directory Processing

- **Status:** `Complete`
- **Dependencies:** EPIC-015
- **Objective:** Bulk doc dumps in single command.
- **Scope:**
  - Accept directory path as `<path>`
  - Iterate supported files, classify + extract each
  - Output combined JSON array of `ExtractionResult`
  - Partial failure handling
- **Done when:**
  - Directory → valid JSON array
  - Unsupported files skipped
  - Single failure doesn't crash batch

### EPIC-018: SKILL.md `uv run` Migration & Alignment

- **Status:** `Complete`
- **Dependencies:** EPIC-005
- **Objective:** Fix first-run `ModuleNotFoundError` — SKILL.md used bare `python` not `uv run`. Fix liteparse silent-skip + align with CLAUDE.md.
- **Scope:**
  - All examples: `python` → `cd ${SKILL_DIR} && uv run python scripts/parse_vision.py`
  - Add `uv` to `requires.bins` + `compatibility`
  - `allowed-tools`: `Bash(cd * && uv run *)` + `Bash(uv run *)`
- **Done when:**
  - All examples use `uv run`
  - `allowed-tools` includes both patterns
  - `compatibility` mentions `uv`

### EPIC-019: Fix `model_dump` JSON Serialization Bug

- **Status:** `Complete`
- **Dependencies:** EPIC-002
- **Objective:** Fix `TypeError: Object of type date is not JSON serializable` from `json.dumps()` after successful extraction. `res.model_dump()` returns native `datetime.date`.
- **Scope:**
  - `res.model_dump()` → `res.model_dump(mode="json")`
  - Unit test for date serialization through `json.dumps()`
- **Done when:**
  - `uv run pytest` passes with new test
  - Docs with `extracted_date` produce valid JSON

### EPIC-020: `--summary` Flag & Token-Efficient Response

- **Status:** `Complete`
- **Dependencies:** EPIC-015, EPIC-018
- **Objective:** ~60% agent token reduction. Compact one-line summary per doc on stderr.
- **Scope:**
  - `--summary` flag
  - `build_summary()` with type-specific formatting:
    - COA: `COA | {lot} | {product} | {pass}/{total} PASS | confidence={conf}`
    - Invoice: `INVOICE | #{num} | {vendor} | {items} items | ${total} | confidence={conf}`
    - Generic fallback
  - SKILL.md defaults to `--output` + `--summary`
  - Success format: save JSON, relay summary, tell user file path
- **Done when:**
  - `--summary` prints compact summaries to stderr
  - SKILL.md no longer instructs displaying raw JSON

### EPIC-021: `--quiet` Flag & Dead Code Cleanup

- **Status:** `Complete`
- **Dependencies:** EPIC-018
- **Objective:** Kill ~12 lines batch progress noise. Remove dead `main.py`.
- **Scope:**
  - `--quiet` flag
  - `print_progress()` helper checking flag; convert progress-only `print_err()` calls
  - Warnings/errors always print
  - SKILL.md includes `--quiet` in defaults
  - Delete `main.py`
- **Done when:**
  - `--quiet` suppresses progress, shows warnings/errors
  - `main.py` gone
  - `uv run pytest` passes

### EPIC-022: Provider Abstraction Layer

- **Status:** `Pending`
- **Dependencies:** EPIC-006
- **Objective:** Decouple from Google Gemini — plug in new providers without touching orchestration. Auto-detect via env var (Gemini default), optional `--provider` flag. Pure internal refactor.
- **Scope:**
  - `Provider` Protocol in `scripts/providers/base.py`: `upload()`, `classify()`, `extract()`, `cleanup()`. Returns raw JSON; Pydantic validation in orchestrator. `FileHandle` dataclass + `ProviderError`
  - `resolve_provider()` in `__init__.py`: check env vars in priority, return first match. `--provider` overrides
  - Migrate `scripts/gemini.py` → `scripts/providers/gemini.py` as `GeminiProvider`. Delete old file
  - Update `parse_vision.py`: `resolve_provider()` + protocol methods
  - Update `evals/snapshot.py`: pass `--provider` to subprocess
  - Update tests: mock at Protocol level
- **Done when:**
  - `parse_vision.py test_docs/...` works (auto-detects Gemini)
  - `--provider gemini` explicit — same result
  - `uv run pytest` passes
  - `compare` shows zero regressions
  - New provider = create `providers/<name>.py` + add to registry

### EPIC-023: Agent-Facing Provider Ergonomics

- **Status:** `Pending`
- **Dependencies:** EPIC-022
- **Objective:** Update SKILL.md + CLAUDE.md so agents self-discover providers, troubleshoot keys, use pluggable system.
- **Scope:**
  - **SKILL.md:** update `compatibility` + `requires.env`, "Provider Setup" section (table), `--provider` in args, exit code 1 → check available keys, troubleshooting tree
  - **CLAUDE.md:** add `scripts/providers/` to structure, document `--provider`, "Adding a New Provider" subsection, per-provider env vars
- **Done when:**
  - Agent determines provider from SKILL.md without human help
  - Exit code 1 guides agent to check env vars
  - CLAUDE.md reflects `providers/` structure

### EPIC-024: SKILL.md Compression & Batch Docs

- **Status:** `Pending`
- **Dependencies:** None
- **Objective:** Reduce SKILL.md token footprint ~30-40%. Document batch output structure.
- **Context:** SKILL.md loads into agent context on every invocation (~1,200 tokens). Redundancies: "run from skill dir" repeated in MANDATORY + examples, exit code "Action" column restates obvious, multiple similar examples.
- **Scope:**
  - Deduplicate "run from skill dir" + "use uv run" (appears in MANDATORY and every example)
  - Collapse exit code "Action" column into "Meaning" (obvious from context)
  - Merge similar examples (3 `--output` variants → 1 with inline comments)
  - Add one line documenting batch output structure: single file → JSON object, directory → JSON array
  - Target: ~60 lines from ~85
- **Done when:**
  - SKILL.md <70 lines
  - Batch output structure documented
  - All existing functionality still described (no information loss)

### EPIC-025: Summary Improvements

- **Status:** `Pending`
- **Dependencies:** EPIC-020
- **Objective:** Richer summaries (filename in all paths, markdown format, summary-only triage mode) to reduce agent token waste from reformatting and unnecessary extraction.
- **Context:** Agent spends tokens re-presenting summaries as markdown tables. `build_summary()` omits filename in COA/Invoice/Quote paths. Triage workflows ("did everything pass?") don't need full JSON extraction.
- **Scope:**
  - Add `filename` as first field in ALL `build_summary()` paths (COA, Invoice, Quote, generic fallback)
  - `--format markdown` flag — emit summary as markdown table rows (`| file | type | key_info | confidence |`) so agent relays verbatim
  - `--summary-only` flag — classify via API (1 call), skip extract (pass 2), print summary, exit. No JSON output
  - Update SKILL.md with new flags
- **Done when:**
  - All summary lines include source filename
  - `--format markdown` emits table rows
  - `--summary-only` classifies without extracting, prints summary only
  - `uv run pytest` passes

### EPIC-026: `--schema` Flag (Self-Documenting Schemas)

- **Status:** `Pending`
- **Dependencies:** EPIC-002
- **Objective:** Let agents answer "what fields were extracted?" without reading full JSON payloads. Self-documenting schema access via CLI.
- **Context:** Currently agent must `Read` full JSON file to answer schema questions. Pydantic models already have `.model_json_schema()` — just needs a CLI surface.
- **Scope:**
  - `--schema <TYPE>` — resolve from `PAYLOAD_SCHEMA_MAP`, call `.model_json_schema()`, print to stdout, exit
  - `--schema all` — print all schemas as `{TYPE: schema, ...}`
  - No API key required for this flag
  - Brief schema summary in SKILL.md (just field names per type, ~10 lines)
- **Done when:**
  - `uv run python scripts/parse_vision.py --schema COA` prints JSON schema without API key
  - `--schema all` prints all schemas
  - SKILL.md includes brief field reference

## Minor Backlog

- [ ] Add `COA_RAW` document type and schema parsing based on PRD
- [ ] Add `PACKING_LIST` document type and schema
- [ ] Add `CARRIER_LABEL` document type and schema
- [ ] Add `BOX_CONTENT_LABEL` document type and schema
- [ ] Add `BOL` (Bill of Lading) document type and schema
- [ ] Add `PALLET_LABEL` document type and schema
