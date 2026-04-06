# doc-extractor

A Claude Code skill that extracts structured JSON from supply chain documents (PDFs, images) using Google's Gemini/Gemma models.

## Project Structure

```
doc-extractor/
├── CLAUDE.md                     # You are here
├── docs/
│   ├── PRD.md                    # Product requirements (source of truth for schemas)
│   ├── research.md               # Technical research and decisions
│   └── roadmap.md                # Epic-based implementation plan (LIVE DOCUMENT)
├── scripts/
│   ├── parse_vision.py           # Main extraction engine
│   └── schemas.py                # Pydantic v2 models for all document types
├── evals/                        # Evaluation framework (EPIC-005)
├── test_docs/                    # Real documents for testing (DO NOT commit to public repos)
├── .ai/
│   ├── current-plan.md           # Current session's active plan
│   ├── memory.md                 # Session context and learnings
│   └── errors.md                 # Known issues and error patterns
└── .claude/skills/doc-extractor/ # Skill packaging (EPIC-004)
    ├── SKILL.md
    └── scripts/                  # Symlinked or copied from root scripts/
```

## Key Commands

```bash
# Run extraction on a document
python scripts/parse_vision.py <absolute_file_path>

# Run evals (after EPIC-005)
python evals/run_evals.py
python evals/compare.py
```

## Environment Variables

- `GEMINI_DOC_EXTRACTOR_KEY` — Required. Google AI Studio API key.
- `GEMINI_MODEL` — Optional. Override model (default: `gemini-3-flash-preview`).

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

- Schemas are defined in `scripts/schemas.py` using Pydantic v2
- The PRD (`docs/PRD.md`) is the source of truth for field definitions
- If you change a schema, update both `schemas.py` AND the PRD

### Testing

- Test documents live in `test_docs/` — these are real supply chain documents
- Never commit test docs to public repositories (contain business data)
- After EPIC-005: use the eval framework to validate changes
- Future: integrate with https://github.com/karpathy/autoresearch for automated eval

### Model Switching

Changing the model is a one-line env var change:
```bash
export GEMINI_MODEL="gemma-4-26b-a4b-it"  # Switch to Gemma 4
```
No code changes required. All models use the same `google-genai` SDK surface.
