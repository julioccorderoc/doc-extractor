# ROADMAP

- **Version:** 0.1.0
- **Last Updated:** 2026-04-06
- **Primary Human Owner:** Julio Cordero

## Operating Rules for the Planner Agent

1. You may only move one Epic to `Active` at a time.
2. Before marking an Epic `Complete`, you must verify all its Success Criteria
   are met in the main branch.
3. Do not parse or extract Epics that depend on incomplete prerequisites.
4. After completing each Epic, update this file and `.ai/current-plan.md`.
5. Each Epic is scoped to be completable in a single session.

## Test Document Inventory

The following files in `test_docs/` serve as our evaluation corpus. Each Epic
that adds schema support must be tested against the relevant files.

<!-- markdownlint-disable MD013 -->
| File                                                                          | Expected Type        | Notes                                  |
| ----------------------------------------------------------------------------- | -------------------- | -------------------------------------- |
| `$30,675.00 Monolaurin 600mg Run 13 Deposit 1 Invoice 17095.pdf`              | INVOICE              | Manufacturer invoice                   |
| `$30,806.62 Lysine + Monolaurin Run 11 PO19 Deposit 2 21 Mar 2024.pdf`        | INVOICE              | Manufacturer invoice                   |
| `(Sales_Order)(PO_PT04)(SO#0007812)(Immune_Support)(Protab).pdf`              | INVOICE              | Sales order (treat as invoice variant) |
| `(Sales_Order)(PO_PT08)(SO#0007859)(L-Lysine_Monolaurin)(Protab).pdf`         | INVOICE              | Sales order (treat as invoice variant) |
| `(first_payment)(BN3).png`                                                    | PAYMENT_PROOF        | Bank payment screenshot                |
| `(first_payment)(NS38)(NutraStar)($33,059.57).png`                            | PAYMENT_PROOF        | Bank payment screenshot                |
| `(packaging_spec_sheet)(3001)(Monolaurin_800mg)(NCL)(Protab)(Signed)(v0).pdf` | PACKAGING_SPEC_SHEET | Signed packaging spec                  |
| `(packaging_spec_sheet)(4001)(Clean_L-Lysine)(NCL)(Protab)(Signed)(v1).pdf`   | PACKAGING_SPEC_SHEET | Signed packaging spec                  |
| `(packaging_spec_sheet)(PH4001)(Clean_L-Lysine)(PH)(Protab)(Signed)(v1).pdf`  | PACKAGING_SPEC_SHEET | Different brand (PH)                   |
| `(spec_sheet)(Clean_L-Lysine)(ProTab)(Rev1).pdf`                              | PRODUCT_SPEC_SHEET   | Product specification                  |
| `(spec_sheet)(Immune_Support)(Protab).pdf`                                    | PRODUCT_SPEC_SHEET   | Product specification                  |
| `Artwork_200X_NCL_REV-3.pdf`                                                  | LABEL                | Product label artwork                  |
| `Artwork_400X_NCL_FNSKU-V3.pdf`                                               | LABEL                | Product label artwork                  |
| `Artwork_400X_NCL_FNSKU-V4.pdf`                                               | LABEL                | Product label artwork                  |
| `Artwork_400X_NCL_FNSKU-V5.pdf`                                               | LABEL                | Product label artwork                  |
| `Artwork_400X_PH_FNSKU-V5.pdf`                                                | LABEL                | Different brand (PH)                   |
| `Artwork_900X_NCL_FNSKU-V2.pdf`                                               | LABEL                | Large label artwork                    |
| `Artwork_900X_NCL_FNSKU-V3.pdf`                                               | LABEL                | Large label artwork                    |
| `COA_100X_Run-18_NutraStar_NS32_2025-25535_2025-02_NutraStar.pdf`             | COA                  | NutraStar COA                          |
| `COA_100X_Run-19_Gemini_G4_69600_2025-09-25_Gemini.pdf`                       | COA                  | Gemini COA                             |
| `COA_600X_Run-06_BestNutra_BN2_0125054_2025-04.pdf`                           | COA                  | BestNutra COA                          |
| `COA_600X_Run-07_VitaNorth_VN1_UNKNOWN-LOT_01.pdf`                            | COA                  | VitaNorth COA, unknown lot             |
| `(proof)(BL6)(540837).pdf`                                                    | LABEL_PROOF          | Print proof from label vendor          |
| `(proof)(BL6)(540841).pdf`                                                    | LABEL_PROOF          | Print proof from label vendor          |
| `label_proof_BL5-b_530476.pdf`                                                | LABEL_PROOF          | Print proof from label vendor          |
| `(order_acknowledgement)(423747)(BL6).pdf`                                    | LABEL_ORDER_ACK      | Label PO acknowledgement (BL6)         |
| `(order_acknowledgement)(530476)(BL5-b).pdf`                                  | LABEL_ORDER_ACK      | Label PO acknowledgement (BL5-b)       |
<!-- markdownlint-restore -->

