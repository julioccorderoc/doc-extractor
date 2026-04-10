# PRD: `doc-extractor` Skill

## 1. Executive Summary

`doc-extractor` = "visual cortex" for autonomous supply chain agent. Sole job: convert unstructured files (PDFs, images of labels, COAs, invoices) → predictable, strictly typed JSON.

UNIX philosophy: do one thing well. Zero business logic or validation. Identify doc type, extract text + tabular data into structured payload, pass baton to agent for downstream processing.

## 2. Core Objectives

- **Classification:** Identify supply chain doc type (COA, Invoice, Quote, Spec Sheet, Product Label).
- **Extraction:** Map unstructured text + complex tables → rigid JSON schemas.
- **Reliability:** Kill AI formatting hallucinations (no markdown wrappers, no conversational text).
- **Modularity:** Standardized payload consumed by downstream validation skills (e.g., `doc-validator`).

## 3. Architecture & Implementation

### 3.1 Technology Stack

- **SDK:** `google-genai` (unified Google Gen AI Python SDK)
- **Schema Definition:** Pydantic v2 models with `.model_json_schema()` for structured output enforcement
- **Starting Model:** `gemini-3-flash-preview` (frontier-class multimodal, structured output, cost-efficient)
- **Target Model:** `gemma-4-26b-a4b-it` (free, structured JSON, vision — available on AI Studio)
- **Long-term Model:** `gemma-4-e4b` (smallest/free variant, when API-available)

### 3.2 Component Breakdown

Repo root IS the publishable skill, agnostic to agent runtime:

1. **`SKILL.md`** (Agent Instructions):
    - Trigger logic: when user/agent needs to "read," "extract," "digitize," or "parse" a document.
    - Prerequisite checks (verifying `$GEMINI_DOC_EXTRACTOR_KEY`).
    - Instructs agent to execute Python script and capture stdout JSON.
2. **`scripts/parse_vision.py`** (The Engine):
    - Python script using `google-genai` SDK.
    - Authenticates via `GEMINI_DOC_EXTRACTOR_KEY` env var.
    - File upload to Google temp storage via `client.files.upload()`.
    - Inference with structured output enforcement via `response_mime_type` + `response_json_schema`.
3. **`scripts/schemas.py`** (The Contract):
    - Pydantic v2 models defining all doc type schemas.
    - Used for JSON Schema generation (sent to model) and response validation.

### 3.3 Technical Workflow

1. **Input:** Agent calls `python scripts/parse_vision.py <path> [options]`.
2. **File Handling & Preprocessing:**
    - `--url` provided → download to temp dir.
    - Directory input → batch process all supported files.
    - Validate extension (`.pdf`, `.png`, `.jpg`, `.jpeg`, `.webp`, `.xlsx`, `.docx`, `.csv`, `.md`, `.txt`).
    - Office/CSV → preprocess to Markdown text via MarkItDown.
    - `--pages` provided (PDFs) → slice to target pages.
    - Upload via `client.files.upload(file=path)`.
    - Poll `file.state` until `PROCESSING` → `ACTIVE`.
3. **Inference:**
    - Model: `gemini-3-flash-preview` (starting), configurable via `GEMINI_MODEL` env var.
    - Config: `response_mime_type="application/json"` + `response_json_schema=Schema.model_json_schema()`.
    - Prompt: identify doc type, extract per schema.
4. **Output:** Raw JSON → `stdout`, `sys.exit(0)`.
5. **Cleanup:** Delete file from Google temp storage via `client.files.delete()`.

## 4. Output Data Structure (The JSON Contract)

Always returns object matching this top-level schema. `payload` structure changes based on `document_type`.

```json
{
  "document_type": "string (ENUM: COA | INVOICE | QUOTE | PRODUCT_SPEC_SHEET | PACKAGING_SPEC_SHEET | LABEL | LABEL_PROOF | LABEL_ORDER_ACK | PAYMENT_PROOF | UNKNOWN)",
  "confidence": "number (0.0 to 1.0)",
  "extracted_date": "ISO 8601 Timestamp",
  "payload": {
    // Dynamic schema based on document_type
  },
  "raw_text_fallback": "string (used only if table extraction fails)"
}
```

### 4.1 Required Sub-Schemas (The payload object)

Defined as Pydantic v2 models in `scripts/schemas/`. Models = absolute single source of truth for JSON Schema via `.model_json_schema()`.

Refer to `scripts/schemas/_enums.py` for active `DocumentType` enum values, and `scripts/schemas/_envelope.py` for type → payload model mapping.

All extracted dates: `YYYY-MM-DD` format.

## 5. Error Handling & Edge Cases

- **Missing API Key:** Print `export GEMINI_DOC_EXTRACTOR_KEY='...'` → `sys.exit(1)`. Agent relays to user.
- **Unsupported File Type:** Bad extension (e.g., `.exe`) → `sys.exit(2)`. Agent tells user: "Only supports PDFs, Images, and Office documents."
- **API Timeout/Rate Limit:** Exponential backoff (retries = 3). If fails → `sys.exit(3)`. Agent logs: "Google API rate-limited. Retrying later."
- **Unreadable Document:** Model can't identify → return `"document_type": "UNKNOWN"`, populate `"raw_text_fallback"` + generic tables. Agent flags for human review.

## 6. Success Metrics

- **Zero Format Failures:** Never returns conversational AI filler.
- **Table Accuracy:** Complex misaligned COA tables correctly mapped >95%.
- **Statelessness:** No lingering files in local dir or Google cloud storage after execution.
