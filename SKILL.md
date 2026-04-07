---
name: doc-extractor
description: Extract structured JSON from a supply chain document (PDF, PNG, JPG, WEBP) using Google Gemini. Invoke when the user runs /doc-extractor <path> or asks to extract or parse a supply chain document.
disable-model-invocation: true
allowed-tools:
  - Bash(python *)
---

# doc-extractor

Extract structured JSON from a supply chain document (PDF, PNG, JPG, WEBP).

## Arguments

The invocation is: `/doc-extractor <path> [--type TYPE]`

- `<path>` — required. Absolute or relative path to the document. It may be absolute or relative to the project root.
- `--type TYPE` — optional. If you already know the document type from context, pass it here to skip the classification pass and save one API call. Valid values: `COA`, `INVOICE`, `QUOTE`, `PRODUCT_SPEC_SHEET`, `PACKAGING_SPEC_SHEET`, `LABEL`, `LABEL_PROOF`, `PAYMENT_PROOF`, `UNKNOWN`.

## Execution

For best results and to eliminate numeric hallucinations (especially on dense tabular data like COAs and Invoices), use the hybrid extraction pipeline:

```bash
# Step 1: Pre-process with local text extraction
uv run python ${SKILL_DIR}/scripts/extract_text.py "<path>" > context.md

# Step 2: Extract vision context with the pre-processed text
uv run python ${SKILL_DIR}/scripts/parse_vision.py "<path>" --text-context context.md
```

Alternatively, you can run without text context:
```bash
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
