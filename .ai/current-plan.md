# Current Plan

## Status: Schema Normalization & Generic Payload (Completed)

## What Was Done (Current Session)
- **Schema Normalization**: Standardized `vendor_product_id` and `buyer_product_id` across all relevant schemas (`_coa`, `_invoice`, `_quote`, `_product_spec`, `_packaging_spec`, `_label_proof`, `_label_order_ack`) to ensure robust ERP integration mapping.
- **Technical Label Specs Refactor**: Consolidated redundant label specification fields into a shared `TechnicalLabelSpecs` model in `_shared.py`, drying up `_label_order_ack`, `_label_proof`, and `_packaging_spec`.
- **Dynamic Quotes**: Completely refactored `_quote.py` to support dynamic `QuotedItem` lists containing `technical_details` (as a key-value array), volume-based `pricing_tiers`, and `additional_fees`.
- **Billing & Shipping**: Added `bill_to`, `ship_to`, `shipping_handling`, and `tax_amount` to invoices and order acknowledgements.
- **Generic Fallback**: Replaced the static `UNKNOWN` string with a fully structured `GenericPayload` in `_generic.py`. Unsupported documents now extract dynamic `key_value_pairs`, full tabular data (`tables`), `title`, and AI-generated `summary`.
- **Documentation**: Simplified `docs/PRD.md` to point to the Pydantic models as the absolute source of truth. Removed the hardcoded test documents table from `docs/roadmap.md` since the test runner discovers documents dynamically.
- **Test Corpus**: Added five new quote documents to `test_docs/manifest.json`.

## What Was Done (2026-04-07, EPIC-010 & EPIC-011)

- Implemented the Hybrid Extraction Pipeline by leveraging `liteparse`.
- Added `liteparse` dependency to `pyproject.toml`.
- Created `scripts/extract_text.py` as a standalone CLI to pre-process text locally.
- Updated `scripts/parse_vision.py` with a `--use-liteparse` flag to run the NLP step locally in-memory and append it to Gemini via the `contents` payload.
- Refined `build_extraction_prompt_for_type()` in `scripts/prompts.py` to accept the pre-processed text and resolve data conflicts (preferring local text for spellings and numbers).
- Modified `SKILL.md` usage instructions to favor the hybrid pipeline execution (`--use-liteparse`).
- Updated `evals/snapshot.py` to integrate the hybrid pipeline explicitly for snapshot generation using the unified flag.
- Replaced `difflib` with `rapidfuzz` to enable order-agnostic fuzzy matching via `token_set_ratio`.
- Added recursive `count_leaf_nodes()` to `evals/_diff.py` to calculate exact denominator for accuracy metrics per document.
- Restructured `evals/_report.py` to decouple soft matches from the Hard Diff table and inject the (X/Y fields) accuracy metric into headers.

## Blockers Discovered

- **Gemma HTTP 400:** `response_schema` / `response_mime_type="application/json"` are Gemini-only. Gemma rejects them. Needs a separate extraction path (EPIC-007).
- **Gemma paid account restriction:** Google blocks Gemma on paid API keys. `GEMMA_FREE_API` env var is wired up but useless until the structured-output blocker is fixed.

## What's Next
- Re-run the baseline test corpus using `uv run python evals/snapshot.py --model gemini-2.5-flash approve --all`.
- Re-run the candidate test corpus using `uv run python evals/snapshot.py --model gemini-3.1-pro-preview approve --all`.
- Run the cross-model diff using `uv run python evals/snapshot.py compare-models gemini-2.5-flash gemini-3.1-pro-preview` to validate the new schemas and generic fallback behavior.
- Address the Gemma 4 free-tier constraints (EPIC-007).

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
