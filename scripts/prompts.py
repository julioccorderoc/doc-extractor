import datetime

from schemas import DocumentType

# ---------------------------------------------------------------------------
# Per-type field rules (used in the focused extraction prompt)
# ---------------------------------------------------------------------------

_FIELD_RULES: dict[str, str] = {
    "PAYMENT_PROOF": (
        "date (YYYY-MM-DD), payer (sender name/account), payee (recipient name/account), "
        "amount (number — no currency symbol), confirmation_number, "
        "payment_method (e.g. 'Zelle', 'ACH', 'Wire Transfer')"
    ),
    "COA": (
        "header_data: testing_lab_name (required), manufacturer_name, customer_name, product_name (required), "
        "lot_number (required — prefer Finished Product/Manufacturing Lot if multiple exist), po_number, "
        "date_manufactured (exact text e.g. '02/2026'), date_expiration (exact text), "
        "serving_size, other_ingredients_statement. "
        "test_results[] — extract EVERY row without skipping: "
        "test_category (PHYSICAL/ACTIVE_INGREDIENT/MICROBIOLOGY/HEAVY_METAL/IDENTITY), "
        "specific_analyte (exact name), test_method (or null), specification_target (exact spec text), "
        "raw_result_text (exact result string), result_operator (=/</>/<=/>=/ND/ABSENT/CONFORMS), "
        "result_numeric (isolated number or null for Absent/ND/Conforms), result_uom (unit or null), "
        "lab_conclusion (PASS/FAIL/OUT_OF_SPECIFICATION/INFORMATION_ONLY)"
    ),
    "INVOICE": (
        "date (YYYY-MM-DD), vendor_name, invoice_number, po_number, "
        "line_items[] (description, quantity [number], quantity_unit [e.g. 'bottle','label','kg'], "
        "unit_price, total), grand_total. "
        "If this is a deposit/partial payment invoice: deposit_number (integer, e.g. 1 for 'Deposit 1'), "
        "deposit_percentage (fraction 0.0–1.0), due_amount (remaining balance after this payment). "
        "Sales orders should also be classified as INVOICE."
    ),
    "QUOTE": (
        "date (YYYY-MM-DD), vendor_name, quote_number, "
        "line_items[] (description, quantity [number], quantity_unit, unit_price, total), total"
    ),
    "PRODUCT_SPEC_SHEET": (
        "date (YYYY-MM-DD), manufacturer_name, product_name, product_code, product_description, "
        "product_formula[] (ingredient, amount [number], unit [e.g. 'mg','g','mcg','IU']), "
        "capsule_type (e.g. 'Size 00 Vegetable Capsule' — the delivery form, not an ingredient), "
        "excipients[] (non-active ingredients listed without amounts, e.g. ['Magnesium Stearate']), "
        "count [integer], count_unit [e.g. 'capsule','tablet','softgel'], servings [integer], "
        "includes_packaging [true if the document also describes bottle/label/carton specs]"
    ),
    "PACKAGING_SPEC_SHEET": (
        "date (YYYY-MM-DD), manufacturer_name, product_name, product_code, product_description, "
        "count [integer], count_unit, servings [integer], "
        "packaging_components object with these normalized fields (set each to a string description or null): "
        "container, closure, filler, desiccant, neck_band, label, master_shipper, inner_shipper, pallet, "
        "extras[] (component_name, description) — for anything not in the list above. "
        "label_specs object: label_size, barcode, core_size, max_outer_diameter, wind_position, "
        "extras[] — for any additional label spec lines not covered above. "
        "Do NOT include product_formula — packaging spec sheets describe packaging, not formulas."
    ),
    "LABEL_PROOF": (
        "date (YYYY-MM-DD), manufacturer_name (the printing company), brand, product_name, "
        "product_code, barcode, version (it always starts with FNSKU or REV), "
        "count [integer], count_unit, servings [integer], label_size, corner_radius, substrate, inks, "
        "core_size, max_outer_diameter, wind_position, "
        "supplements_fact_panel[] (ingredient, amount_per_serving, daily_value_percent), "
        "other_ingredients, allergens, company (name, address, email, phone), "
        "suggested_use, marketing_text"
    ),
    "LABEL": (
        "brand, product_name, barcode, version, count [integer], count_unit, servings [integer], "
        "supplements_fact_panel[] (ingredient, amount_per_serving, daily_value_percent), "
        "other_ingredients, allergens, company (name, address, email, phone), "
        "suggested_use, marketing_text. "
        "If the label artwork has no readable text, the document should have been classified as UNKNOWN."
    ),
}


# ---------------------------------------------------------------------------
# Pass 1: classify only
# ---------------------------------------------------------------------------


def build_classification_prompt() -> str:
    """Lightweight prompt for pass 1 — returns only document_type + confidence."""
    return """\
Classify this supply chain document. Choose exactly one document_type:
  COA, INVOICE, QUOTE, PRODUCT_SPEC_SHEET, PACKAGING_SPEC_SHEET,
  LABEL, LABEL_PROOF, PAYMENT_PROOF, UNKNOWN

Definitions:
- COA: Certificate of Analysis (test results, lot numbers, pass/fail specifications)
- INVOICE: Invoice or Sales Order (line items, vendor, grand total)
- QUOTE: Quote or RFQ (quoted prices and quantities, not a confirmed order)
- PRODUCT_SPEC_SHEET: Formula/specification sheet (ingredients, formula, capsule type — primary focus is the formula)
- PACKAGING_SPEC_SHEET: Packaging specification (bottle, label roll, carton specs — primary focus is packaging)
- LABEL: Finished product label or label artwork (supplement facts panel, allergens, ingredients)
- LABEL_PROOF: Print proof from a printer for client review (has technical print specs: substrate, ink colors, corner radius, wind position)
- PAYMENT_PROOF: Bank payment confirmation or screenshot (payer, payee, amount, confirmation number)
- UNKNOWN: Cannot classify or unreadable

Set confidence: 1.0 = certain, 0.0 = total guess.
"""


# ---------------------------------------------------------------------------
# Pass 2: focused extraction for a specific document type
# ---------------------------------------------------------------------------


def build_extraction_prompt_for_type(doc_type: DocumentType) -> str:
    """Focused extraction prompt for a single document type. No classification step."""
    today = datetime.date.today().isoformat()
    rules = _FIELD_RULES[doc_type.value]
    return f"""\
You are a document data extractor for supply chain documents.
Today's date is {today}.

This document has been classified as {doc_type.value}. Extract ONLY the fields defined below.

FIELD RULES:
{rules}

GENERAL RULES:
- Extract exactly what the document says. Do not infer or fabricate data.
- If a field cannot be found, set it to null (or empty list for arrays).
- All quantity/count/servings fields are numbers (integers or floats), never strings.
- All dates must be in YYYY-MM-DD format.
- confidence: 1.0 = certain, 0.0 = total guess.
"""
