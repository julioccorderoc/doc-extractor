# Current Plan

## Status: EPIC-010 Complete — EPIC-007 Up Next

## What Was Done (2026-04-07, EPIC-010)

- Implemented the Hybrid Extraction Pipeline by leveraging `liteparse`.
- Added `liteparse` dependency to `pyproject.toml`.
- Created `scripts/extract_text.py` as a standalone CLI to pre-process text locally.
- Updated `scripts/parse_vision.py` to support `--text-context FILE` and pass it to Gemini via the `contents` payload.
- Refined `build_extraction_prompt_for_type()` in `scripts/prompts.py` to accept the pre-processed text and resolve data conflicts (preferring local text for spellings and numbers).
- Modified `SKILL.md` usage instructions to favor the hybrid pipeline execution.
- Updated `evals/snapshot.py` to integrate the hybrid pipeline explicitly for snapshot generation.

## What Was Done (2026-04-06, EPIC-006)

- `evals/snapshot.py` built with `approve`, `approve --all`, `compare`, `compare <file>` commands
- `evals/snapshots/` seeded with all test docs (gemini-2.5-flash baseline)
- `test_docs/manifest.json` created
- **Multi-model support added (extended scope):**
  - `--model <name>` flag routes snapshots to `evals/snapshots/<model>/` and sets `GEMINI_MODEL` for extraction
  - `compare-models <baseline> <candidate>` produces a structured report (header, summary, per-doc diff sections, matched list) — no re-extraction needed
  - API key routing: Gemma models use `GEMMA_FREE_API`, Gemini models use `GEMINI_DOC_EXTRACTOR_KEY`

## What Was Done (2026-04-06, EPIC-009)

- Completed EPIC-009: Created `LABEL_ORDER_ACK` schema for label vendor order acknowledgements
- Added `LabelOrderAckPayload` and `LabelOrderAckLineItem` to `scripts/schemas/_label_order_ack.py`
- Added `LABEL_ORDER_ACK` to `DocumentType` enum
- Updated `scripts/schemas/_envelope.py` to correctly map the new type
- Refined classification and extraction prompts in `scripts/prompts.py`
- Verified schema and union dispatch unit tests pass
- Updated `docs/PRD.md` and `docs/roadmap.md` to reflect the new schema

## What Was Done (2026-04-07, EPIC-011)

- Replaced `difflib` with `rapidfuzz` to enable order-agnostic fuzzy matching via `token_set_ratio`.
- Added recursive `count_leaf_nodes()` to `evals/_diff.py` to calculate exact denominator for accuracy metrics per document.
- Restructured `evals/_report.py` to decouple soft matches from the Hard Diff table and inject the (X/Y fields) accuracy metric into headers.

## Blockers Discovered

- **Gemma HTTP 400:** `response_schema` / `response_mime_type="application/json"` are Gemini-only. Gemma rejects them. Needs a separate extraction path (EPIC-007).
- **Gemma paid account restriction:** Google blocks Gemma on paid API keys. `GEMMA_FREE_API` env var is wired up but useless until the structured-output blocker is fixed.

## What's Next (EPIC-007)

- Add `_extract_gemma()` path in `parse_vision.py`:
  - No `response_mime_type` / `response_schema`
  - Append explicit JSON instruction to prompt
  - Strip markdown fences, validate with `ExtractionResult.model_validate_json()`
- Route on `model.startswith("gemma")` — existing Gemini path unchanged
- Then run EPIC-008: seed all four model snapshot dirs and compare

## Key Decisions Made

- SDK: `google-genai` (not legacy `google-generativeai`)
- Default model: `gemini-2.5-flash`
- Schema approach: Pydantic v2 with `response_schema=ExtractionResult` (Gemini only)
- `PackagingSpecSheetPayload` before `ProductSpecSheetPayload` in union — superset ordering
- Retry strategy: `APIError.code` for status check; 400 is not retried (bad input, not transient)
- Upload split from polling so `finally` cleanup always has a file ref
- Pipeline now utilizes a dual LLM and Local NLP approach (`liteparse`) to minimize numeric hallucinations natively.

### Recent Changes
- Moved `build_extraction_prompt()` from `parse_vision.py` to `scripts/prompts.py` for better decoupling and adherence to SOLID principles.
