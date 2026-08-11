from __future__ import annotations

import datetime

from schemas import DocumentType

# ---------------------------------------------------------------------------
# Pass 1: classify only
# ---------------------------------------------------------------------------


def build_classification_prompt() -> str:
    """Lightweight prompt for pass 1 — returns only document_type + confidence."""
    return """\
Classify this supply chain document. Choose exactly one document_type:
  COA, INVOICE, QUOTE, PRODUCT_SPEC_SHEET, PACKAGING_SPEC_SHEET,
  LABEL, LABEL_PROOF, LABEL_ORDER_ACK, PAYMENT_PROOF, PACKING_LIST,
  PACKOUT_SHEET, UNKNOWN

Definitions:
- COA: Certificate of Analysis (test results, lot numbers, pass/fail specifications)
- INVOICE: Invoice or Sales Order (line items, vendor, grand total)
- QUOTE: Quote or RFQ (quoted prices and quantities, not a confirmed order)
- PRODUCT_SPEC_SHEET: Formula/specification sheet (ingredients, formula, capsule type — primary focus is the formula)
- PACKAGING_SPEC_SHEET: Packaging specification (bottle, label roll, carton specs — primary focus is packaging)
- LABEL: Finished product label or label artwork (supplement facts panel, allergens, ingredients)
- LABEL_PROOF: Print proof from a printer for client review (has technical print specs: substrate, ink colors, corner radius, wind position)
- LABEL_ORDER_ACK: Label vendor order acknowledgement confirming quantities, pricing, and technical print specifications.
- PAYMENT_PROOF: Bank payment confirmation or screenshot (payer, payee, amount, confirmation number)
- PACKING_LIST: Generic shipment manifest enclosed with freight — what shipped, how many, ship-from/ship-to, carrier or tracking reference. Commercial grain: line items and quantities, no case-by-case or pallet-by-pallet breakdown.
- PACKOUT_SHEET: A manufacturer's finished-goods pack-out record issued after a production run. Physical grain: individual case lines and pallet lines, each carrying a lot code, units per case, and dimensions or weights. Titles like 'Packout', 'Pack Out', 'Rework / New Case Dims', or a pickup block with pallet dimensions are strong signals. If the document breaks the shipment down into cases and pallets with lot codes, it is PACKOUT_SHEET, not PACKING_LIST.
- UNKNOWN: Cannot classify or unreadable

Set confidence: 1.0 = certain, 0.0 = total guess.
"""


# ---------------------------------------------------------------------------
# Pass 2: focused extraction for a specific document type
# ---------------------------------------------------------------------------


