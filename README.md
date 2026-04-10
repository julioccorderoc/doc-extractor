# doc-extractor

![Python](https://img.shields.io/badge/python-3.13+-blue) ![License](https://img.shields.io/github/license/julioccorderoc/doc-extractor) ![Stars](https://img.shields.io/github/stars/julioccorderoc/doc-extractor?style=social)

Agent-agnostic skill + CLI tool. Extracts structured JSON from supply chain documents (PDFs, images) using Google Gemini models. AI agents handle orchestration; deterministic script handles extraction enforcing strict Pydantic v2 schemas.

```bash
# Install skill — one command
npx skills add julioccorderoc/doc-extractor
```

Then ask your agent (e.g., Claude Code):

> "Extract the data from `invoice_123.pdf` and tell me the grand total and who it's from."

Agent verifies file, runs extraction, instantly has fully parsed JSON payload.

---

## Supported Document Types

| Document Type | Description |
| --- | --- |
| `COA` | Certificate of Analysis. Test results, lots, dates, specs. |
| `INVOICE` | Invoices and Sales Orders. Vendor, PO/invoice numbers, line items. |
| `QUOTE` | Quotes and RFQs. Quoting details and line items. |
| `PRODUCT_SPEC_SHEET` | Product specs/formulas. Ingredients, counts, units, servings. |
| `PACKAGING_SPEC_SHEET` | Packaging specs. Components (bottles, closures, desiccants), label rolls. |
| `LABEL` | Finished label artwork. Fact panels, ingredients, allergens, barcodes. |
| `LABEL_PROOF` | Printer proof docs. Technical print specs (substrate, inks, winds) + label content. |
| `PAYMENT_PROOF` | Bank transfers/payment screenshots. Payer, payee, amounts, dates. |

---

## How It Works

1. **Agent identifies intent** — user wants to "read" or "extract" a document.
2. **Agent invokes CLI** — `uv run python scripts/parse_vision.py <file_path>`. Known type → pass `--type TYPE` to skip Pass 1.
3. **Pass 1 — Classify** — Lightweight Gemini call returns `document_type` + `confidence`. Skipped with `--type`.
4. **Pass 2 — Extract** — Second Gemini call uses exact Pydantic schema for identified type (no union ambiguity). Focused and precise.
5. **Agent reads output** — Pure JSON on stdout. Agent ingests and answers question.

---

## AI Agent Skill

Install so agents (like Claude Code) orchestrate natively:

```bash
npx skills add julioccorderoc/doc-extractor -g -y
```

**Update after changes:**

```bash
npx skills update -g
```

> See [SKILL.md](SKILL.md) for full skill definition: triggers, env vars, exit codes.

## Manual Setup

Need CLI on machine + Google AI Studio API key.

```bash
git clone https://github.com/julioccorderoc/doc-extractor.git
cd doc-extractor
uv sync
```

**Export Gemini API Key:**

```bash
export GEMINI_DOC_EXTRACTOR_KEY="your-google-ai-studio-key"
```

---

## Stack

| Library | Role |
| --- | --- |
| [Google GenAI SDK](https://github.com/googleapis/python-genai) | Official Google SDK for Gemini API (Native Vision). |
| [Pydantic v2](https://docs.pydantic.dev) | Generates `response_schema` for Gemini, ensures strict typed payloads. |
| [uv](https://github.com/astral-sh/uv) | Dependency management + script runner. Reproducible environments with lockfile. |

---

## CLI Reference

```text
uv run python scripts/parse_vision.py <path_or_url> [options]
```

**Options:**

- `--url <URL>`: Download remote doc to temp file before extraction.
- `--type TYPE`: Skip classification, extract directly. Valid: `COA`, `INVOICE`, `QUOTE`, `PRODUCT_SPEC_SHEET`, `PACKAGING_SPEC_SHEET`, `LABEL`, `LABEL_PROOF`, `LABEL_ORDER_ACK`, `PAYMENT_PROOF`, `UNKNOWN`.
- `--use-liteparse`: Hybrid pipeline — local OCR text appended to Gemini prompt. Reduces numeric hallucinations on dense tables.
- `--output <file.json>`: Write JSON to file instead of stdout. Recommended for large docs.
- `--pages "<spec>"`: Slice PDF pages (e.g. `"1-3"`, `"1,3,5"`) before extraction.
- `--debug`: Dump raw LLM string to stderr on validation failure.

**Exit codes:**

| Outcome | Exit code | stdout | stderr |
| --- | --- | --- | --- |
| Success | `0` | Strictly typed JSON | Progress logs |
| Missing API Key | `1` | (Empty) | Error message |
| Unsupported file | `2` | (Empty) | Error message |
| API Failure | `3` | (Empty) | Exception trace |

No interactive prompts. stdout = exclusively JSON. Everything else → stderr.

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

**Run eval suite** (accuracy check against snapshots):

```bash
uv run python evals/snapshot.py compare
```

**Run unit tests** (offline schema validation):

```bash
uv run pytest
```

---

## Model Choice

Default: **`gemini-3.1-pro-preview`**. Rigorously validated against `gemini-2.5-flash` and `datalab` across 31 complex supply chain docs (COAs, invoices, packaging specs, label proofs, payment records).

Key findings:

- **Gemini 3.1 Pro Preview wins.** Handles complex layouts, nested schemas, visual reasoning flawlessly. Near-perfect extraction rate — only trivial formatting variations (curly vs straight quotes).
- **Gemini 2.5 Flash** too erratic. Struggles with attention on complex docs, misclassifies types, drops large nested objects.
- **Pure GenAI vs Legacy:** Gemini 3.1 Pro vastly outperforms `datalab` pipeline — cleaner, more accurate, more literal extractions without hallucinated data or misaligned business logic.

Switch models:

```bash
export GEMINI_MODEL="gemini-2.5-flash"
```

---

## Extending

Add new doc type: follow [docs/adding-new-document-type.md](docs/adding-new-document-type.md). Create modular schema, wire into two-pass prompt, validate via eval framework.

---

## Why This Skill Is Safe

| Property | Detail |
| --- | --- |
| **Strict JSON Output** | Pydantic schemas forced onto LLM. Never outputs unstructured text. |
| **No File Modifications** | Strictly read-only on local filesystem. |
| **Encapsulated Scope** | One thing: file in, JSON out. Zero business logic. |

*Note: Uploads document to Google temp storage for Gemini API processing. Do not use on highly classified documents without authorization to process through Google.*

---

## Project Structure

```text
doc-extractor/
├── SKILL.md                 ← Skill entry point — agent-agnostic instructions
├── scripts/
│   ├── parse_vision.py      ← Main extraction engine
│   ├── prompts.py           ← Extraction prompts and field instructions
│   ├── cleanup_files.py     ← Utility to prune temp Google AI files
│   └── schemas/             ← Modular Pydantic v2 schemas per doc type
├── evals/                   ← Snapshot-based regression testing
├── tests/                   ← Unit tests (pytest)
└── test_docs/               ← Real documents for testing (ignored in public repo)
```