**Missing test coverage:** Quote documents. Add samples when available.

## Epic Ledger

### EPIC-001: Core Engine — Upload, Infer, Return JSON

- **Status:** `Complete`
- **Dependencies:** None
- **Business Objective:** Get a working end-to-end pipeline that takes a file
  path, sends it to Gemini, and returns structured JSON to stdout. This is the
  skeleton everything else builds on.
- **Technical Boundary:**
  - Set up project: `pyproject.toml` with `google-genai` and `pydantic`
    dependencies
  - Create `scripts/parse_vision.py` with: CLI arg parsing, API key validation,
    file upload + polling, inference call with `gemini-3-flash-preview`, stdout
    JSON output, file cleanup
  - Create `scripts/schemas.py` with: top-level `ExtractionResult` envelope, ONE
    payload schema (PRODUCT_SPEC_SHEET — simplest to validate visually)
  - Single prompt: classify + extract in one call
  - Test against: `(spec_sheet)(Clean_L-Lysine)(ProTab)(Rev1).pdf`
- **Verification Criteria (Definition of Done):**
  - `python scripts/parse_vision.py "test_docs/(spec_sheet)(Clean_L-Lysine)(ProTab)(Rev1).pdf"`
    prints valid JSON to stdout
  - JSON matches the `ExtractionResult` envelope schema
  - `document_type` is `PRODUCT_SPEC_SHEET`
  - File is deleted from Google's storage after extraction
  - Exit code 0 on success, 1 on missing key, 2 on bad file type

### EPIC-002: All Document Schemas + Classification

- **Status:** `Complete`
- **Dependencies:** EPIC-001
- **Business Objective:** Support all supply chain document types defined in the
  PRD so the agent can handle any document thrown at it.
- **Technical Boundary:**
  - Add Pydantic models for: COA, Invoice, Label, Packaging Spec Sheet
  - Update the master schema to be a discriminated union (all payload types)
  - Refine the prompt to handle classification across all types + UNKNOWN
    fallback
  - Add `raw_text_fallback` population when extraction fails
  - Test against all files in the test document inventory above
- **Verification Criteria (Definition of Done):**
  - All test documents return valid JSON with correct `document_type`
    classification
  - Invoices extract `line_items`, `grand_total`
  - Spec sheets extract `product_formula`
  - Packaging spec sheets extract `packaging_components`
  - Label artworks extract `supplements_fact_panel` (or UNKNOWN if artwork is
    not readable)
  - Payment screenshots return `UNKNOWN` with `raw_text_fallback`

### EPIC-003: Error Handling + Retry Logic

- **Status:** `Complete`
- **Dependencies:** EPIC-001
- **Business Objective:** Make the script production-resilient so the autonomous
  agent doesn't crash on transient API failures or bad inputs.
- **Technical Boundary:**
  - Exponential backoff with 3 retries on API errors (429, 500, 503)
  - Exit code mapping: 0=success, 1=missing key, 2=bad file type, 3=API failure
    after retries
  - File extension validation (`.pdf`, `.png`, `.jpg`, `.jpeg`, `.webp` only)
  - Graceful handling of: file not found, upload failure, processing timeout
  - Ensure cleanup runs even on error (try/finally)
- **Verification Criteria (Definition of Done):**
  - Running without `GEMINI_DOC_EXTRACTOR_KEY` → exit code 1, actionable error
    message
  - Running with a `.docx` file → exit code 2
  - Running with a nonexistent path → exit code 2
  - Cleanup confirmed: no orphaned files in Google storage after any error path

### EPIC-004: Unit Tests

- **Status:** `Complete`
- **Dependencies:** EPIC-002, EPIC-003
- **Business Objective:** Give the codebase a fast, offline test suite so
  schema changes and extraction logic can be validated without an API key or
  real documents.
- **Technical Boundary:**
  - Add `pytest` to `pyproject.toml` dev dependencies
  - Create `tests/test_schemas.py`:
    - All 6 payload models validate expected JSON fixtures
    - Union dispatch: COA JSON → `COAPayload`, packaging JSON →
      `PackagingSpecSheetPayload` (not `ProductSpecSheetPayload`)
    - `ExtractionResult` with `document_type=UNKNOWN` and `payload=null`
      validates cleanly
    - `confidence` rejects values outside 0.0–1.0
  - Create `tests/test_parse_vision.py` (mock API, no real calls):
    - `validate_file` exits 2 for missing file
    - `validate_file` exits 2 for unsupported extension
    - `build_extraction_prompt()` contains today's date string
    - `with_retry` retries on 429/500/503 and raises after `MAX_RETRIES`
    - `with_retry` does not retry on 400/404
    - `main()` exits 1 when `GEMINI_DOC_EXTRACTOR_KEY` is unset
    - Cleanup runs even when extraction raises an exception
