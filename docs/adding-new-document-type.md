# Adding a New Document Type

Step-by-step process for adding new doc type support. Written for AI agent ingestion — follows architectural conventions, no skipped steps.

## Architecture Context

Two-pass extraction strategy:
1. **Pass 1 (Classification):** Lightweight prompt with small schema (`ClassificationResult`) → identify doc type.
2. **Pass 2 (Extraction):** Focused prompt with exact Pydantic schema for that type → extract payload.

## Step-by-Step Guide

Adding new type (e.g., `PACKING_SLIP`):

### 1. Add Document Type Enum
`scripts/schemas/_enums.py`:
- Add to `DocumentType` enum
- Example: `PACKING_SLIP = "PACKING_SLIP"`

### 2. Create Schema Model
New file `scripts/schemas/_packing_slip.py`:
- Define `LineItem` model (if applicable) + main `Payload` model
- Pydantic v2 with strict `Field(default=None, description="...")`
- Numbers → `float` (or `int` if explicitly discrete)
- Dates must specify `YYYY-MM-DD` in descriptions
- Name intuitively (e.g., `PackingSlipPayload`)

### 3. Export Schema
`scripts/schemas/__init__.py`:
- Import new models
- Add to `__all__`

### 4. Wire Envelope and Routing
`scripts/schemas/_envelope.py`:
- Import new payload model
- Add to `PayloadUnion` type
- Add to `PAYLOAD_SCHEMA_MAP` dict (e.g., `DocumentType.PACKING_SLIP: PackingSlipPayload`)

### 5. Update Prompts
`scripts/prompts.py`:
- **`_FIELD_RULES`:** Add entry with explicit field instructions (used in Pass 2)
- **`build_classification_prompt()`:** Add new type to choices list + one-line definition in `Definitions:` section

### 6. Update PRD
`docs/PRD.md`:
- **Section 4.1:** Add bulleted field list
- **Section 4:** Update `document_type` ENUM in JSON snippet

### 7. Add Unit Tests
`tests/test_schemas.py`:
- Validation test: `test_new_doc_payload_validates()` — sample JSON dict → verify fields + types
- Dispatch test: `test_extraction_result_dispatches_new_doc()` — `ExtractionResult.model_validate()` instantiates correct payload class via Union

### 8. Seed Evaluation Snapshots
- Add test document to `test_docs/`
- Update `test_docs/manifest.json` with filename → `DocumentType` mapping
- Run: `uv run python evals/snapshot.py approve --all`

## Checklist for Agents
- [ ] Enum updated (`_enums.py`)
- [ ] Schema created (`_new_doc.py`)
- [ ] Schema exported (`__init__.py`)
- [ ] Envelope updated and mapped (`_envelope.py`)
- [ ] Prompts updated for classification and extraction (`prompts.py`)
- [ ] PRD updated (`docs/PRD.md`)
- [ ] Unit tests added (`tests/test_schemas.py`)
- [ ] Evaluation suite tests pass (`uv run pytest`)
