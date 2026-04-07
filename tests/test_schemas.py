"""Unit tests for schemas — no API key or network access required."""

import pytest
from pydantic import ValidationError

from schemas import (
    CoaExtraction,
    DocumentType,
    ExtractionResult,
    InvoicePayload,
    LabelPayload,
    LabelProofPayload,
    PackagingSpecSheetPayload,
    PaymentProofPayload,
    ProductSpecSheetPayload,
    QuotePayload,
)


# ---------------------------------------------------------------------------
# All payload models validate from expected JSON fixtures
# ---------------------------------------------------------------------------


def test_coa_extraction_validates():
    # CoaExtraction uses strict=True so we validate from JSON (as in production via model_validate_json)
    import json
    data = {
        "header_data": {
            "testing_lab_name": "Acme Labs",
            "product_name": "Vitamin C",
            "lot_number": "LOT001",
            "date_manufactured": "01/2026",
            "date_expiration": "01/2028",
        },
        "test_results": [
            {
                "test_category": "PHYSICAL",
                "specific_analyte": "Moisture Content",
                "test_method": "USP <921>",
                "specification_target": "NMT 5%",
                "raw_result_text": "2.1%",
                "result_operator": "=",
                "result_numeric": 2.1,
                "result_uom": "%",
                "lab_conclusion": "PASS",
            }
        ],
    }
    result = CoaExtraction.model_validate_json(json.dumps(data))
    assert result.header_data.product_name == "Vitamin C"
    assert result.header_data.lot_number == "LOT001"
    assert len(result.test_results) == 1
    assert result.test_results[0].specific_analyte == "Moisture Content"
    assert result.test_results[0].lab_conclusion.value == "PASS"


def test_invoice_payload_validates():
    data = {
        "date": "2026-02-10",
        "vendor_name": "Supplier Co.",
        "invoice_number": "INV-1001",
        "po_number": "PO-2001",
        "line_items": [
            {
                "description": "Raw Material A",
                "quantity": 100,
                "quantity_unit": "kg",
                "unit_price": 5.50,
                "total": 550.0,
            }
        ],
        "grand_total": 550.0,
    }
    result = InvoicePayload.model_validate(data)
    assert result.invoice_number == "INV-1001"
    assert result.grand_total == 550.0
    assert len(result.line_items) == 1
    assert result.line_items[0].quantity == 100.0
    assert result.line_items[0].quantity_unit == "kg"


def test_invoice_payload_deposit_fields():
    data = {
        "vendor_name": "ProTab Labs",
        "invoice_number": "INV-17095",
        "grand_total": 30675.0,
        "deposit_number": 1,
        "deposit_percentage": 0.5,
        "due_amount": 15337.5,
        "line_items": [],
    }
    result = InvoicePayload.model_validate(data)
    assert result.deposit_number == 1
    assert result.deposit_percentage == 0.5
    assert result.due_amount == 15337.5


def test_quote_payload_validates():
    data = {
        "date": "2026-03-01",
        "vendor_name": "QuoteCo",
        "quote_number": "Q-001",
        "line_items": [
            {
                "description": "Bottles",
                "quantity": 500,
                "quantity_unit": "bottle",
                "unit_price": 0.10,
                "total": 50.0,
            }
        ],
        "total": 50.0,
    }
    result = QuotePayload.model_validate(data)
    assert result.quote_number == "Q-001"
    assert result.total == 50.0


def test_product_spec_sheet_payload_validates():
    data = {
        "product_name": "Omega-3",
        "product_code": "SKU-101",
        "manufacturer_name": "NutriCo",
        "product_formula": [{"ingredient": "Fish Oil", "amount": 1000, "unit": "mg"}],
        "capsule_type": "Size 0 Softgel",
        "excipients": ["Gelatin", "Glycerin"],
        "count": 90,
        "count_unit": "softgel",
        "servings": 30,
        "includes_packaging": False,
    }
    result = ProductSpecSheetPayload.model_validate(data)
    assert result.product_name == "Omega-3"
    assert len(result.product_formula) == 1
    assert result.product_formula[0].ingredient == "Fish Oil"
    assert result.product_formula[0].amount == 1000.0
    assert result.capsule_type == "Size 0 Softgel"
    assert result.excipients == ["Gelatin", "Glycerin"]
    assert result.count == 90
    assert result.count_unit == "softgel"
    assert result.includes_packaging is False


def test_product_spec_sheet_includes_packaging_default():
    result = ProductSpecSheetPayload.model_validate({"product_name": "X"})
    assert result.includes_packaging is False