- **Verification Criteria (Definition of Done):**
  - `uv run pytest` passes with no API key set
  - All tests run in under 5 seconds (no real I/O)
  - Coverage includes all exit code paths and the union dispatch edge case

### EPIC-005: SKILL.md Integration

- **Status:** `Complete`
- **Dependencies:** EPIC-001, EPIC-002, EPIC-003, EPIC-004
- **Business Objective:** Package the repo as an agent-agnostic skill so any AI agent (Claude Code, Gemini, OpenCode, etc.) can invoke `/doc-extractor <path>` to extract structured JSON from supply chain documents.
- **Technical Boundary:**
  - `SKILL.md` at repo root — minimal frontmatter (`name`, `description` only), no agent-specific flags
  - References `${SKILL_DIR}/scripts/parse_vision.py` — agent-agnostic path variable
  - Instructions: run script, capture stdout, interpret exit codes, format response
  - The repo root IS the publishable skill — no nested packaging directory
- **Verification Criteria (Definition of Done):**
  - `/doc-extractor test_docs/(spec_sheet)(Clean_L-Lysine)(ProTab)(Rev1).pdf` returns valid JSON in a Claude Code session
  - Exit code errors produce actionable agent messages
  - Skill appears in skill listing

### EPIC-006: Snapshot Eval Framework