_TYPE_SPECIFIC_GUIDANCE: dict[DocumentType, str] = {
    DocumentType.LABEL_ORDER_ACK: """
LABEL_ORDER_ACK NOTES:
- customer_id: extract the buyer's account number in the vendor's system when printed on the acknowledgement. It is typically labeled 'Customer #', 'Account #', 'Ship-To ID', or similar.
""",
    DocumentType.PRODUCT_SPEC_SHEET: """
PRODUCT_SPEC_SHEET NOTES:
- packaging_components: some manufacturers include packaging specifications (bottle, closure, filler, shipper, pallet, etc.) alongside the product formula on the same document. When present, populate packaging_components with the structured breakdown. Leave null when the document specifies only the product formula.
""",
    DocumentType.PACKOUT_SHEET: """
PACKOUT_SHEET NOTES:

The consumer of this extraction derives missing values itself and flags each
derivation for a human to check. A value you compute arrives indistinguishable
from one the manufacturer actually printed, so it silently deletes that flag.
Leaving a gap open is always the better answer.

- units_per_case: state it ONLY if the document prints a per-case quantity. If the document gives a line total and a case count, do NOT divide one by the other — leave units_per_case null.
- case_type: FULL or PARTIAL only when the document uses those words (or 'standard' / 'remainder' / 'odd'). A case that is neither is a real answer: leave it UNKNOWN. Do not judge fullness from the quantities.
- weight_basis: GROSS, TARE, or NET only when the document labels the weight that way. A bare 'WEIGHT' column stays UNKNOWN — the same word covers both an empty pallet and a loaded one, and the magnitude is not proof.
- exp_date: many documents print the expiration on the first row of a lot group only. Leave it null on the rows that do not print it; do not carry it down.
- pallet grouping: '9 Pallets x 16 Boxes' is ONE pallet row with pallet_count=9. Never expand a group into one row per pallet.
- stated_totals: extract every total the document asserts about itself, even when it looks redundant with the line rows. Those totals are how the consumer checks the extraction.
- po_ref: copy any PO string verbatim. It is frequently the vendor's own numbering rather than the buyer's, so it is evidence, not an identifier to act on.
""",
    DocumentType.COA: """
COA NOTES:
- specification_target: many certificates print results with no acceptance limit (information-only rows). Leave it null there rather than restating the result as its own spec.
- lab_conclusion: report the certificate's own verdict. If the certificate states no spec for a row, that row is INFORMATION_ONLY — do not decide PASS or FAIL yourself by comparing numbers.
- assessed_conclusion: this is where YOUR judgement goes, and it stays separate from lab_conclusion. Leave it null unless the row is decidable on its own terms. It is NOT decidable when no limit is printed, when the spec is a percentage and no label claim appears, or when spec_basis and result_basis differ. A wrong assessment is worse than none: the consumer treats a disagreement between the two fields as a finding to investigate, and a fabricated verdict destroys that signal.
- date_report: the date the certificate was issued or reported, which is usually distinct from the manufacture and expiration dates. Leave null if only manufacture/expiration dates appear.
- lot_number holds the FINISHED PRODUCT lot only — the code that reaches the bottle. Certificates commonly print an in-process or bulk lot beside it, and they are different numbers. Put every non-finished lot in other_lots_noted with the label the document gives it. If nothing is labelled as the finished lot, leave lot_number null rather than promoting whichever lot appears first.
- report_number is the lab's own document id (report, certificate, or work-order number), not a lot. Some certificates are named by report number alone, so the two are easy to confuse — a number that identifies the paperwork rather than the batch belongs here.
- BASIS: record spec_basis and result_basis independently, each read from its OWN unit. They disagree more often than you would expect — a heavy metal is routinely reported '0.064 ug/cap' against a limit of '<5 ug/day'. Do not reconcile them, do not convert, do not copy one into the other. A unit with no denominator is UNKNOWN, which is a real answer rather than a fallback.
- SPEC STRUCTURE: fill specification_uom, spec_bound_type, spec_low and spec_high from what is printed. 'NMT 3 mcg/Unit' is MAX with spec_high 3 and uom 'mcg/Unit'. '893 - 987 mg' is RANGE 893 to 987. '835.00 mg ± 10%' is RANGE 751.5 to 918.5. 'Absent/10g' and 'Conforms' are QUALITATIVE with no numbers. A row with no printed limit is NONE.
- LABEL CLAIM: when the specification is a percentage, the certificate prints the claim it is a percentage of in a nearby column. Capture it in label_claim_text / label_claim_numeric / label_claim_uom — without it, '100-150%' cannot be evaluated by anyone downstream.
- FOOTNOTES: capture every marked note in the document-level footnotes array, verbatim and unabridged, and list the markers appearing on each row in that row's footnote_markers. A footnote can change what a limit means — one may state that a criterion written '<100,000' is read as a maximum of 200,000, another may explain that a result below its printed floor is accepted for measurement uncertainty. Record the note; never fold its reasoning into a conclusion yourself.
""",
}


def build_extraction_prompt_for_type(
    doc_type: DocumentType, has_text_context: bool = False
) -> str:
    """Focused extraction prompt for a single document type. No classification step."""
    today = datetime.date.today().isoformat()

    conflict_resolution = ""
    if has_text_context:
        conflict_resolution = """
CONFLICT RESOLUTION:
- Base structure and context on the visual document.
- Base exact spellings, numerical values, and lot numbers on the provided text extraction.
- If the provided text is garbled, irrelevant, or missing data, trust the image.
"""

    type_specific = _TYPE_SPECIFIC_GUIDANCE.get(doc_type, "")

    return f"""\
You are a document data extractor for supply chain documents.
Today's date is {today}.

This document has been classified as {doc_type.value}. Extract data strictly according to the provided JSON schema.
{conflict_resolution}
NORMALIZATION RULES:
- Typography: Replace all smart/curly quotes (” “ ’ ‘) with standard straight quotes (" ').
- Units Formatting: Standardize dimensional units to use standard shorthand (e.g., convert `0.125 in.` or `0.125 inch` to `0.125"`).
- Spacing: Remove arbitrary extra spaces in version numbers, identifiers, and lot numbers (e.g., `V. 3` -> `V.3`).
- Dates: Always ensure dates are formatted strictly as YYYY-MM-DD.

GENERAL RULES:
- Extract exactly what the document says. Do not infer or fabricate data.
- If a field cannot be found, set it to null (or empty list for arrays).
- Pay close attention to the descriptions and data types in the JSON schema.
{type_specific}"""
