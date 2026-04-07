# doc-extractor

A skill that extracts structured JSON from supply chain documents (PDFs, images) using Google's Gemini/Gemma models. Agnostic to the invoking agent (Claude Code, Gemini, OpenCode, etc.).

## Project Structure

```
doc-extractor/                    # This directory IS the publishable skill
├── SKILL.md                      # Skill entry point — agent-agnostic instructions
├── CLAUDE.md                     # You are here (Claude Code session context)
├── docs/
│   ├── PRD.md                    # Product requirements (source of truth for schemas)
│   ├── research.md               # Technical research and decisions
│   └── roadmap.md                # Epic-based implementation plan (LIVE DOCUMENT)
├── scripts/
│   ├── parse_vision.py           # Main extraction engine
│   ├── prompts.py                # Extraction prompts and system instructions
│   └── schemas/                  # Pydantic v2 models (one file per document type)
│       ├── __init__.py           # Re-exports all public symbols
│       ├── _enums.py             # DocumentType enum
│       ├── _shared.py            # FormulaComponent, SupplementsFact, CompanyInfo
│       ├── _coa.py               # CoaExtraction, CoaHeader, TestResult (+ enums)
│       ├── _invoice.py           # InvoicePayload
│       ├── _quote.py             # QuotePayload
│       ├── _product_spec.py      # ProductSpecSheetPayload
│       ├── _packaging_spec.py    # PackagingSpecSheetPayload
│       ├── _label.py             # LabelPayload
│       ├── _label_proof.py       # LabelProofPayload
│       ├── _payment_proof.py     # PaymentProofPayload
│       └── _envelope.py          # ExtractionResult, ClassificationResult, PAYLOAD_SCHEMA_MAP
├── evals/                        # Evaluation framework (EPIC-006)
├── tests/                        # Unit tests (pytest)
├── test_docs/                    # Real documents for testing (DO NOT commit to public repos)
└── .ai/
    ├── current-plan.md           # Current session's active plan
    ├── memory.md                 # Session context and learnings
    └── errors.md                 # Known issues and error patterns
```

## Key Commands

```bash
# Run extraction (two-pass: classify then extract)
python scripts/parse_vision.py <absolute_file_path>

# Run extraction with known type (skips classification pass)
python scripts/parse_vision.py <absolute_file_path> --type <TYPE>

# Run evals
python evals/snapshot.py approve --all   # seed snapshots
python evals/snapshot.py compare         # regression check
```

## Environment Variables

- `GEMINI_DOC_EXTRACTOR_KEY` — Required. Google AI Studio API key.
- `GEMINI_MODEL` — Optional. Override model (default: `gemini-2.5-flash`).

## Working Conventions

### Always Keep These Files Updated

After every session or significant change:
1. **`.ai/current-plan.md`** — Update with current status, what was done, what's next
2. **`.ai/memory.md`** — Record learnings, decisions, gotchas discovered during the session
3. **`.ai/errors.md`** — Log any errors encountered and their resolutions
4. **`docs/roadmap.md`** — Update Epic statuses when completing work

### Code Style

- Python 3.13+, type hints everywhere
- Pydantic v2 for all data models
- No business logic in this project — extraction only
- stdout is sacred: only JSON goes to stdout, everything else to stderr
- Exit codes: 0=success, 1=missing key, 2=bad file type, 3=API failure

### Schema Changes

- Schemas live in `scripts/schemas/` — one file per document type
- The PRD (`docs/PRD.md`) is the source of truth for field definitions
- If you change a schema, update both the relevant `schemas/_<type>.py` file AND the PRD
- COA uses `CoaExtraction` (structured with `header_data` + `test_results[]`); all other types use flat `*Payload` models

### Testing

- Test documents live in `test_docs/` — these are real supply chain documents
- Never commit test docs to public repositories (contain business data)
- After EPIC-006: use the eval framework to validate changes
- Future: integrate with https://github.com/karpathy/autoresearch for automated eval

### Model Switching

Changing the model is a one-line env var change:
```bash
export GEMINI_MODEL="gemma-4-26b-a4b-it"  # Switch to Gemma 4
```
No code changes required. All models use the same `google-genai` SDK surface.
