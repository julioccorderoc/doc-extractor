# Adding a New Document Type

This document outlines the step-by-step process for adding support for a new document type to the `doc-extractor` skill. This guide is specifically written to be ingested by AI agents to ensure they follow the architectural conventions of this project without skipping any steps.

## Architecture Context

The `doc-extractor` uses a **two-pass extraction strategy**:
1. **Pass 1 (Classification):** A lightweight prompt with a small schema (`ClassificationResult`) asks the model to identify the document type.
2. **Pass 2 (Extraction):** A focused prompt with the exact Pydantic schema for that specific document type is used to extract the payload.

## Step-by-Step Guide

To add a new document type (e.g., `PACKING_SLIP`), follow these exact steps in order:

### 1. Add the Document Type Enum
Modify `scripts/schemas/_enums.py`:
- Add the new document type to the `DocumentType` enum.
- Example: `PACKING_SLIP = "PACKING_SLIP"`

### 2. Create the Schema Model
Create a new file in `scripts/schemas/` (e.g., `scripts/schemas/_packing_slip.py`):
- Define the `LineItem` model (if applicable) and the main `Payload` model.
- Use `Pydantic v2` with strict `Field(default=None, description="...")` annotations.
- All numbers should be typed as `float` (or `int` if explicitly discrete).
- All dates must specify `YYYY-MM-DD` format in their descriptions.
- Ensure the main payload model is named intuitively (e.g., `PackingSlipPayload`).

### 3. Export the Schema
Modify `scripts/schemas/__init__.py`:
- Import your new models from the new file.
- Add them to the `__all__` list.

### 4. Wire the Envelope and Routing
Modify `scripts/schemas/_envelope.py`:
- Import your new payload model.
- Add it to the `PayloadUnion` type.
- Add a routing entry in the `PAYLOAD_SCHEMA_MAP` dictionary (e.g., `DocumentType.PACKING_SLIP: PackingSlipPayload`).

### 5. Update the Prompts
Modify `scripts/prompts.py`:
- **In `_FIELD_RULES`:** Add an entry for your new document type with explicit, comma-separated field instructions (used in Pass 2).
- **In `build_classification_prompt()`:** 
  - Add your new document type to the list of choices.
  - Add a one-line definition in the `Definitions:` section to help Pass 1 classify it accurately.

### 6. Update the PRD
Modify `docs/PRD.md`:
- Under **Section 4.1 Required Sub-Schemas**, add a bulleted list of the fields your new schema extracts.
- Update the `document_type` ENUM list in the **Section 4 Output Data Structure** JSON snippet to include the new type.

### 7. Add Unit Tests
Modify `tests/test_schemas.py`:
- Add a validation test `test_new_doc_payload_validates()` passing a sample JSON dictionary to verify field extraction and types.
- Add a dispatch test `test_extraction_result_dispatches_new_doc()` to ensure `ExtractionResult.model_validate()` correctly instantiates your specific payload class via the Union.

### 8. Seed the Evaluation Snapshots
- Ensure there is at least one test document in `test_docs/` that matches this new type.
- Update `test_docs/manifest.json` mapping the new file's name to the new `DocumentType` string.
- (To be run by the user or an agent with API keys): Run `uv run python evals/snapshot.py approve --all` to seed the snapshots.

## Checklist for Agents
- [ ] Enum updated (`_enums.py`)
- [ ] Schema created (`_new_doc.py`)
- [ ] Schema exported (`__init__.py`)
- [ ] Envelope updated and mapped (`_envelope.py`)
- [ ] Prompts updated for classification and extraction (`prompts.py`)
- [ ] PRD updated (`docs/PRD.md`)
- [ ] Unit tests added (`tests/test_schemas.py`)
- [ ] Evaluation suite tests pass (`uv run pytest`)
