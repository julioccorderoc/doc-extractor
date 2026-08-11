"""Schema contract tests — no API key or network required.

These lock the two properties that are easy to regress and expensive to notice:
every DocumentType routes to a payload model, and the fields whose absence is
meaningful stay optional. A field that quietly becomes required again is an
instruction to the model to invent a value for it.
"""

from unittest.mock import MagicMock

import pytest

from gemini import UsageTally
from schemas import (
    CoaExtraction,
    DocumentType,
    ExtractionResult,
    LabConclusion,
    MeasurementBasis,
    PackingListPayload,
    PackoutCaseType,
    PackoutSheetPayload,
    PackoutWeightBasis,
    PAYLOAD_SCHEMA_MAP,
    SpecBoundType,
)
from summary import build_summary


# ---------------------------------------------------------------------------
# Routing — every declared type extracts into something
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("doc_type", list(DocumentType))
def test_every_document_type_has_a_payload_schema(doc_type):
    assert doc_type in PAYLOAD_SCHEMA_MAP


def test_packout_and_packing_list_route_to_distinct_schemas():
    """The whole point of two types is two shapes — a shared model defeats it."""
    assert PAYLOAD_SCHEMA_MAP[DocumentType.PACKOUT_SHEET] is PackoutSheetPayload
    assert PAYLOAD_SCHEMA_MAP[DocumentType.PACKING_LIST] is PackingListPayload


# ---------------------------------------------------------------------------
# Packout — gaps stay open
# ---------------------------------------------------------------------------


def test_packout_case_leaves_unstated_units_per_case_null():
    payload = PackoutSheetPayload.model_validate(
        {"cases": [{"case_count": 24, "sku_ref": "MONO-600"}]}
    )
    case = payload.cases[0]
    assert case.units_per_case is None, "an unstated case size must stay null, never 0"
    assert case.case_type == PackoutCaseType.UNKNOWN
    assert case.exp_date is None


def test_packout_pallet_weight_basis_defaults_to_unknown():
    payload = PackoutSheetPayload.model_validate(
        {"pallets": [{"pallet_count": 9, "weight_lbs": 620.0}]}
    )
    assert payload.pallets[0].weight_basis == PackoutWeightBasis.UNKNOWN


def test_packout_case_count_must_be_positive():
    """Zero cases is not a line — it is a parse failure worth surfacing."""
    with pytest.raises(ValueError):
        PackoutSheetPayload.model_validate({"cases": [{"case_count": 0}]})


def test_packout_empty_document_validates():
    """An empty packout still parses; the consumer flags the emptiness."""
    payload = PackoutSheetPayload.model_validate({})
    assert payload.cases == []
    assert payload.pallets == []
    assert payload.stated_totals == []


# ---------------------------------------------------------------------------
# COA — the fields whose absence is meaningful stay optional
# ---------------------------------------------------------------------------


def test_coa_accepts_a_result_row_with_no_spec_or_conclusion():
    coa = CoaExtraction.model_validate(
        {
            "header_data": {},
            "test_results": [
                {
                    "test_category": "PHYSICAL",
                    "specific_analyte": "Appearance",
                    "raw_result_text": "White powder",
                    "result_operator": "CONFORMS",
                }
            ],
        }
    )
    row = coa.test_results[0]
    assert row.specification_target is None
    assert row.lab_conclusion is None


def test_coa_header_carries_a_report_date():
    coa = CoaExtraction.model_validate(
        {"header_data": {"date_report": "11/14/2026"}, "test_results": []}
    )
    assert coa.header_data.date_report == "11/14/2026"


def test_coa_header_tolerates_a_certificate_with_no_lot_number():
    coa = CoaExtraction.model_validate({"header_data": {}, "test_results": []})
    assert coa.header_data.lot_number is None


def test_coa_header_separates_finished_lot_from_the_others_and_the_report_number():
    """Three identifiers that look alike and mean different things. A certificate
    printing an in-process lot beside the finished one, or named by its report
    number, must not collapse them into lot_number."""
    coa = CoaExtraction.model_validate(
        {
            "header_data": {
                "lot_number": "2025-27724",
                "other_lots_noted": "IN-PROCESS LOT # 2025-27721",
                "report_number": "115182",
            },
            "test_results": [],
        }
    )
    header = coa.header_data
    assert header.lot_number == "2025-27724"
    assert header.other_lots_noted == "IN-PROCESS LOT # 2025-27721"
    assert header.report_number == "115182"