def test_packaging_spec_sheet_payload_validates():
    data = {
        "product_name": "Omega-3",
        "manufacturer_name": "NutriCo",
        "count": 90,
        "count_unit": "softgel",
        "packaging_components": {
            "container": "60cc HDPE natural",
            "closure": "28-400 CRC child-resistant cap",
            "filler": "16g rayon packing",
            "desiccant": "1g silica desiccant",
            "neck_band": "Clear perforated safety seal",
            "label": "3\" x 8\" label, FNSKU X001234",
            "master_shipper": "12-count master carton",
            "inner_shipper": None,
            "pallet": "48\" x 40\" standard wood pallet",
            "extras": [{"component_name": "case_label", "description": "3\" x 4\" white Avery label"}],
        },
        "label_specs": {
            "label_size": "3\" x 8\"",
            "barcode": "X001234",
            "core_size": "3\" diameter",
            "max_outer_diameter": "12\"",
            "wind_position": "left to right",
            "extras": ["Pressure sensitive die cut, 1/8\" gap between labels"],
        },
    }
    result = PackagingSpecSheetPayload.model_validate(data)
    assert result.product_name == "Omega-3"
    assert result.packaging_components.container == "60cc HDPE natural"
    assert result.packaging_components.closure == "28-400 CRC child-resistant cap"
    assert result.packaging_components.neck_band == "Clear perforated safety seal"
    assert len(result.packaging_components.extras) == 1
    assert result.packaging_components.extras[0].component_name == "case_label"
    assert result.label_specs.label_size == "3\" x 8\""
    assert result.label_specs.wind_position == "left to right"
    assert len(result.label_specs.extras) == 1


def test_packaging_spec_sheet_defaults_to_empty_components():
    result = PackagingSpecSheetPayload.model_validate({"product_name": "X"})
    assert result.packaging_components.container is None
    assert result.packaging_components.extras == []
    assert result.label_specs.label_size is None
    assert result.label_specs.extras == []


def test_label_payload_validates():
    data = {
        "brand": "VitaBrand",
        "product_name": "Vitamin D3",
        "barcode": "012345678901",
        "count": 60,
        "count_unit": "capsule",
        "servings": 60,
        "supplements_fact_panel": [
            {
                "ingredient": "Vitamin D3",
                "amount_per_serving": "25 mcg",
                "daily_value_percent": "125%",
            }
        ],
        "other_ingredients": "Cellulose, Silica",
        "allergens": "None",
        "company": {
            "name": "VitaBrand Inc.",
            "address": "123 Health St.",
            "email": None,
            "phone": None,
        },
        "suggested_use": "Take 1 capsule daily",
        "marketing_text": "Supports bone health",
    }
    result = LabelPayload.model_validate(data)
    assert result.brand == "VitaBrand"
    assert result.count == 60
    assert result.count_unit == "capsule"
    assert len(result.supplements_fact_panel) == 1
    assert result.company is not None
    assert result.company.name == "VitaBrand Inc."


def test_payment_proof_payload_validates():
    data = {
        "date": "2026-03-09",
        "payer": "Natural Cure Labs - 8176",
        "payee": "BEST NUTRA, INC.",
        "amount": 5247.84,
        "confirmation_number": "m5xyf1ty4",
        "payment_method": "Zelle",
    }
    result = PaymentProofPayload.model_validate(data)
    assert result.payer == "Natural Cure Labs - 8176"
    assert result.payee == "BEST NUTRA, INC."
    assert result.amount == 5247.84
    assert result.confirmation_number == "m5xyf1ty4"


def test_label_proof_payload_validates():
    data = {
        "date": "2026-02-25",
        "manufacturer_name": "Fortis Labels",
        "product_name": "LOQUAT LEAF 10:1 EXTRACT",
        "product_code": "540837",
        "count": 60,
        "count_unit": "capsule",
        "servings": 60,
        "label_size": "2.75\" x 7\"",
        "corner_radius": "0.125 in.",
        "substrate": "2M Metallized BOPP/S7000ER/1.2 Mil PET",
        "inks": "Cyan, Magenta, Yellow, Black, Premium White",
        "supplements_fact_panel": [
            {"ingredient": "Loquat Leaf Extract", "amount_per_serving": "600 mg", "daily_value_percent": None}
        ],
    }
    result = LabelProofPayload.model_validate(data)
    assert result.label_size == "2.75\" x 7\""
    assert result.corner_radius == "0.125 in."
    assert result.substrate == "2M Metallized BOPP/S7000ER/1.2 Mil PET"
    assert len(result.supplements_fact_panel) == 1


# ---------------------------------------------------------------------------
# FormulaComponent amount is a float (not a string)
# ---------------------------------------------------------------------------


def test_formula_component_amount_is_float():
    from schemas import FormulaComponent
    fc = FormulaComponent.model_validate({"ingredient": "Vitamin C", "amount": 500, "unit": "mg"})
    assert fc.amount == 500.0
    assert isinstance(fc.amount, float)


