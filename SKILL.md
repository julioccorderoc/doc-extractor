---
name: doc-extractor
description: Extract structured JSON from supply chain documents (PDF, PNG, JPG, WEBP) or an entire directory of documents. Invoke when the user runs /doc-extractor <path> or asks to extract/parse a supply chain document or directory
compatibility: Requires Python 3.13+, uv, and the GEMINI_DOC_EXTRACTOR_KEY environment variable
author: julioccorderoc
version: "0.3.0"
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
- `--type TYPE` — skip classification. Valid: `COA`, `INVOICE`, `QUOTE`, `PRODUCT_SPEC_SHEET`, `PACKAGING_SPEC_SHEET`, `LABEL`, `LABEL_PROOF`, `LABEL_ORDER_ACK`, `PAYMENT_PROOF`, `PACKING_LIST`, `PACKOUT_SHEET`, `UNKNOWN`
- `--output <file.json>` — write JSON to file instead of stdout (recommended for large payloads)
- `--output-dir <dir>` — write one `<stem>.json` per input file. Required for a resumable batch; a single `--output` file cannot record partial progress
- `--skip-existing` — with `--output-dir`, skip inputs whose output already exists and parses. A re-run after a crash only pays for what is still missing
- `--id <string>` — echoed into the output as `source_id`. Join on this, not `source_file`, which is a bare basename and collides across folders
- `--timeout-secs <n>` — wall-clock limit per document (default `300`, `0` disables). Without it one malformed PDF can hang a batch indefinitely
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

Output: single file produces a JSON object; directory produces a JSON array. Capture stderr for summaries/warnings/errors. With `--output` or `--output-dir`, stdout is empty on success.

Each result carries `usage` (tokens billed for that document; `null` means the API reported none, never zero) and `text_context_chars` (characters of local text sent alongside the image; `0` = liteparse read nothing, `null` = it did not run).

```bash
# Resumable batch: per-file outputs, re-run after a crash pays only for what's missing
cd ${SKILL_DIR} && uv run python scripts/parse_vision.py "path/to/folder" \
  --output-dir "results/" --skip-existing
```

## Exit Codes

A batch returns the worst code it saw. Never assume `0` from partial output.

| Code | Handle |
| ---- | ------ |
| `0` | Relay summary from stderr. If `--output` used, tell user file path. Only read full JSON if user asks |
| `1` | Tell user: "GEMINI_DOC_EXTRACTOR_KEY not set. Get key at `https://aistudio.google.com/apikey` and run: `export GEMINI_DOC_EXTRACTOR_KEY='your-key-here'`" |
| `2` | Show stderr error. Confirm file exists + supported type (`.pdf`, `.png`, `.jpg`, `.jpeg`, `.webp`) |
| `3` | Show stderr error. Suggest retry — transient errors resolve on their own |
| `4` | Model response failed schema validation. Re-run with `--debug` to dump the raw response, then report it — retrying unchanged usually reproduces it |
| `5` | Timed out on one document. Re-run that file with a higher `--timeout-secs`, or `--pages` to cut it down |
| `6` | Quota exhausted — a wall, not a hiccup. The batch stopped early and remaining files were skipped. Tell user to check billing/quota; re-run later with `--output-dir --skip-existing` to resume |
| `7` | Local failure (not the API). Show stderr error |
