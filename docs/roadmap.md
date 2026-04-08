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

The `test_docs/` folder contains a comprehensive test corpus of PDFs and images covering all supported supply chain document types. Each Epic that adds or modifies schema support must be tested against these files.

*Note: The explicit document list has been removed to reduce maintenance overhead. The test runner dynamically discovers all valid files in the `test_docs/` directory.*

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
- **Business Objective:** Establish a quality benchmark across all four target models so the best cost/quality tradeoff can be chosen for production.
- **Models to benchmark:**
  1. `gemini-3.1-pro-preview` — highest quality, most expensive (baseline)
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
    - `doc_number` — vendor's internal confirmation/order number
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

### EPIC-010: Hybrid Extraction Pipeline (Liteparse + Gemini)

- **Status:** `Complete`
- **Dependencies:** EPIC-002, EPIC-003
- **Business Objective:** Eliminate numeric hallucinations and row skipping in dense tabular data (like COAs and Invoices) by augmenting the visual encoder with deterministic textual data.
- **Context:** By executing `liteparse` locally before the API call, we can provide a deterministic Markdown representation of the table layout, bridging the vision-language gap.
- **Technical Boundary:**
  - Add `liteparse` to `pyproject.toml` dependencies.
  - Create `scripts/extract_text.py` as a standalone tool that uses `liteparse` to parse a file and output text to `stdout`.
  - Add a `--use-liteparse` flag to `scripts/parse_vision.py` to process the document text locally in-memory.
  - If `--use-liteparse` is provided, append the OCR text to the `contents` array sent to Gemini, alongside the `uploaded_file`.
  - Inject explicit conflict resolution instructions into `build_extraction_prompt_for_type()`:
    - "Base structure and context on the visual document."
    - "Base exact spellings, numerical values, and lot numbers on the provided text extraction."
    - "If the provided text is garbled, irrelevant, or missing data, trust the image."
  - Update `SKILL.md` to instruct the agent on executing the single-command hybrid extraction: `uv run python scripts/parse_vision.py <file> --use-liteparse`.
- **Verification Criteria (Definition of Done):**
  - `scripts/extract_text.py` runs independently and prints parsed text.
  - `scripts/parse_vision.py` accepts the `--use-liteparse` flag and executes OCR in-memory.
  - Snapshots run via `evals/snapshot.py approve --all` complete successfully using the new flag.
  - `compare-models` running the new pipeline against the old baseline shows zero degraded fields on `COA` and `INVOICE` documents.

### EPIC-011: Quantitative Eval Reporting & Advanced Fuzzy Math

- **Status:** `Complete`
- **Dependencies:** EPIC-006
- **Business Objective:** Upgrade the cross-model evaluation report to provide objective, quantitative accuracy scores per document (e.g., "98% accuracy"), and eliminate false positives in the diffing logic using token-based fuzzy matching.
- **Context:** The current `compare-models` report uses basic `difflib` string matching, which penalizes correct extractions if word order changes (e.g., "100 capsules" vs "100 count"). Furthermore, failing 3 fields on a 150-field COA is drastically different than failing 3 fields on a 5-field invoice; the report needs to calculate the denominator to provide an objective accuracy percentage.
- **Technical Boundary:**
  - Add `rapidfuzz` to `pyproject.toml` dependencies.
  - In `evals/_diff.py`, replace `difflib.SequenceMatcher` with `rapidfuzz.fuzz.token_set_ratio` for the `lenient_diff` calculation (using an 85% threshold).
  - Add a recursive `count_leaf_nodes(json_obj)` function to calculate `total_fields` for a given snapshot (excluding ignored fields like `extracted_date`).
  - Restructure `evals/_report.py` to strictly separate diff types: Soft matches (`≈`) must NOT appear in the Hard Differences table.
  - Inject the calculated accuracy score into the markdown headers of the generated report (e.g., `### COA_100X_Run-18.pdf — 96.5% Match (112/116 fields)`).
- **Verification Criteria (Definition of Done):**
  - String arrays with reordered words (e.g., `"Vitamin C 500mg"` vs `"500mg Vitamin C"`) evaluate as a Soft Match using `rapidfuzz`.
  - The "Hard Differences" section of the generated markdown report exclusively contains genuine data mismatches (`✗`), completely devoid of case or fuzzy matches.
  - Every document in the report displays its specific `(matches/total)` ratio and percentage.

