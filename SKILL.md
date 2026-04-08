---
name: doc-extractor
description: Extract structured JSON from a supply chain document (PDF, PNG, JPG, WEBP) using Google Gemini. Invoke when the user runs /doc-extractor <path> or asks to extract or parse a supply chain document.
compatibility: Requires Python 3.13+ and the GEMINI_DOC_EXTRACTOR_KEY environment variable.
author: julioccorderoc
version: "0.1.0"
metadata:
  openclaw:
    requires:
      env:
        - GEMINI_DOC_EXTRACTOR_KEY
      bins:
        - python
    primaryEnv: GEMINI_DOC_EXTRACTOR_KEY
    emoji: "📦"
disable-model-invocation: true
allowed-tools:
  - Bash(python *)
---

# doc-extractor

Extract structured JSON from a supply chain document (PDF, PNG, JPG, WEBP).

## MANDATORY RESTRICTIONS - DO NOT VIOLATE

1. **ONLY use the script** - Execute the script `python scripts/parse_vision.py`
2. **NEVER parse documents directly** - Do NOT try to extract text using built-in vision or any other method
3. **NEVER offer alternatives** - Do NOT suggest "I can try to analyze it" or similar
4. **IF SCRIPT FAILS** - Follow the exit code handling rules below and STOP.
5. **NO fallback methods** - Do NOT attempt text extraction any other way

## Arguments

The invocation is: `/doc-extractor <path> [options]`

- `<path>` / `--url <URL>` — required. Provide either a local file path or a remote URL to download.
- `--type TYPE` — optional. If you already know the document type, pass it here to skip the classification pass. Valid values: `COA`, `INVOICE`, `QUOTE`, `PRODUCT_SPEC_SHEET`, `PACKAGING_SPEC_SHEET`, `LABEL`, `LABEL_PROOF`, `LABEL_ORDER_ACK`, `PAYMENT_PROOF`, `UNKNOWN`.
- `--use-liteparse` — optional. Extract local text for a hybrid extraction pipeline to reduce numeric hallucinations.
- `--output <file.json>` — optional. Write the JSON directly to the specified file instead of stdout. Recommended for large payloads to bypass terminal capture limits.
- `--pages "<spec>"` — optional. Slice the PDF to specific pages before extraction (e.g., `"1-3"`, `"1,3,5"`). Only applies to PDF files.
- `--debug` — optional. Dump the raw LLM response string to stderr if JSON schema validation fails.


## Execution

For best results and to eliminate numeric hallucinations (especially on dense tabular data like COAs and Invoices), use the hybrid extraction pipeline flag (`--use-liteparse`). This processes the document's text locally and passes it to the vision model in-memory.

```bash
# Recommended: Hybrid extraction (Vision + Local Text)
python ${SKILL_DIR}/scripts/parse_vision.py "<path>" --use-liteparse

# Without type hint (two-pass: classify then extract)
python ${SKILL_DIR}/scripts/parse_vision.py "<path>"

# With type hint (single pass: extract directly)
python ${SKILL_DIR}/scripts/parse_vision.py "<path>" --type <TYPE>
```

Capture both stdout (JSON result) and stderr (progress / error messages).

## Exit Code Handling

| Exit code | Meaning | Action |
|-----------|---------|--------|
| `0` | Success | Parse stdout as JSON and present the extracted data. Summarize `document_type`, `confidence`, and key payload fields. |
| `1` | Missing API key | Tell the user: "GEMINI_DOC_EXTRACTOR_KEY is not set. Get a key at `https://aistudio.google.com/apikey` and run: `export GEMINI_DOC_EXTRACTOR_KEY='your-key-here'`" |
| `2` | Bad file or path | Show the stderr error message. Confirm the file exists and is a supported type (`.pdf`, `.png`, `.jpg`, `.jpeg`, `.webp`). |
| `3` | API failure | Show the stderr error message. Suggest the user retry — transient errors (rate limits, server errors) resolve on their own. |

## Success Response Format

On exit code 0, display:

1. The raw JSON (in a code block)
2. A brief human-readable summary:
   - Document type and confidence
   - Key extracted fields (vendor name, invoice number, lot number, product name, etc.)
   - Any null fields that might indicate extraction gaps
