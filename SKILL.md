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

1. ONLY use script — `uv run python scripts/parse_vision.py` from skill dir
2. NEVER parse docs directly — no built-in vision or other methods
3. NEVER offer alternatives — no "I can try to analyze it"
4. IF SCRIPT FAILS — follow exit codes below, STOP
5. NO fallback methods

## Arguments

Invocation: `/doc-extractor <path> [options]`

- `<path>` / `--url <URL>` — required. Local file, directory (batch), or remote URL
- `--type TYPE` — optional. Skip classification pass. Valid: `COA`, `INVOICE`, `QUOTE`, `PRODUCT_SPEC_SHEET`, `PACKAGING_SPEC_SHEET`, `LABEL`, `LABEL_PROOF`, `LABEL_ORDER_ACK`, `PAYMENT_PROOF`, `UNKNOWN`
- `--skip-liteparse` — optional. Disable hybrid text extraction, vision-only (not recommended, more hallucinations)
- `--output <file.json>` — optional. Write JSON to file instead of stdout. Recommended for large payloads
- `--pages "<spec>"` — optional. Slice PDF pages before extraction (e.g., `"1-3"`, `"1,3,5"`). PDF only
- `--debug` — optional. Dump raw LLM response to stderr on validation failure
- `--no-summary` — optional. Disable compact summary on stderr (enabled by default)
- `--verbose` — optional. Show progress on stderr (suppressed by default; warnings/errors always shown)

## Execution

**Run from skill directory** so `uv` resolves deps from `pyproject.toml`.

Skip hybrid pipeline (Vision + Local Text) with `--skip-liteparse`.

```bash
# Recommended: save JSON to file (summary + quiet on by default)
cd ${SKILL_DIR} && uv run python scripts/parse_vision.py "<path>" --output "<path>.json"

# Batch process directory
cd ${SKILL_DIR} && uv run python scripts/parse_vision.py "path/to/folder" --output "results.json"

# With type hint (single pass: extract directly)
cd ${SKILL_DIR} && uv run python scripts/parse_vision.py "<path>" --type <TYPE> --output "<path>.json"

# Without --output (JSON to stdout — avoid for large payloads)
cd ${SKILL_DIR} && uv run python scripts/parse_vision.py "<path>"
```

Capture stderr for summaries, warnings, errors. With `--output`, stdout empty on success.

## Exit Code Handling

| Exit code | Meaning | Action |
|-----------|---------|--------|
| `0` | Success | Relay summary from stderr. If `--output` used, tell user file path. Only read full JSON if user asks |
| `1` | Missing API key | Tell user: "GEMINI_DOC_EXTRACTOR_KEY not set. Get key at `https://aistudio.google.com/apikey` and run: `export GEMINI_DOC_EXTRACTOR_KEY='your-key-here'`" |
| `2` | Bad file or path | Show stderr error. Confirm file exists + supported type (`.pdf`, `.png`, `.jpg`, `.jpeg`, `.webp`) |
| `3` | API failure | Show stderr error. Suggest retry — transient errors resolve on their own |

## Success Response Format

On exit 0:

1. Tell user where JSON saved (`--output` path)
2. Relay summary from stderr as human-readable result
3. Only show full JSON if user explicitly asks