### EPIC-012: The Objective Function (F1 Score)

- **Status:** `Pending`
- **Dependencies:** EPIC-011
- **Business Objective:** Establish a continuous, scalar reward signal required for autonomous LLM optimization (Karpathy's "fixed metric"). Binary pass/fail regression is insufficient for automated hyperparameter/prompt tuning.
- **Context:** To implement autonomous research, an agent needs an F1 score (0.0 to 100.0) quantifying extraction accuracy relative to a human-verified Ground Truth, punishing both hallucinations (False Positives) and omissions (False Negatives).
- **Technical Boundary:**
  - Create `evals/source_of_truth/` directory.
  - Populate `source_of_truth` with the highest-quality existing snapshots, manually verified and scrubbed of any errors.
  - Create `evals/score.py`.
  - Implement recursive Dict traversal to calculate true positives (using `rapidfuzz` from EPIC-011), false positives, and false negatives.
  - Execute `parse_vision.py` over `test_docs/`, compare against `source_of_truth/`.
  - Ensure the script outputs a solitary float to stdout (e.g., `84.5`) representing the global F1 score across the dataset.
- **Verification Criteria (Definition of Done):**
  - `uv run python evals/score.py` executes successfully.
  - Output is a single deterministic float value to stdout.
  - Adding a hallucinated field to a parsed JSON correctly lowers Precision.
  - Deleting a required field from a parsed JSON correctly lowers Recall.

### EPIC-013: Autoresearch Orchestrator

- **Status:** `Pending`
- **Dependencies:** EPIC-012
- **Business Objective:** Close the autonomous optimization loop. Deploy an LLM agent that iteratively rewrites extraction prompts, runs the objective function (`score.py`), and commits or reverts its own code based on the scalar metric.
- **Context:** Direct port of the `karpathy/autoresearch` architecture. The "target space" is `scripts/prompts.py` and `scripts/schemas/`. The "loop" modifies code, evaluates, and decides.
- **Technical Boundary:**
  - Create `program.md` at project root. This is the human steering interface (e.g., "Focus on extracting line item prices correctly").
  - Create `scripts/autoresearch.py` orchestrator.
  - Implement the Execution Loop:
    1. Read `program.md`, `prompts.py`, and target schemas.
    2. Invoke Gemini/Claude API (system prompt: "You are an AI optimization researcher. Propose code diffs to increase the F1 score.").
    3. Apply the generated code modifications to `scripts/prompts.py` or schemas.
    4. Execute `uv run python evals/score.py`.
    5. Compare `new_score` vs `best_score`.
    6. If `new_score > best_score`, log success, update `best_score`. Else, `git checkout -- scripts/` (Revert) and feedback the failure mode to the LLM context.
  - Enforce a strict iteration budget (e.g., `MAX_ITERATIONS = 10`) to prevent runaway API costs.
- **Verification Criteria (Definition of Done):**
  - `uv run python scripts/autoresearch.py` executes an uninterrupted loop.
  - The script successfully modifies `prompts.py`.
  - The script successfully reverts modifications when the F1 score decreases.
  - The script terminates cleanly when `MAX_ITERATIONS` is hit, leaving the repository in the highest-scoring state.

### EPIC-014: Datalab.to Hybrid Extraction Sandbox

- **Status:** `Complete`
- **Dependencies:** EPIC-006
- **Business Objective:** Evaluate if Datalab.to provides higher fidelity structured extraction (especially for dense tables like COAs) than pure Gemini, by building a parallel sandbox and running head-to-head snapshot comparisons without altering the core production script.
- **Context:** Datalab.to provides purpose-built document layout parsing and provides field-level citations. We will use a Two-Pass Hybrid: Pass 1 uses `google-genai` to classify the document, and Pass 2 maps our existing Pydantic schemas to Datalab's JSON Schema format for extraction.
- **Technical Boundary:**
  - Create an experimental directory: `experiments/datalab_hybrid/`.
  - Create a sandbox `requirements.txt` containing `datalab-python-sdk`.
  - Create `experiments/datalab_hybrid/parse_datalab.py` that implements the hybrid handoff:
    1. Call Gemini to classify the document.
    2. Dynamically translate the targeted Pydantic schema to JSON Schema (`target_class.model_json_schema()`).
    3. Invoke Datalab's `/extract` API via the SDK.
    4. Validate and re-hydrate the result using Pydantic.
  - Adapt `evals/snapshot.py` to support an `--engine datalab` (or similar) flag. If flagged, `run_extraction()` routes to the new sandbox script instead of `scripts/parse_vision.py`.
  - Generate a new set of snapshots for the Datalab engine using `approve --all`.
  - Run a `compare-models` report to output a markdown diff of Gemini vs Datalab.
- **Verification Criteria (Definition of Done):**
  - `parse_datalab.py` correctly imports our shared schemas and successfully extracts JSON.
  - `uv run python evals/snapshot.py --engine datalab approve --all` seeds complete snapshots.
  - `uv run python evals/snapshot.py compare-models gemini-2.5-flash datalab` generates a diff report in `evals/reports/`.
  - Core production (`scripts/parse_vision.py`) remains entirely untouched.

### EPIC-015: Agentic Ergonomics & CLI Expansion

- **Status:** `Complete`
- **Dependencies:** EPIC-010
- **Business Objective:** Make `parse_vision.py` easier for autonomous agents to use by supporting remote URLs, targeted page slicing, and direct file output to bypass terminal stdout limits.
- **Context:** Large PDFs overwhelm context limits, and agents struggle with stdout capture limits for massive JSON payloads. Supporting URLs enables cloud-native file processing.
- **Technical Boundary:**
  - Add `--url` flag to `parse_vision.py`. If provided, download the file to a temp directory before passing to Gemini.
  - Add `--output <file.json>` flag. If provided, write the JSON directly to the file instead of stdout.
  - Add `--pages "1-3"` flag (or similar syntax). Implement a preprocessing step (e.g., using `pypdf`) to slice the PDF to the specified pages before extraction.
  - Add `--debug` or `--include-raw` flag to dump the raw LLM response string when Pydantic validation fails.
  - Update `SKILL.md` to document the new arguments.
- **Verification Criteria (Definition of Done):**
  - Script successfully downloads and extracts from a valid public `--url`.
  - Script correctly writes valid JSON to the file path specified in `--output`.
  - Script successfully slices a multi-page PDF using `--pages` and extracts only from the target pages.
  - `--debug` flag prints the raw text string from the model on validation failure.

### EPIC-016: Format Preprocessing Layer (.xlsx/.docx to .pdf)

- **Status:** `Pending`
- **Dependencies:** EPIC-015
- **Business Objective:** Expand the supported file types to include Office documents (Excel, Word) which are extremely common in supply chain quotes and specifications.
- **Context:** Gemini Vision cannot natively process `.xlsx` or `.docx` files. We need a local conversion or text-extraction layer to bridge this gap.
- **Technical Boundary:**
  - Introduce a preprocessing utility (possibly extending `extract_text.py` or using a tool like LibreOffice/LiteParse underneath) that detects `.xlsx` and `.docx` extensions.
  - Automatically convert these formats to `.pdf` (or extract their layout text) before passing them to the classification/extraction pipeline.
  - Remove strict extension blocking for `.xlsx` and `.docx` in the CLI validation.
- **Verification Criteria (Definition of Done):**
  - Running `parse_vision.py` on an `.xlsx` file processes successfully and returns valid JSON.
  - Running `parse_vision.py` on a `.docx` file processes successfully and returns valid JSON.
  - Temp files generated during conversion are properly cleaned up.

### EPIC-017: Batch Directory Processing

- **Status:** `Pending`
- **Dependencies:** EPIC-015
- **Business Objective:** Enable agents to process bulk document dumps (e.g., "extract all 50 invoices from this folder") in a single command.
- **Context:** Currently the script only accepts a single file path. Looping in bash is error-prone for agents.
- **Technical Boundary:**
  - Update `parse_vision.py` to accept a directory path as the `<path>` argument (or via a `--batch` flag).
  - Iterate through all supported files in the directory.
  - Classify and extract each file.
  - Output a combined JSON array of `ExtractionResult` objects.
  - Handle partial failures gracefully (e.g., file 3 fails, but files 1, 2, 4, 5 succeed and are returned).
- **Verification Criteria (Definition of Done):**
  - Passing a directory path outputs a valid JSON array of extraction results.
  - Non-supported files in the directory are safely skipped.
  - At least one file failing API extraction does not crash the entire batch process.

## Minor Backlog

- [ ] Add `COA_RAW` document type and schema parsing based on PRD
