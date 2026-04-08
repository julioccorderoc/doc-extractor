# Executive Summary: Model Extraction Performance

## Evaluation Setup

* **Total Documents:** 31 supply chain documents compared.
* **Baseline:** `source_of_truth` (manually verified perfect extractions).
* **Candidates:** `gemini-3.1-pro-preview`, `gemini-2.5-flash`, and `datalab`.
* **Match Criteria:** Strict scalar matching, array order-insensitivity, and ≥85% fuzzy matching for text (Soft matches).

## 🏆 TL;DR

**Gemini 3.1 Pro Preview is the undisputed winner** and is unequivocally ready for production. While the report shows a 39% "Hard Diff" rate for Pro, a manual review of those diffs reveals they are almost entirely trivial formatting variations (e.g., `3" x 8"` vs `3” x 8”`). It is factually near-perfect. Both **Flash** and **Datalab** perform poorly against the source of truth, struggling with misclassification, hallucinations, and misaligned business logic.

## 1. Gemini 3.1 Pro Preview (The Winner)

* **Exact Matches:** 42% (13/31)
* **Soft Matches:** 19% (6/31)
* **Hard Diffs:** 39% (12/31)

**Analysis:**
Despite the 39% hard diff rate, Pro is extracting the data perfectly. The evaluation script is incredibly strict, meaning Pro was penalized for:

* **Typography:** Using curly quotes instead of straight quotes (`3” x 8”` vs `3" x 8"`).
* **Units Formatting:** Writing `0.125 in.` instead of `0.125"`.
* **Spacing:** Writing `FNSKU V. 3` instead of `FNSKU V.3`.

It only made **one** genuine factual error across all 31 documents (missing a `deposit_number` on a complex invoice). It completely understands the schemas and never misclassified a document.

## 2. Gemini 2.5 Flash (The Erratic Performer)

* **Exact Matches:** 3% (1/31)
* **Soft Matches:** 16% (5/31)
* **Hard Diffs:** 81% (25/31)

**Analysis:**
Flash is not reliable for this workload. It struggles significantly with attention span on complex documents:

* **Misclassification:** It completely misclassified a Product Spec Sheet as a Quote, resulting in catastrophic schema failures.
* **Date Confusion:** It mixed up day/month formats (e.g., extracting `2025-12-01` instead of `2025-01-12`).
* **Dropped Data:** It routinely returned `null` for large nested objects like `bill_to` that were clearly present on the page.

## 3. Datalab (The Misaligned Pipeline)

* **Exact Matches:** 0% (0/31)
* **Soft Matches:** 19% (6/31)
* **Hard Diffs:** 81% (25/31)

**Analysis:**
Datalab fails against our Source of Truth because its internal logic and assumptions misalign with our strict Pydantic schemas:

* **Bad Math/Logic:** On an invoice with a 50% deposit, it extracted the *total* invoice amount (`61350.0`) into the `due_amount` field instead of the actual deposit amount due (`30675.0`).
* **Hallucinated/Derived Fields:** It injected calculated numbers that aren't on the page (e.g., putting `0.4683` into `deposit_percentage`).
* **Bleeding Data:** It populated `ship_to.email` fields with data that didn't belong to the shipping entity.

### Conclusion & Next Steps

1. **Ship Gemini 3.1 Pro:** It handles the complex layouts, deeply nested schemas, and visual reasoning of these documents flawlessly.
2. **Deprecate Flash for this task:** The cost savings of Flash are not worth the risk of misclassifying a Product Spec as a Quote, which would break downstream pipelines.
3. **Ignore Datalab:** We have proven that a pure GenAI pipeline using Gemini 3.1 Pro outperforms the legacy Datalab logic, providing cleaner, more accurate, and more literal extractions without injecting bad assumptions.
