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
uv run python scripts/parse_vision.py <absolute_file_path> [--type TYPE] [--use-liteparse]
```

`--use-liteparse` triggers a hybrid extraction pipeline that locally extracts deterministic OCR text from the document and appends it to the Gemini prompt context. This drastically reduces numeric hallucinations on dense tabular data (like COAs and Invoices).

`--type TYPE` skips the classification pass and goes straight to extraction. Useful when the caller already knows the document type. Valid values: `COA`, `INVOICE`, `QUOTE`, `PRODUCT_SPEC_SHEET`, `PACKAGING_SPEC_SHEET`, `LABEL`, `LABEL_PROOF`, `PAYMENT_PROOF`, `UNKNOWN`.

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

The default model is **`gemini-2.5-flash`**. This was validated against `gemini-3.1-pro-preview` across 25 real supply chain documents (COAs, invoices, packaging specs, label proofs, payment records).

Key findings:

- **2.5 Flash wins** on COA test result completeness, deposit field recognition, packaging component extras, and spec sheet structured fields.
- **3.1 Pro wins** on date disambiguation (doc date vs. revision date) and extracting complete marketing text blocks.
- Overall, 2.5 Flash is more reliable and consistent across all document types, at significantly lower cost and latency.

To switch models:

```bash
export GEMINI_MODEL="gemini-3.1-pro-preview"
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