def test_coa_records_spec_and_result_bases_independently():
    """The mismatch is the finding. A heavy metal reported per capsule against a
    per-day limit is not comparable, and flattening the two bases hides that."""
    coa = CoaExtraction.model_validate(
        {
            "header_data": {},
            "test_results": [
                {
                    "test_category": "HEAVY_METAL",
                    "specific_analyte": "LEAD",
                    "specification_target": "<5 µg/day",
                    "specification_uom": "µg/day",
                    "spec_bound_type": "MAX",
                    "spec_high": 5.0,
                    "spec_basis": "PER_DAY",
                    "raw_result_text": "0.064 µg/cap",
                    "result_operator": "=",
                    "result_numeric": 0.064,
                    "result_uom": "µg/cap",
                    "result_basis": "PER_CAPSULE",
                }
            ],
        }
    )
    row = coa.test_results[0]
    assert row.spec_basis == MeasurementBasis.PER_DAY
    assert row.result_basis == MeasurementBasis.PER_CAPSULE
    assert row.spec_basis != row.result_basis
    assert row.spec_bound_type == SpecBoundType.MAX
    assert row.spec_high == 5.0


def test_coa_basis_defaults_to_unknown_not_to_a_guess():
    coa = CoaExtraction.model_validate(
        {
            "header_data": {},
            "test_results": [
                {
                    "test_category": "PHYSICAL",
                    "specific_analyte": "Appearance",
                    "raw_result_text": "Conforms",
                    "result_operator": "CONFORMS",
                }
            ],
        }
    )
    row = coa.test_results[0]
    assert row.spec_basis == MeasurementBasis.UNKNOWN
    assert row.result_basis == MeasurementBasis.UNKNOWN
    assert row.spec_bound_type == SpecBoundType.NONE
    assert row.footnote_markers == []


def test_coa_keeps_the_certificate_verdict_and_our_assessment_apart():
    """Two facts about one result. Collapsing them loses the disagreement, which
    is exactly the signal worth investigating."""
    coa = CoaExtraction.model_validate(
        {
            "header_data": {},
            "test_results": [
                {
                    "test_category": "ACTIVE_INGREDIENT",
                    "specific_analyte": "L-Lysine HCl",
                    "specification_target": "600 - 900 mg",
                    "spec_bound_type": "RANGE",
                    "spec_low": 600.0,
                    "spec_high": 900.0,
                    "raw_result_text": "† 580 mg",
                    "result_operator": "=",
                    "result_numeric": 580.0,
                    "footnote_markers": ["†"],
                    "lab_conclusion": "PASS",
                    "assessed_conclusion": "OUT_OF_SPECIFICATION",
                }
            ],
        }
    )
    row = coa.test_results[0]
    assert row.lab_conclusion == LabConclusion.PASS
    assert row.assessed_conclusion == LabConclusion.OOS
    assert row.lab_conclusion != row.assessed_conclusion
    assert row.footnote_markers == ["†"]


def test_coa_assessment_may_be_absent_while_the_certificate_still_judges():
    """An undecidable row must be able to say so. A default verdict would read as
    an assessment nobody made."""
    coa = CoaExtraction.model_validate(
        {
            "header_data": {},
            "test_results": [
                {
                    "test_category": "ACTIVE_INGREDIENT",
                    "specific_analyte": "Curcumin",
                    "specification_target": "100-150%",
                    "raw_result_text": "128.84 mg",
                    "result_operator": "=",
                    "lab_conclusion": "PASS",
                }
            ],
        }
    )
    assert coa.test_results[0].assessed_conclusion is None


