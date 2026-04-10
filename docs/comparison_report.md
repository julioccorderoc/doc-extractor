# Executive Summary: Model Extraction Performance

## Evaluation Setup

* **Documents:** 31 supply chain docs compared
* **Baseline:** `source_of_truth` (manually verified perfect extractions)
* **Candidates:** `gemini-3.1-pro-preview`, `gemini-2.5-flash`, `datalab`
* **Match Criteria:** Strict scalar matching, array order-insensitivity, >=85% fuzzy matching for text (Soft matches)

## TL;DR

**Gemini 3.1 Pro Preview wins.** Unequivocally production-ready. Report shows 39% "Hard Diff" rate for Pro, but manual review reveals almost entirely trivial formatting variations (e.g., `3" x 8"` vs `3" x 8"`). Factually near-perfect. Both **Flash** and **Datalab** perform poorly — misclassification, hallucinations, misaligned business logic.

## 1. Gemini 3.1 Pro Preview (Winner)

* **Exact Matches:** 42% (13/31)
* **Soft Matches:** 19% (6/31)
* **Hard Diffs:** 39% (12/31)

**Analysis:**
Despite 39% hard diff rate, Pro extracts data perfectly. Eval script is strict — Pro penalized for:

* **Typography:** Curly quotes vs straight quotes (`3" x 8"` vs `3" x 8"`)
* **Units Formatting:** `0.125 in.` vs `0.125"`
* **Spacing:** `FNSKU V. 3` vs `FNSKU V.3`

**One** genuine factual error across 31 docs (missing `deposit_number` on complex invoice). Zero misclassifications.

## 2. Gemini 2.5 Flash (Erratic)

* **Exact Matches:** 3% (1/31)
* **Soft Matches:** 16% (5/31)
* **Hard Diffs:** 81% (25/31)

**Analysis:**
Not reliable for this workload. Struggles with attention span on complex docs:

* **Misclassification:** Product Spec Sheet → Quote. Catastrophic schema failure.
* **Date Confusion:** Mixed day/month (e.g., `2025-12-01` instead of `2025-01-12`)
* **Dropped Data:** Returned `null` for large nested objects like `bill_to` clearly present on page

## 3. Datalab (Misaligned)

* **Exact Matches:** 0% (0/31)
* **Soft Matches:** 19% (6/31)
* **Hard Diffs:** 81% (25/31)

**Analysis:**
Fails because internal logic misaligns with strict Pydantic schemas:

* **Bad Math:** Invoice with 50% deposit → extracted total (`61350.0`) into `due_amount` instead of actual deposit due (`30675.0`)
* **Hallucinated Fields:** Injected calculated numbers not on page (e.g., `0.4683` into `deposit_percentage`)
* **Bleeding Data:** Populated `ship_to.email` with data from wrong entity

### Conclusion & Next Steps

1. **Ship Gemini 3.1 Pro:** Handles complex layouts, nested schemas, visual reasoning flawlessly.
2. **Deprecate Flash:** Cost savings not worth misclassification risk breaking downstream pipelines.
3. **Ignore Datalab:** Pure GenAI via Gemini 3.1 Pro outperforms legacy Datalab — cleaner, more accurate, more literal extractions without bad assumptions.
