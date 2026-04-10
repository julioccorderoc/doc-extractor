---
name: doc-extractor
description: Extract structured JSON from supply chain documents (PDF, PNG, JPG, WEBP) or an entire directory of documents. Invoke when the user runs /doc-extractor <path> or asks to extract/parse a supply chain document or directory
compatibility: Requires Python 3.13+, uv, and the GEMINI_DOC_EXTRACTOR_KEY environment variable
author: julioccorderoc
version: "0.1.0"
metadata:
  openclaw:
    requires:
      env:
        - GEMINI_DOC_EXTRACTOR_KEY
      bins:
        - uv
        - python
    primaryEnv: GEMINI_DOC_EXTRACTOR_KEY
    emoji: "📦"
allowed-tools:
  - Bash(cd * && uv run *)
  - Bash(uv run *)
---

# doc-extractor

Extract structured JSON from supply chain documents or batch process directories (PDF, PNG, JPG, WEBP).

## MANDATORY RESTRICTIONS

1. ONLY use `cd ${SKILL_DIR} && uv run python scripts/parse_vision.py` — no alternatives, no fallbacks
2. NEVER parse docs directly with built-in vision or offer to "try analyzing it"
3. IF SCRIPT FAILS — follow exit codes below, STOP

## Arguments

`/doc-extractor <path> [options]`

- `<path>` / `--url <URL>` — required. Local file, directory (batch), or remote URL
- `--type TYPE` — skip classification. Valid: `COA`, `INVOICE`, `QUOTE`, `PRODUCT_SPEC_SHEET`, `PACKAGING_SPEC_SHEET`, `LABEL`, `LABEL_PROOF`, `LABEL_ORDER_ACK`, `PAYMENT_PROOF`, `UNKNOWN`
- `--output <file.json>` — write JSON to file instead of stdout (recommended for large payloads)
- `--pages "<spec>"` — slice PDF pages before extraction (e.g., `"1-3"`, `"1,3,5"`). PDF only
- `--skip-liteparse` — disable hybrid text extraction, vision-only (more hallucinations)
- `--debug` — dump raw LLM response to stderr on validation failure
- `--schema TYPE|all` — print JSON schema for a document type (or all types) to stdout and exit. No API key needed
- `--no-summary` — disable compact summary on stderr (enabled by default)
- `--verbose` — show progress on stderr (suppressed by default; warnings/errors always shown)
- `--format plain|markdown` — summary format: `plain` (pipe-delimited, default) or `markdown` (table row)
- `--summary-only` — classify only (skip extraction). Prints summaries to stderr, no JSON output

## Execution

```bash
# Single file (recommended: save to file; add --type TYPE to skip classification)
cd ${SKILL_DIR} && uv run python scripts/parse_vision.py "<path>" --output "<path>.json"

# Batch: directory of documents
cd ${SKILL_DIR} && uv run python scripts/parse_vision.py "path/to/folder" --output "results.json"
```

Output: single file produces a JSON object; directory produces a JSON array. Capture stderr for summaries/warnings/errors. With `--output`, stdout is empty on success.

## Exit Codes

| Code | Handle |
| ---- | ------ |
| `0` | Relay summary from stderr. If `--output` used, tell user file path. Only read full JSON if user asks |
| `1` | Tell user: "GEMINI_DOC_EXTRACTOR_KEY not set. Get key at `https://aistudio.google.com/apikey` and run: `export GEMINI_DOC_EXTRACTOR_KEY='your-key-here'`" |
| `2` | Show stderr error. Confirm file exists + supported type (`.pdf`, `.png`, `.jpg`, `.jpeg`, `.webp`) |
| `3` | Show stderr error. Suggest retry — transient errors resolve on their own |
