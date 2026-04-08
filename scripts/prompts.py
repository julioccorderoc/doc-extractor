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
  LABEL, LABEL_PROOF, LABEL_ORDER_ACK, PAYMENT_PROOF, UNKNOWN

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
- UNKNOWN: Cannot classify or unreadable

Set confidence: 1.0 = certain, 0.0 = total guess.
"""


# ---------------------------------------------------------------------------
# Pass 2: focused extraction for a specific document type
# ---------------------------------------------------------------------------


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
"""
