# doc-extractor

![Python](https://img.shields.io/badge/python-3.13+-blue) ![License](https://img.shields.io/github/license/julioccorderoc/doc-extractor) ![Stars](https://img.shields.io/github/stars/julioccorderoc/doc-extractor?style=social)

An agent-agnostic skill and CLI tool that extracts structured JSON from supply chain documents (PDFs, images) using Google's Gemini models. AI agents handle the orchestration; a deterministic script handles the extraction enforcing strict Pydantic v2 schemas.

<!-- DEMO GIF PLACEHOLDER -->
<!-- ![doc-extractor demo](assets/demo.gif) -->

```bash
# Install the skill — one command
npx skills add julioccorderoc/doc-extractor
```

Then just ask your agent (e.g., Claude Code):

> "Extract the data from `invoice_123.pdf` and tell me the grand total and who it's from."

The agent verifies the file, runs the extraction, and instantly has access to the fully parsed JSON payload.

---

## What it looks like

<!-- SCREENSHOT PLACEHOLDER — input document vs structured JSON output -->
<!-- ![Document vs JSON](assets/screenshot_extraction.png) -->

---

## Supported Document Types

| Document Type | Description |
| --- | --- |
| `COA` | Certificate of Analysis. Extracts test results, lots, dates, and specifications. |
| `INVOICE` | Invoices and Sales Orders. Extracts vendor, po/invoice numbers, and detailed line items. |
| `QUOTE` | Quotes and RFQs. Extracts quoting details and line items. |
| `PRODUCT_SPEC_SHEET` | Product specifications or formulas. Extracts ingredients, counts, units, and servings. |
| `PACKAGING_SPEC_SHEET` | Packaging specifications. Normalizes components (bottles, closures, desiccants) and label rolls. |
| `LABEL` | Finished product label artwork. Extracts fact panels, ingredients, allergens, and barcodes. |
| `LABEL_PROOF` | Printer proof documents. Extracts technical print specs (substrate, inks, winds) + label content. |
| `PAYMENT_PROOF` | Bank transfers or payment screenshots. Extracts payer, payee, amounts, and dates. |

---

## How It Works

1. **Agent identifies intent** — Your AI agent sees you want to "read" or "extract" a document.
2. **Agent invokes the CLI** — Runs `uv run python scripts/parse_vision.py <file_path>`. If the agent already knows the document type, it can pass `--type TYPE` to skip pass 1.
3. **Pass 1 — Classify** — A lightweight Gemini call returns only `document_type` + `confidence`. Skipped when `--type` is provided.
4. **Pass 2 — Extract** — A second Gemini call uses the exact Pydantic schema for the identified type (no union ambiguity). Each call is focused and precise.
5. **Agent reads output** — Pure JSON is sent to `stdout`. The agent ingests it and answers your question.

---

## AI Agent Skill

Install the skill so agents (like Claude Code) can orchestrate the workflow natively:

```bash
npx skills add julioccorderoc/doc-extractor -g -y
```

**To update after changes:**

```bash
npx skills update -g
```

> See [SKILL.md](SKILL.md) for the full skill definition: trigger conditions, required environment variables, and exit codes.

## Manual Setup

The CLI needs to be on your machine, and you need a Google AI Studio API key.

```bash
git clone https://github.com/julioccorderoc/doc-extractor.git
cd doc-extractor
uv sync
```

**Export your Gemini API Key:**

```bash
export GEMINI_DOC_EXTRACTOR_KEY="your-google-ai-studio-key"
```

---

## Stack

| Library | Role |
| --- | --- |
| [Google GenAI SDK](https://github.com/googleapis/python-genai) | Official Google SDK for interacting with the Gemini API (supports Native Vision). |
| [Pydantic v2](https://docs.pydantic.dev) | Generates `response_schema` for Gemini and ensures returned payloads are strictly typed. |
| [uv](https://github.com/astral-sh/uv) | Dependency management and script runner. Reproducible environments with a lockfile. |

---

## CLI Reference

For agents or direct use:

```text
uv run python scripts/parse_vision.py <path_or_url> [options]
```

**Options:**

- `--url <URL>`: Download a remote document to a temporary file before extraction.
- `--type TYPE`: Skip the classification pass and go straight to extraction. Useful when the caller already knows the document type. Valid values: `COA`, `INVOICE`, `QUOTE`, `PRODUCT_SPEC_SHEET`, `PACKAGING_SPEC_SHEET`, `LABEL`, `LABEL_PROOF`, `LABEL_ORDER_ACK`, `PAYMENT_PROOF`, `UNKNOWN`.
- `--use-liteparse`: Triggers a hybrid extraction pipeline that locally extracts deterministic OCR text from the document and appends it to the Gemini prompt context. This drastically reduces numeric hallucinations on dense tabular data (like COAs and Invoices).
- `--output <file.json>`: Write the extracted JSON directly to a file instead of stdout. Recommended for extremely large documents to avoid terminal output limits.
- `--pages "<spec>"`: Slice a PDF to specific pages (e.g. `"1-3"`, `"1,3,5"`) before extraction to save tokens and improve focus.
- `--debug`: Dump the raw LLM string to stderr if JSON schema validation fails.

**Exit codes:**

| Outcome | Exit code | stdout | stderr |
| --- | --- | --- | --- |
| Success | `0` | Strictly typed JSON payload | Progress logs |
| Missing API Key | `1` | (Empty) | Error message |
| Unsupported file | `2` | (Empty) | Error message |
| API Failure | `3` | (Empty) | Exception stack trace |

No interactive prompts. Output to `stdout` is exclusively JSON. Everything else goes to `stderr`.

---

## Running Locally

**Prerequisites:**

```bash
uv sync
export GEMINI_DOC_EXTRACTOR_KEY="your-api-key"
```

**Extract a document:**

```bash
uv run python scripts/parse_vision.py test_docs/sample_invoice.pdf
```

**Run the eval suite** (checks parsing accuracy against snapshots):

```bash
uv run python evals/snapshot.py compare
```

**Run unit tests** (offline schema validation):

```bash
uv run pytest
```

---

## Model Choice

The default model is **`gemini-3.1-pro-preview`**. This was rigorously validated against `gemini-2.5-flash` and legacy `datalab` extractions across 31 complex supply chain documents (COAs, invoices, packaging specs, label proofs, payment records).

Key findings:

- **Gemini 3.1 Pro Preview is the undisputed winner.** It handles complex layouts, deeply nested schemas, and visual reasoning flawlessly with a near-perfect extraction rate, only occasionally varying in trivial formatting (e.g., curly vs straight quotes).
- **Gemini 2.5 Flash** proved too erratic for this workload, struggling with attention span on complex documents, frequently misclassifying document types, and dropping large nested objects.
- **Pure GenAI vs Legacy Pipelines:** The pure GenAI approach utilizing Gemini 3.1 Pro vastly outperformed the legacy `datalab` extraction pipeline, providing cleaner, more accurate, and more literal extractions without injecting hallucinated data or misaligned business logic assumptions.

To switch models for experimentation:

```bash
export GEMINI_MODEL="gemini-2.5-flash"
```

---

## Extending

To add a new document type to the extractor, follow the strict architectural guidelines outlined in [docs/adding-new-document-type.md](docs/adding-new-document-type.md). The process involves creating a modular schema, wiring it into the two-pass extraction prompt, and validating it via the evaluation framework.

---

## Why This Skill Is Safe to Install

| Property | Detail |
| --- | --- |
| **Strict JSON Output** | The script uses Pydantic JSON schemas forced onto the LLM. It will never output unstructured text. |
| **No File Modifications** | The script is strictly read-only on your local filesystem. |
| **Encapsulated Scope** | Does one thing: takes a file, returns JSON. It contains no business logic. |

*Note: This script uploads the document to Google's temporary storage to process it via Gemini API. Do not use this tool on highly classified documents if you are not authorized to process them through Google.*

---

## Project Structure

```text
doc-extractor/
├── SKILL.md                 ← Skill entry point — agent-agnostic instructions
├── scripts/
│   ├── parse_vision.py      ← Main extraction engine
│   ├── prompts.py           ← Extraction prompts and field instructions
│   ├── cleanup_files.py     ← Utility to prune temporary Google AI files
│   └── schemas/             ← Modular Pydantic v2 schemas per document type
├── evals/                   ← Snapshot-based regression testing suite
├── tests/                   ← Unit tests (pytest)
└── test_docs/               ← Real documents for testing (Ignored in public repo)
```
