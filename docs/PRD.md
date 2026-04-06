# PRD: `doc-extractor` Skill

## 1. Executive Summary

The `doc-extractor` skill acts as the "visual cortex" for an autonomous supply chain agent. Its sole responsibility is to convert unstructured real-world files (PDFs, Images of labels, COAs, Invoices) into predictable, strictly typed JSON.

Following the UNIX philosophy of "do one thing well," this skill performs zero business logic or validation. It simply identifies the document type and reliably extracts the text and tabular data into a structured payload, passing the baton back to the agent for downstream processing.

## 2. Core Objectives

- **Classification:** Accurately identify the type of supply chain document (COA, Invoice, Quote, Spec Sheet, Product Label).
- **Extraction:** Map unstructured text and complex tables into rigid JSON schemas.
- **Reliability:** Eliminate AI formatting hallucinations (no markdown wrappers, no conversational text).
- **Modularity:** Output a standardized payload that can be seamlessly consumed by downstream validation skills (e.g., `doc-validator`).

## 3. Architecture & Implementation

### 3.1 Technology Stack

- **SDK:** `google-genai` (the unified Google Gen AI Python SDK)
- **Schema Definition:** Pydantic v2 models with `.model_json_schema()` for structured output enforcement
- **Starting Model:** `gemini-3-flash-preview` (frontier-class multimodal, structured output, cost-efficient)
- **Target Model:** `gemma-4-26b-a4b-it` (free, structured JSON, vision — available on AI Studio)
- **Long-term Model:** `gemma-4-e4b` (smallest/free variant, when API-available)

### 3.2 Component Breakdown

The skill resides at the repo root (the repo IS the publishable skill, agnostic to agent runtime) and consists of:

1. **`SKILL.md`** (Agent Instructions):
    - Defines the trigger logic: When the user or agent needs to "read," "extract," "digitize," or "parse" a document.
    - Handles prerequisite checks (verifying `$GEMINI_DOC_EXTRACTOR_KEY` exists).
    - Instructs the agent to execute the Python script and capture the `stdout` JSON.
2. **`scripts/parse_vision.py`** (The Engine):
    - A Python script utilizing the `google-genai` SDK.
    - Authenticates via `GEMINI_DOC_EXTRACTOR_KEY` environment variable.
    - Handles file upload to Google's temporary storage via `client.files.upload()`.
    - Executes inference with structured output enforcement via `response_mime_type` + `response_json_schema`.
3. **`scripts/schemas.py`** (The Contract):
    - Pydantic v2 models defining all document type schemas.
    - Used both for JSON Schema generation (sent to the model) and response validation.

### 3.3 The Technical Workflow

1. **Input:** Agent calls `python parse_vision.py <absolute_file_path>`.
2. **File Handling:**
    - Validate file extension (must be `.pdf`, `.png`, `.jpg`, `.jpeg`, `.webp`).
    - Upload via `client.files.upload(file=path)`.
    - Poll: Check `file.state` until it transitions from `PROCESSING` to `ACTIVE`.
3. **Inference:**
    - Model: `gemini-3-flash-preview` (starting), configurable via env var `GEMINI_MODEL`.
    - Config: `response_mime_type="application/json"` + `response_json_schema=Schema.model_json_schema()`.
    - Prompt: Instruct the model to identify the document type and extract according to the schema.
4. **Output:** Script prints the raw JSON to `stdout` and exits cleanly (`sys.exit(0)`).
5. **Cleanup:** Script deletes the file from Google's temporary storage via `client.files.delete()`.

## 4. Output Data Structure (The JSON Contract)

The script must *always* return an object matching this top-level schema. The structure of the `payload` object changes based on the `document_type`.

```json
{
  "document_type": "string (ENUM: COA | INVOICE | QUOTE | SPEC_SHEET | LABEL | UNKNOWN)",
  "confidence": "number (0.0 to 1.0)",
  "extracted_date": "ISO 8601 Timestamp",
  "payload": {
    // Dynamic schema based on document_type
  },
  "raw_text_fallback": "string (used only if table extraction fails)"
}
```

### 4.1 Required Sub-Schemas (The payload object)

Defined as Pydantic v2 models in `scripts/schemas.py`. The models generate JSON Schema via `.model_json_schema()` which is passed to the API's `response_json_schema` parameter to enforce strict adherence.

- **COA** (Certificate of Analysis):
  - date
  - manufacturer_name
  - product_name
  - lot_number
  - expiration_date
  - test_results (array of objects: [test_name, method, specification, result, pass_fail_status])
- **INVOICE:**
  - date
  - vendor_name
  - invoice_number
  - po_number
  - line_items (array of objects: [description, quantity, unit_price, total])
  - grand_total
- **LABEL:**
  - brand
  - product_name
  - barcode
  - version
  - count (capsules, gummies, pellets, etc...)
  - servings
  - supplements_fact_panel (array of objects: [ingredient, amount_per_serving, %DV])
  - other_ingredients
  - allergens
  - company (name, address, email, phone, all)
  - suggested_use
  - marketing_text (like description)
- **PRODUCT_SPEC_SHEET:**
  - date
  - manufacturer_name
  - product_name
  - product_code
  - product_description
  - product_formula (array of objects)
  - count (capsules, gummies, pellets, etc...)
  - servings
- **PACKAGING_SPEC_SHEET:**
  - date
  - manufacturer_name
  - product_name
  - product_code
  - product_description
  - product_formula (array of objects)
  - packaging_components (array of objects)
  - label_specs (array of objects)
  - closure_specs (array of objects)
  - bottle_specs (array of objects)
  - carton_specs (array of objects)
  - pallet_specs (array of objects)

All the dates must be in the `YYYY-MM-DD` format.

## 5. Error Handling & Edge Cases

- **Missing API Key:** Print actionable error `export GEMINI_DOC_EXTRACTOR_KEY='...'` and `sys.exit(1)`. Agent will relay this to user.
- **Unsupported File Type:** Script detects `.docx`/`.xlsx` → `sys.exit(2)`. Agent instructs user: "The doc-extractor only supports PDFs and Images. Please convert the file."
- **API Timeout/Rate Limit:** Implement exponential backoff in the python script (retries = 3). If it fails, `sys.exit(3)`. Agent logs: "Google API is currently rate-limited. Retrying later."
- **Unreadable Document:** If the model cannot identify the document, it must return `"document_type": "UNKNOWN"` and populate `"raw_text_fallback"`. The agent will flag this for human review.

## 6. Success Metrics

- **Zero Format Failures:** The skill never returns conversational AI filler (e.g., "Here is the JSON you requested...").
- **Table Accuracy:** Complex, misaligned COA tables are correctly mapped to their respective columns >95% of the time.
- **Statelessness:** The skill leaves no lingering files in the local directory or Google's cloud storage after execution.