- **Status:** `Complete`
- **Dependencies:** EPIC-004
- **Business Objective:** Create a snapshot-based regression suite so any change to schemas, prompts, or models can be validated against known-good extractions. Also establish the intake pipeline so new documents can be added to the corpus and approved in one command. Foundation for future autoresearch integration (<https://github.com/karpathy/autoresearch>).
- **Technical Boundary:**
  - `evals/snapshot.py` — entry point (approve, compare, main); delegates to `_diff.py` and `_report.py`
  - `evals/_diff.py` — diff primitives: `strict_diff()` for regression, `lenient_diff()` for cross-model (case-insensitive + similarity scoring via `difflib`)
  - `evals/_report.py` — Markdown report builder for `compare-models`; writes to `evals/reports/`
  - `evals/usage.md` — full usage reference
  - Commands:
    - `uv run python evals/snapshot.py approve <file>` — runs extraction, saves output to `evals/snapshots/<stem>.json`
    - `uv run python evals/snapshot.py approve --all` — batch-approves all docs in `test_docs/`
    - `uv run python evals/snapshot.py compare` — re-runs all approved docs, diffs against snapshots, field-level pass/fail
    - `uv run python evals/snapshot.py compare <file>` — single-doc diff
    - `uv run python evals/snapshot.py --model <name> approve --all` — seed model-specific snapshots under `evals/snapshots/<model>/`
    - `uv run python evals/snapshot.py --model <name> compare` — regression check against model-specific snapshots
    - `uv run python evals/snapshot.py compare-models <baseline> <candidate>` — structured cross-model comparison report (no re-extraction); report saved to `evals/reports/`
  - `evals/snapshots/` — default snapshots (gemini-2.5-flash baseline)
  - `evals/snapshots/<model>/` — per-model snapshot dirs when `--model` flag is used
  - `evals/reports/` — generated Markdown reports from `compare-models`
  - `test_docs/manifest.json` — maps filenames → expected `document_type`
  - Diff strategy: exact match on scalars, order-insensitive match on arrays, ignore `extracted_date` and `confidence` (change every run)
  - Cross-model diff: case-only differences → "soft match"; string similarity ≥ 75% → "soft match"; genuine value changes → "hard diff"
  - API key routing: Gemini models use `GEMINI_DOC_EXTRACTOR_KEY`; Gemma models (model name starts with `gemma`) use `GEMMA_FREE_API`
- **Verification Criteria (Definition of Done):**
  - `uv run python evals/snapshot.py approve --all` seeds all snapshots without errors
  - `uv run python evals/snapshot.py compare` passes with 0 regressions on the seeded snapshots
  - Adding a new doc, approving it, and running compare includes it in the suite automatically
  - `extracted_date` is excluded from diffs so comparisons don't flap
  - `compare-models` produces a structured report with summary, per-doc diff sections, and matched list

### EPIC-007: Gemma 4 Support

- **Status:** `Pending`
- **Dependencies:** EPIC-006
- **Business Objective:** Enable Gemma 4 models as a free-tier alternative to
  Gemini, eliminating per-token cost while maintaining extraction quality.
- **Blocker (discovered during EPIC-006):** Gemma models reject
  `response_mime_type="application/json"` + `response_schema` with HTTP 400
  "invalid argument". This is a Gemini-only feature. Gemma requires a different
  extraction path: prompt it to return JSON, parse the output text manually,
  and validate against the Pydantic schema. Additionally, Gemma is only
  available on free-tier API accounts — paid accounts receive HTTP 400.
  A separate `GEMMA_FREE_API` env var is already wired up in `parse_vision.py`.
- **Technical Boundary:**
  - Add a `_extract_gemma()` path in `parse_vision.py`:
    - No `response_mime_type` or `response_schema` in `GenerateContentConfig`
    - Append explicit JSON output instruction to the prompt
    - Strip markdown code fences from response text before parsing
    - Validate output with `ExtractionResult.model_validate_json()`
  - Route to `_extract_gemma()` when `model.startswith("gemma")`; existing
    `_extract_gemini()` path unchanged
  - Run `compare-models` against Gemini Flash and Pro baselines
  - Tune prompt if classification or field quality degrades
- **Verification Criteria (Definition of Done):**
  - `uv run python evals/snapshot.py --model gemma-4-26b-a4b-it approve --all`
    completes without errors
  - `compare-models gemini-2.5-flash gemma-4-26b-a4b-it` shows ≥85% field match
  - No misclassifications on document types present in the test corpus
  - `GEMMA_FREE_API` is documented in `CLAUDE.md` and `SKILL.md`

### EPIC-008: Multi-Model Quality Baseline

- **Status:** `Pending`
- **Dependencies:** EPIC-006, EPIC-007
- **Business Objective:** Establish a quality benchmark across all four target
  models so the best cost/quality tradeoff can be chosen for production.
- **Models to benchmark:**
  1. `gemini-2.5-pro-preview` — highest quality, most expensive (baseline)
  2. `gemini-2.5-flash` — default, good quality, low cost
  3. `gemma-4-26b-a4b-it` — free tier, large model
- **Technical Boundary:**
  - Seed snapshots for all four models (`--model` flag, one run each)
  - Run `compare-models` for each model against the Pro baseline
  - Document field-match % and misclassification count per model
  - Record findings in `.ai/memory.md` as the permanent quality record
- **Verification Criteria (Definition of Done):**
  - All four model snapshot dirs exist under `evals/snapshots/`
  - Comparison report generated and findings recorded
  - Recommended default model documented with rationale

### EPIC-009: LABEL_ORDER_ACK Schema

- **Status:** `Complete`
- **Dependencies:** EPIC-002
- **Business Objective:** Support label vendor order acknowledgements — documents
  sent by the label printer to confirm they received and accepted a purchase order.
  Distinct from `LABEL_PROOF` (artwork approval) and `INVOICE` (billing): these
  confirm quantities, pricing, AND technical print specifications in a single document.
- **Context:** Two test documents added to corpus: `(order_acknowledgement)(423747)(BL6).pdf`
  and `(order_acknowledgement)(530476)(BL5-b).pdf`. Expected type `LABEL_ORDER_ACK`
  is already in `test_docs/manifest.json`.
- **Technical Boundary:**
  - Add `LABEL_ORDER_ACK = "LABEL_ORDER_ACK"` to `DocumentType` enum
  - Add `LabelOrderAckPayload` Pydantic model to `scripts/schemas/` with fields:
    - `date` (YYYY-MM-DD)
    - `vendor_name` — label printer name
    - `acknowledgement_number` — vendor's internal confirmation/order number
    - `po_number` — buyer's PO number being acknowledged
    - `line_items[]` — each item has: `description`, `quantity` [number],
      `quantity_unit` (e.g. 'label', 'roll'), `unit_price`, `total`,
      plus technical specs: `label_size`, `substrate`, `inks`
    - `grand_total`
    - `delivery_date` (YYYY-MM-DD, optional)
  - Add `LABEL_ORDER_ACK` entry to `PAYLOAD_SCHEMA_MAP`
  - Add classification definition to `build_classification_prompt()`
  - Add extraction rules to `_FIELD_RULES` in `prompts.py`
  - Seed snapshots: `uv run python evals/snapshot.py approve --all`
- **Verification Criteria (Definition of Done):**
  - Both test documents classify as `LABEL_ORDER_ACK` with confidence ≥ 0.9
  - `line_items` extract correctly with quantities and at least one technical spec
  - `uv run pytest` passes with new schema tests
  - Snapshots approved and `compare` passes
