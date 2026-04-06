# Research: `doc-extractor` Implementation

## 1. Google GenAI SDK (The Engine)

### Which SDK?

Use `google-genai` (the new unified SDK), NOT the legacy `google-generativeai`.

```bash
pip install google-genai
```

Client initialization:

```python
from google import genai
client = genai.Client(api_key=os.environ["GEMINI_DOC_EXTRACTOR_KEY"])
```

The SDK auto-detects `GEMINI_API_KEY` env var, but since the PRD specifies `GEMINI_DOC_EXTRACTOR_KEY`, we pass it explicitly.

### File Upload API

```python
# Upload
uploaded = client.files.upload(file="/path/to/doc.pdf")

# Poll for readiness (PDFs need processing time)
import time
while uploaded.state.name == "PROCESSING":
    time.sleep(2)
    uploaded = client.files.get(name=uploaded.name)

# Use in inference
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=["Extract data from this document", uploaded]
)

# Cleanup
client.files.delete(name=uploaded.name)
```

Limits: 50MB per PDF, 1000 pages max, 2GB general file limit. Files auto-delete after 48h. No additional cost for the Files API itself.

### Structured Output (Critical for Reliability)

Two approaches — both enforce `application/json` response:

#### Option A: Pydantic models (recommended)

```python
from pydantic import BaseModel, Field
from typing import List, Optional

class TestResult(BaseModel):
    test_name: str
    method: str
    specification: str
    result: str
    pass_fail_status: str

class COAPayload(BaseModel):
    date: str
    manufacturer_name: str
    product_name: str
    lot_number: str
    expiration_date: str
    test_results: List[TestResult]

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=["Extract...", uploaded_file],
    config={
        "response_mime_type": "application/json",
        "response_json_schema": COAPayload.model_json_schema(),
    },
)
```

#### Option B: Raw JSON Schema dict

Same `config` shape, just pass a dict instead of Pydantic. Less type-safe, harder to maintain.

#### Recommendation

Pydantic. We get validation, type hints, and `.model_json_schema()` for free.

---

## 2. Model Strategy

### Starting Model: `gemini-2.5-flash`

| Property | Value |
|---|---|
| Model ID | `gemini-2.5-flash` |
| Input cost | $0.30 / 1M tokens (text/image) |
| Output cost | $2.50 / 1M tokens |
| Vision | Yes (images + PDFs natively) |
| Structured output | Yes (guaranteed JSON schema adherence) |
| Context window | 1M tokens |
| Free tier | Yes (rate-limited) |

A typical document extraction (1-page PDF + schema prompt) costs roughly ~$0.001–$0.003 per call. Extremely cheap.

Why Flash over Pro: The task is extraction, not reasoning. Flash handles structured data extraction from documents very well and is 10x cheaper than Pro.

### Target Model: Gemma 4

Gemma 4 was released April 2, 2026 in 4 variants:

| Variant | Params | Vision | API Available | Structured JSON |
|---|---|---|---|---|
| E2B | 2.3B effective | Yes + Audio | Local only (AI Edge) | Unknown via API |
| E4B | 4.5B effective | Yes + Audio | Local only (AI Edge) | Unknown via API |
| 26B MoE | 3.8B active / 25.2B total | Yes | Yes (AI Studio) | Yes |
| 31B Dense | 30.7B | Yes | Yes (AI Studio) | Yes |