def test_coa_captures_document_footnotes_verbatim():
    """A footnote can redefine the limit itself, so it is data, not decoration."""
    note = (
        "** As per USP <1111> when an acceptance criteria for microbiological quality "
        "is prescribed to be as <100,000, it is interpreted as maximum acceptable "
        "count =200,000 cfu/g."
    )
    coa = CoaExtraction.model_validate(
        {
            "header_data": {},
            "test_results": [],
            "footnotes": [{"marker": "**", "text": note}],
        }
    )
    assert coa.footnotes[0].marker == "**"
    assert coa.footnotes[0].text == note


def test_coa_footnotes_default_to_empty_not_null():
    coa = CoaExtraction.model_validate({"header_data": {}, "test_results": []})
    assert coa.footnotes == []


# ---------------------------------------------------------------------------
# Token usage — unknown is null, never zero
# ---------------------------------------------------------------------------


def _response(prompt: int, output: int, total: int) -> MagicMock:
    resp = MagicMock()
    resp.usage_metadata.prompt_token_count = prompt
    resp.usage_metadata.candidates_token_count = output
    resp.usage_metadata.total_token_count = total
    return resp


def test_usage_tally_sums_across_passes():
    tally = UsageTally()
    tally.add(_response(100, 10, 110))
    tally.add(_response(900, 200, 1100))
    assert tally.seen is True
    assert tally.calls == 2
    assert tally.prompt_tokens == 1000
    assert tally.output_tokens == 210
    assert tally.total_tokens == 1210


def test_usage_tally_stays_unseen_without_metadata():
    """No metadata means unknown cost — the caller must not read it as free."""
    resp = MagicMock()
    resp.usage_metadata = None
    tally = UsageTally()
    tally.add(resp)
    assert tally.seen is False
    assert tally.calls == 1


def test_extraction_result_usage_is_optional():
    res = ExtractionResult(document_type=DocumentType.COA, confidence=1.0)
    assert res.usage is None


# ---------------------------------------------------------------------------
# Summary — the new type has a line, and tokens surface
# ---------------------------------------------------------------------------


def test_packout_summary_reports_case_and_pallet_counts():
    payload = PackoutSheetPayload.model_validate(
        {
            "vendor_ref": "NutraSky",
            "cases": [{"case_count": 20}, {"case_count": 4}],
            "pallets": [{"pallet_count": 2}],
            "stated_totals": [{"units": 2190}],
        }
    )
    res = ExtractionResult(
        document_type=DocumentType.PACKOUT_SHEET, confidence=0.9, payload=payload
    )
    line = build_summary(res, "packout.pdf")
    assert "PACKOUT_SHEET" in line
    assert "24 cases" in line, "case_count is summed, not counted as rows"
    assert "2 pallets" in line
    assert "stated 2190" in line


def test_summary_omits_tokens_when_usage_is_absent():
    res = ExtractionResult(document_type=DocumentType.COA, confidence=1.0)
    assert "tokens=" not in build_summary(res, "coa.pdf")


def _coa_with(conclusions: list[str | None]) -> CoaExtraction:
    return CoaExtraction.model_validate(
        {
            "header_data": {"lot_number": "L1", "product_name": "Monolaurin"},
            "test_results": [
                {
                    "test_category": "PHYSICAL",
                    "specific_analyte": f"t{i}",
                    "raw_result_text": "x",
                    "result_operator": "CONFORMS",
                    **({"lab_conclusion": c} if c else {}),
                }
                for i, c in enumerate(conclusions)
            ],
        }
    )


def test_summary_does_not_report_unjudged_rows_as_failures():
    """'2/5 PASS' read as three failures when three rows carried no verdict at all."""
    res = ExtractionResult(
        document_type=DocumentType.COA,
        confidence=1.0,
        payload=_coa_with(["PASS", "PASS", "INFORMATION_ONLY", None, None]),
    )
    line = build_summary(res, "coa.pdf")
    assert "2 pass" in line
    assert "3 unjudged" in line
    assert "FAIL" not in line


def test_summary_surfaces_a_real_failure():
    res = ExtractionResult(
        document_type=DocumentType.COA,
        confidence=1.0,
        payload=_coa_with(["PASS", "OUT_OF_SPECIFICATION"]),
    )
    assert "1 FAIL" in build_summary(res, "coa.pdf")
