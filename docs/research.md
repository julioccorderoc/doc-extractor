# Research: `doc-extractor` Implementation

## 1. Google GenAI SDK (The Engine)

### Which SDK?

Use `google-genai` (new unified SDK), NOT legacy `google-generativeai`.

```bash
pip install google-genai
```

Client initialization:

```python
from google import genai
client = genai.Client(api_key=os.environ["GEMINI_DOC_EXTRACTOR_KEY"])
```

SDK auto-detects `GEMINI_API_KEY` env var, but PRD specifies `GEMINI_DOC_EXTRACTOR_KEY` — pass explicitly.

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

Limits: 50MB/PDF, 1000 pages max, 2GB general. Auto-delete after 48h. No extra cost for Files API.

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

Same `config` shape, pass dict instead of Pydantic. Less type-safe, harder to maintain.

#### Recommendation

Pydantic. Get validation, type hints, and `.model_json_schema()` for free.

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

Typical extraction (~1-page PDF + schema prompt) costs ~$0.001–$0.003/call. Extremely cheap.

Flash over Pro: task is extraction, not reasoning. Flash handles structured extraction well, 10x cheaper.

### Target Model: Gemma 4

Released April 2, 2026 in 4 variants:

| Variant | Params | Vision | API Available | Structured JSON |
|---|---|---|---|---|
| E2B | 2.3B effective | Yes + Audio | Local only (AI Edge) | Unknown via API |
| E4B | 4.5B effective | Yes + Audio | Local only (AI Edge) | Unknown via API |
| 26B MoE | 3.8B active / 25.2B total | Yes | Yes (AI Studio) | Yes |
| 31B Dense | 30.7B | Yes | Yes (AI Studio) | Yes |

Key finding: E4B (long-term target) NOT available through AI Studio API — local deployment only (Hugging Face, Ollama, AI Edge Gallery). Only 26B and 31B are API-accessible.

Model IDs on API:

- `gemma-4-26b-a4b-it` — MoE, lighter compute
- `gemma-4-31b-it` — Dense, heavier but more capable

Both support `response_mime_type: "application/json"` for structured output.

Gemma 4 listed "Free of charge" on free tier — no per-token cost, rate limits only.

### Migration Path

```text
Phase 1-3: gemini-2.5-flash  →  Phase 4: gemma-4-26b-a4b-it  →  Future: gemma-4-e4b (when API-available)
```

Switching models = one-line change. Same SDK and API surface.

---

## 3. Skill Architecture

### Skill Format

Repo root IS the publishable skill — agent-agnostic (Claude Code, Gemini, OpenCode, etc.):

```text
doc-extractor/
├── SKILL.md              # Required — trigger logic + agent instructions
├── scripts/
│   ├── parse_vision.py   # The extraction engine
│   ├── prompts.py        # Extraction prompts
│   └── schemas.py        # Pydantic schema definitions
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

`disable-model-invocation: true` — autonomous supply chain agent controls when extraction happens. Agent invokes via `/doc-extractor <file_path>`.

`allowed-tools: Bash(python *)` — skill only needs to run Python script.

### Script Invocation Pattern

SKILL.md instructs agent to:

1. Verify `$GEMINI_DOC_EXTRACTOR_KEY` is set
2. Run `python ${SKILL_DIR}/scripts/parse_vision.py $ARGUMENTS`
3. Capture stdout (pure JSON)
4. Interpret exit codes (0=success, 1=missing key, 2=bad file type, 3=API error)

`${SKILL_DIR}` = agent-agnostic equivalent of `${CLAUDE_SKILL_DIR}` — resolved by whichever runtime loads skill.

---

## 4. Implementation Phases

Each phase completable in single session.

### Phase 1: Core Script + Single Schema (COA)

- Set up deps (`google-genai`, `pydantic`)
- Implement `parse_vision.py`: API key validation, file upload + polling, inference with `gemini-2.5-flash`, structured output with single schema (COA), stdout JSON, file cleanup
- Test with real COA from `test_docs/`

### Phase 2: All Document Schemas

- Define Pydantic models for all types: COA, Invoice, Label, Product Spec Sheet, Packaging Spec Sheet
- Two-step prompt: classify doc type → extract with correct schema
- `UNKNOWN` fallback with `raw_text_fallback`
- Test with multiple doc types from `test_docs/`

### Phase 3: SKILL.md + Error Handling

- Write `SKILL.md` with trigger logic + instructions
- Exponential backoff (3 retries)
- Exit codes (0, 1, 2, 3) per PRD
- File extension validation
- End-to-end test via skill invocation

### Phase 4: Gemma 4 Migration + Polish

- Switch model to `gemma-4-26b-a4b-it`
- Compare extraction quality vs Flash
- Tune prompts for Gemma 4 behavior
- Final testing across all doc types

---

## 5. Open Questions for User

1. Skill location: repo root is skill — publish repo directly. No nested packaging dir needed.
2. Two-step vs single-step inference: PRD implies one call that classifies + extracts. Alternative: two calls (classify first, then extract with right schema). Single call cheaper but may be less accurate on edge cases.
3. Schema strictness on Gemma 4: 26B MoE supports structured JSON, but E4B (long-term target) is local-only and may need different approach (e.g., Ollama + instructor library).

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