Key finding: The E4B model (the user's long-term target) is currently NOT available through Google AI Studio API — only via local deployment (Hugging Face, Ollama, AI Edge Gallery). Only the 26B and 31B are API-accessible today.

Model IDs on the API:

- `gemma-4-26b-a4b-it` — MoE, lighter compute
- `gemma-4-31b-it` — Dense, heavier but more capable

Both support `response_mime_type: "application/json"` for structured output through the Gemini API.

Gemma 4 is listed as "Free of charge" on the free tier — no per-token cost, just rate limits.

### Migration Path

```text
Phase 1-3: gemini-2.5-flash  →  Phase 4: gemma-4-26b-a4b-it  →  Future: gemma-4-e4b (when API-available)
```

Switching models is a one-line change since they all use the same SDK and API surface.

---

## 3. Skill Architecture

### Skill Format

The repo root IS the publishable skill — agent-agnostic (Claude Code, Gemini, OpenCode, etc.):

```text
doc-extractor/
├── SKILL.md              # Required — trigger logic + agent instructions
├── scripts/
│   └── parse_vision.py   # The extraction engine
└── scripts/
    └── schemas.py        # Pydantic schema definitions
```

### SKILL.md Design

```yaml
---
name: doc-extractor
description: |
  Extract structured data from supply chain documents (PDFs, images of labels, COAs, invoices, spec sheets). Use when the agent needs to "read," "extract," "digitize," or "parse" a document file. Outputs strict JSON to stdout.
disable-model-invocation: true
allowed-tools:
  - Bash(python *)
---
```

`disable-model-invocation: true` — The autonomous supply chain agent controls when extraction happens. The agent invokes it via `/doc-extractor <file_path>`.

`allowed-tools: Bash(python *)` — The skill only needs to run the Python script.

### Script Invocation Pattern

The SKILL.md instructs the agent to:

1. Verify `$GEMINI_DOC_EXTRACTOR_KEY` is set
2. Run `python ${SKILL_DIR}/scripts/parse_vision.py $ARGUMENTS`
3. Capture stdout (pure JSON)
4. Interpret exit codes (0=success, 1=missing key, 2=bad file type, 3=API error)

`${SKILL_DIR}` is the agent-agnostic equivalent of `${CLAUDE_SKILL_DIR}` — resolved by whichever runtime loads the skill.

---

## 4. Implementation Phases

Each phase is small enough to complete in a single session.

### Phase 1: Core Script + Single Schema (COA)

- Set up project dependencies (`google-genai`, `pydantic`)
- Implement `parse_vision.py` with:
  - API key validation
  - File upload + polling
  - Inference with `gemini-2.5-flash`
  - Structured output using a single schema (COA)
  - stdout JSON output
  - File cleanup
- Test with a real COA from `test_docs/`

### Phase 2: All Document Schemas

- Define Pydantic models for all document types: COA, Invoice, Label, Product Spec Sheet, Packaging Spec Sheet
- Implement the two-step prompt: classify document type → extract with correct schema
- Add the `UNKNOWN` fallback with `raw_text_fallback`
- Test with multiple document types from `test_docs/`

### Phase 3: SKILL.md + Error Handling

- Write the `SKILL.md` with trigger logic and instructions
- Add exponential backoff (3 retries)
- Add exit codes (0, 1, 2, 3) per PRD spec
- Add file extension validation
- End-to-end test via skill invocation

### Phase 4: Gemma 4 Migration + Polish

- Switch model to `gemma-4-26b-a4b-it`
- Compare extraction quality vs Flash
- Tune prompts for Gemma 4's behavior
- Final testing across all document types

---

## 5. Open Questions for User

1. Skill location: The repo root is the skill — publish the repo directly. No nested packaging directory needed.
2. Two-step vs single-step inference: The PRD implies one call that both classifies and extracts. An alternative is two calls (classify first, then extract with the right schema). Single call is cheaper but may be less accurate on edge cases.
3. Schema strictness on Gemma 4: The 26B MoE model supports structured JSON, but the E4B (long-term target) is local-only and may need a different approach (e.g., Ollama + instructor library). Worth noting for future planning.

---

## Sources

- [Structured output — Gemini API](https://ai.google.dev/gemini-api/docs/structured-output)
- [Gemini API Pricing](https://ai.google.dev/gemini-api/docs/pricing)
- [Gemma 4 Model Card](https://ai.google.dev/gemma/docs/core/model_card_4)
- [Gemma 4 Announcement](https://blog.google/innovation-and-ai/technology/developers-tools/gemma-4/)
- [google-genai Python SDK](https://github.com/googleapis/python-genai)
- [Files API — Gemini API](https://ai.google.dev/gemini-api/docs/files)
- [Document Processing — Gemini API](https://ai.google.dev/gemini-api/docs/document-processing)
- [Claude Code Skills Documentation](https://code.claude.com/docs/en/skills)
- [Skill Creator Reference](https://github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md)
