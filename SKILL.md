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

Extract structured JSON from a supply chain document or batch process a directory (PDF, PNG, JPG, WEBP)

## MANDATORY RESTRICTIONS - DO NOT VIOLATE

1. ONLY use the script - Execute the script via `uv run python scripts/parse_vision.py` from the skill directory
2. NEVER parse documents directly - Do NOT try to extract text using built-in vision or any other method
3. NEVER offer alternatives - Do NOT suggest "I can try to analyze it" or similar
4. IF SCRIPT FAILS - Follow the exit code handling rules below and STOP
5. NO fallback methods - Do NOT attempt text extraction any other way

## Arguments

The invocation is: `/doc-extractor <path> [options]`

- `<path>` / `--url <URL>` — required. Provide either a local file path, a directory path (for batch processing all supported files within), or a remote URL to download
- `--type TYPE` — optional. If you already know the document type, pass it here to skip the classification pass. Valid values: `COA`, `INVOICE`, `QUOTE`, `PRODUCT_SPEC_SHEET`, `PACKAGING_SPEC_SHEET`, `LABEL`, `LABEL_PROOF`, `LABEL_ORDER_ACK`, `PAYMENT_PROOF`, `UNKNOWN`
- `--skip-liteparse` — optional. Disable the local text extraction hybrid pipeline and rely strictly on the vision model (not recommended, increases numeric hallucinations)
- `--output <file.json>` — optional. Write the JSON directly to the specified file instead of stdout. Recommended for large payloads to bypass terminal capture limits
- `--pages "<spec>"` — optional. Slice the PDF to specific pages before extraction (e.g., `"1-3"`, `"1,3,5"`). Only applies to PDF files
- `--debug` — optional. Dump the raw LLM response string to stderr if JSON schema validation fails
- `--no-summary` — optional. Disable the compact one-line summary that is printed to stderr after each extraction (enabled by default)
- `--verbose` — optional. Show progress messages on stderr (suppressed by default; warnings and errors always shown)

## Execution

**Important:** Always run from the skill directory so `uv` resolves dependencies from `pyproject.toml`.

If you want to skip the hybrid extraction pipeline (Vision + Local Text), opt-out by passing `--skip-liteparse`

```bash
# Recommended: Save JSON to file (summary + quiet are on by default)
cd ${SKILL_DIR} && uv run python scripts/parse_vision.py "<path>" --output "<path>.json"

# Batch process an entire directory
cd ${SKILL_DIR} && uv run python scripts/parse_vision.py "path/to/folder" --output "results.json"

# With type hint (single pass: extract directly)
cd ${SKILL_DIR} && uv run python scripts/parse_vision.py "<path>" --type <TYPE> --output "<path>.json"

# Without --output (JSON goes to stdout — avoid for large payloads)
cd ${SKILL_DIR} && uv run python scripts/parse_vision.py "<path>"
```

Capture stderr for summary lines, warnings, and errors. When using `--output`, stdout is empty on success.

## Exit Code Handling

| Exit code | Meaning | Action |
|-----------|---------|--------|
| `0` | Success | Relay the summary line(s) from stderr. If `--output` was used, tell the user the file path. Only read the full JSON if the user asks |
| `1` | Missing API key | Tell the user: "GEMINI_DOC_EXTRACTOR_KEY is not set. Get a key at `https://aistudio.google.com/apikey` and run: `export GEMINI_DOC_EXTRACTOR_KEY='your-key-here'`" |
| `2` | Bad file or path | Show the stderr error message. Confirm the file exists and is a supported type (`.pdf`, `.png`, `.jpg`, `.jpeg`, `.webp`) |
| `3` | API failure | Show the stderr error message. Suggest the user retry — transient errors (rate limits, server errors) resolve on their own |

## Success Response Format

On exit code 0:

1. Tell the user where the JSON file was saved (the `--output` path)
2. Relay the summary line(s) from stderr as the human-readable result
3. Only read and display the full JSON if the user explicitly asks for it