def test_formula_component_coerces_string_amount():
    from schemas import FormulaComponent
    fc = FormulaComponent.model_validate({"ingredient": "Vitamin C", "amount": "500", "unit": "mg"})
    assert fc.amount == 500.0


# ---------------------------------------------------------------------------
# Union dispatch through ExtractionResult
# ---------------------------------------------------------------------------


def test_extraction_result_holds_coa_extraction():
    # In production, CoaExtraction is always instantiated via PAYLOAD_SCHEMA_MAP, never
    # through union dispatch. Test that ExtractionResult can hold a CoaExtraction payload.
    import json
    coa = CoaExtraction.model_validate_json(json.dumps({
        "header_data": {
            "testing_lab_name": "Acme Labs",
            "product_name": "Vitamin C",
            "lot_number": "LOT001",
        },
        "test_results": [
            {
                "test_category": "PHYSICAL",
                "specific_analyte": "Moisture",
                "specification_target": "NMT 5%",
                "raw_result_text": "2.1%",
                "result_operator": "=",
                "lab_conclusion": "PASS",
            }
        ],
    }))
    result = ExtractionResult(
        document_type=DocumentType.COA,
        confidence=0.95,
        extracted_date="2026-04-06",
        payload=coa,
    )
    assert isinstance(result.payload, CoaExtraction)
    assert result.payload.header_data.product_name == "Vitamin C"


def test_extraction_result_dispatches_packaging_not_product():
    """PackagingSpecSheetPayload uses a nested PackagingComponents object —
    distinct enough from ProductSpecSheetPayload that Pydantic smart union
    correctly dispatches without the inheritance trick."""
    data = {
        "document_type": "PACKAGING_SPEC_SHEET",
        "confidence": 0.9,
        "extracted_date": "2026-04-06",
        "payload": {
            "product_name": "Omega-3",
            "packaging_components": {
                "container": "HDPE 60cc",
                "extras": [],
            },
            "label_specs": {
                "label_size": "4x2 inch",
                "extras": [],
            },
        },
    }
    result = ExtractionResult.model_validate(data)
    assert isinstance(result.payload, PackagingSpecSheetPayload)


def test_extraction_result_dispatches_payment_proof():
    data = {
        "document_type": "PAYMENT_PROOF",
        "confidence": 1.0,
        "extracted_date": "2026-04-06",
        "payload": {
            "date": "2026-03-09",
            "payer": "Natural Cure Labs",
            "payee": "Best Nutra Inc.",
            "amount": 5247.84,
            "confirmation_number": "m5xyf1ty4",
        },
    }
    result = ExtractionResult.model_validate(data)
    assert isinstance(result.payload, PaymentProofPayload)
    assert result.payload.amount == 5247.84


def test_extraction_result_dispatches_label_proof():
    data = {
        "document_type": "LABEL_PROOF",
        "confidence": 1.0,
        "extracted_date": "2026-04-06",
        "payload": {
            "product_name": "Loquat Leaf Extract",
            "label_size": "2.75\" x 7\"",
            "corner_radius": "0.125 in.",
            "substrate": "2M Metallized BOPP",
            "inks": "CMYK + White",
        },
    }
    result = ExtractionResult.model_validate(data)
    assert isinstance(result.payload, LabelProofPayload)
    assert result.payload.label_size == "2.75\" x 7\""


# ---------------------------------------------------------------------------
# ExtractionResult with UNKNOWN document_type and null payload
# ---------------------------------------------------------------------------


def test_extraction_result_unknown_null_payload_validates():
    data = {
        "document_type": "UNKNOWN",
        "confidence": 0.1,
        "extracted_date": "2026-04-06",
        "payload": None,
        "raw_text_fallback": "Could not parse this document.",
    }
    result = ExtractionResult.model_validate(data)
    assert result.document_type == DocumentType.UNKNOWN
    assert result.payload is None
    assert result.raw_text_fallback == "Could not parse this document."


# ---------------------------------------------------------------------------
# confidence field validation
# ---------------------------------------------------------------------------


def test_confidence_rejects_below_zero():
    with pytest.raises(ValidationError):
        ExtractionResult.model_validate(
            {"document_type": "UNKNOWN", "confidence": -0.01, "payload": None}
        )


def test_confidence_rejects_above_one():
    with pytest.raises(ValidationError):
        ExtractionResult.model_validate(
            {"document_type": "UNKNOWN", "confidence": 1.01, "payload": None}
        )


def test_confidence_accepts_boundary_values():
    for val in (0.0, 1.0):
        result = ExtractionResult.model_validate(
            {"document_type": "UNKNOWN", "confidence": val, "payload": None}
        )
        assert result.confidence == val
