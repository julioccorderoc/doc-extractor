"""Certificate of Analysis (COA) schema."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from ._shared import ProductIdentifiers


class ResultOperator(str, Enum):
    """Mathematical or logical state of the test result."""

    EQ = "="
    LT = "<"
    GT = ">"
    LTE = "<="
    GTE = ">="
    ND = "ND"  # Non-Detect / Not Detected
    ABSENT = "ABSENT"  # Used for Negative microbial results
    CONFORMS = "CONFORMS"  # Used for physical descriptions (e.g., color, size)


class TestCategory(str, Enum):
    """Standardized classification of the analyte."""

    PHYSICAL = "PHYSICAL"  # e.g., Appearance, Weight, Disintegration
    ACTIVE_INGREDIENT = "ACTIVE_INGREDIENT"  # e.g., Monolaurin, Vitamin C
    MICROBIOLOGY = "MICROBIOLOGY"  # e.g., E. coli, Total Plate Count
    HEAVY_METAL = "HEAVY_METAL"  # e.g., Lead, Arsenic, Cadmium
    IDENTITY = "IDENTITY"  # e.g., FTIR Correlation


class LabConclusion(str, Enum):
    """The compliance state of the individual line item."""

    PASS = "PASS"
    FAIL = "FAIL"
    OOS = "OUT_OF_SPECIFICATION"
    INFO_ONLY = "INFORMATION_ONLY"


class MeasurementBasis(str, Enum):
    """What a number is measured *per*.

    Specs and results routinely use different denominators on the same row — a
    heavy metal reported '0.064 ug/cap' against a spec of '<5 ug/day' is not a
    comparison until both sides are converted, and the conversion needs the
    label's daily dose, which is not on the certificate. Recording the basis is
    what makes the mismatch visible instead of silent.
    """

    PER_CAPSULE = "PER_CAPSULE"  # e.g. 'mcg/cap', 'mcg/Unit', 'per tablet'
    PER_SERVING = "PER_SERVING"  # e.g. 'mcg/ 2 Capsules', 'mg/Serving'
    PER_DAY = "PER_DAY"  # e.g. 'ug/day' — already a daily exposure
    PER_CONTAINER = "PER_CONTAINER"  # e.g. 'per bottle'
    CONCENTRATION = "CONCENTRATION"  # e.g. 'ppm', 'cfu/g', '%', 'mg/kg'
    UNKNOWN = "UNKNOWN"  # no denominator printed — do NOT guess one


class SpecBoundType(str, Enum):
    """The shape of the acceptance limit, so a consumer never re-parses prose."""

    MAX = "MAX"  # NMT, 'Not More Than', '<', '<='
    MIN = "MIN"  # NLT, 'Not Less Than', '>', '>='
    RANGE = "RANGE"  # '893 - 987 mg', '835 mg +/- 10%'
    EXACT = "EXACT"  # a single target value with no tolerance printed
    QUALITATIVE = "QUALITATIVE"  # 'Absent/10g', 'Conforms', 'Not Detected'
    NONE = "NONE"  # information-only row, no limit printed


class Footnote(BaseModel):
    """A marked note on the certificate, captured verbatim.

    Footnotes are not decoration: one may redefine the acceptance criterion
    itself (a '**' invoking USP <1111> reads '<100,000' as a maximum of
    200,000 cfu/g), another may justify accepting a result below its printed
    floor (a 'dagger' invoking ISO 17025 measurement uncertainty). A verdict
    computed without the footnote text is wrong in both directions.
    """

    model_config = ConfigDict(use_enum_values=True)

    marker: str = Field(
        ...,
        description=(
            "The marker exactly as printed next to the note. Examples: '*', '**', "
            "'†', '(1)'."
        ),
    )
    text: str = Field(
        ...,
        description="The full note text, verbatim and unabridged. Do not summarize it.",
    )


class TestResult(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    test_category: TestCategory = Field(
        ...,
        description=(
            "Categorize the test based on the analyte. Use PHYSICAL for weights/appearance, "
            "ACTIVE_INGREDIENT for active compounds, MICROBIOLOGY for pathogens/counts, "
            "HEAVY_METAL for elements."
        ),
    )
    specific_analyte: str = Field(
        ...,
        description=(
            "The exact name of the item being tested. Examples: 'Lead', 'Total Plate Count', "
            "'Average Weight per Capsule', 'MONOLAURIN (GLYCEROL MONOLAURATE)'."
        ),
    )
    test_method: Optional[str] = Field(
        None,
        description=(
            "The scientific method or standard used. Examples: 'ICP-MS', 'HPLC', 'USP <2021>', "
            "'Visual', 'By Input'. Leave null if omitted."
        ),
    )
    specification_target: Optional[str] = Field(
        None,
        description=(
            "The exact text defining the acceptable limit or range. Combine Low/Target/High limits "
            "into a single string if separated on the document. "
            "Examples: 'NMT 10.00 mcg/ 2 Capsules', '835.00 mg ± 10%'. "
            "Null when the certificate prints no limit for this row — do not restate the "
            "result as its own specification."
        ),
    )
    specification_uom: Optional[str] = Field(
        None,
        description=(
            "The unit attached to the specification, isolated. Example: for "
            "'NMT 3 mcg/Unit' this is 'mcg/Unit'. Null when the limit is qualitative "
            "or prints no unit. Keep it even when it repeats result_uom — a spec whose "
            "unit differs from the result's unit is the signal that matters."
        ),
    )
    spec_bound_type: SpecBoundType = Field(
        SpecBoundType.NONE,
        description=(
            "The shape of the limit. Use NONE for an information-only row with no "
            "printed specification, QUALITATIVE for 'Absent/10g' or 'Conforms'."
        ),
    )
    spec_low: Optional[float] = Field(
        None,
        description=(
            "Lower bound as a number, when one is printed or directly implied. "
            "For '893 - 987 mg' this is 893. For '835.00 mg ± 10%' this is 751.5. "
            "Null for MAX and QUALITATIVE limits."
        ),
    )
    spec_high: Optional[float] = Field(
        None,
        description=(
            "Upper bound as a number. For 'NMT 3 mcg/Unit' this is 3. For "
            "'893 - 987 mg' this is 987. Null for MIN and QUALITATIVE limits."
        ),
    )
    spec_basis: MeasurementBasis = Field(
        MeasurementBasis.UNKNOWN,
        description=(
            "What the SPECIFICATION is measured per, read from the spec's own unit. "
            "'<5 µg/day' is PER_DAY, 'NMT 10.00 mcg/ 2 Capsules' is PER_SERVING, "
            "'NMT 3 mcg/Unit' is PER_CAPSULE, '0.5ppm' is CONCENTRATION. "
            "UNKNOWN when no denominator is printed — never infer one from the result."
        ),
    )
    raw_result_text: str = Field(
        ...,
        description=(
            "The exact, unmodified string extracted from the result column. "
            "Example: '<0.014 mcg/ 2 Capsules'."
        ),
    )
    result_operator: ResultOperator = Field(
        ...,
        description=(
            "The logical operator derived from the raw result. If the text says '< 10', use 'LT'. "
            "If it says 'Absent' or 'Negative', use 'ABSENT'. If it's just a number, use 'EQ'."
        ),
    )
    result_numeric: Optional[float] = Field(
        None,
        description=(
            "The isolated numeric value from the result. Do not include units or operators. "
            "If the result is 'Absent', 'Negative', 'Conforms', or 'ND', this must be null."
        ),
    )
    result_uom: Optional[str] = Field(
        None,
        description=(
            "The isolated unit of measure. Examples: 'mcg/cap', 'cfu/gm', 'mg'. "
            "Leave null for unitless results like visual conformity."
        ),
    )
    result_basis: MeasurementBasis = Field(
        MeasurementBasis.UNKNOWN,
        description=(
            "What the RESULT is measured per, read from the result's own unit — "
            "independently of spec_basis. '0.064 µg/cap' is PER_CAPSULE even when the "
            "spec beside it is PER_DAY. That disagreement is a fact worth recording, "
            "not an error to smooth over."
        ),
    )
    label_claim_text: Optional[str] = Field(
        None,
        description=(
            "The declared label claim this row is measured against, verbatim, when the "
            "certificate prints it in its own column. Example: '125.00 mg / 1 Capsule(s)'. "
            "Required to make sense of a percentage specification — '100-150%' is "
            "meaningless without the amount it is a percentage of."
        ),
    )
    label_claim_numeric: Optional[float] = Field(
        None,
        description="The label claim as a number, units stripped. Null when not printed.",
    )
    label_claim_uom: Optional[str] = Field(
        None,
        description="The label claim's unit, isolated. Example: 'mg'.",
    )
    footnote_markers: list[str] = Field(
        default_factory=list,
        description=(
            "Every footnote marker printed on THIS row, in either the specification or "
            "the result cell. Example: ['**'] for a result printed '=180,000 cfu/g**'. "
            "Empty list when the row carries none. The marker text itself belongs in "
            "the document-level footnotes array."
        ),
    )
    lab_conclusion: Optional[LabConclusion] = Field(
        None,
        description=(
            "The certificate's own verdict for this row. PASS when it reports the result as "
            "conforming, FAIL when it reports a violation, INFORMATION_ONLY when no "
            "specification exists for the row. Null when the certificate states no verdict and "
            "no specification to judge against — do not derive one by comparing numbers "
            "yourself."
        ),
    )
    assessed_conclusion: Optional[LabConclusion] = Field(
        None,
        description=(
            "YOUR OWN assessment of the result against the specification, kept separate "
            "from the certificate's verdict so a reader can tell them apart. Null whenever "
            "the comparison is not decidable from this row alone — no printed limit, a "
            "percentage spec with no label claim, or a spec and result on different bases "
            "(a per-day limit against a per-capsule result). Null is the correct answer far "
            "more often than a guess is; an assessment that disagrees with lab_conclusion "
            "is a finding, and a fabricated one destroys that signal."
        ),
    )


class CoaHeader(ProductIdentifiers):
    model_config = ConfigDict(use_enum_values=True)

    testing_lab_name: Optional[str] = Field(
        None,
        description=(
            "The name of the laboratory that performed the testing and issued the certificate. "
            "Examples: 'ProTab Laboratories', 'NutraStar', 'VitaNorth'. Null if the certificate "
            "names no lab — do not substitute the manufacturer or the brand."
        ),
    )
    manufacturer_name: Optional[str] = Field(
        None,
        description=(
            "The entity that manufactured the physical product, if explicitly distinct from the "
            "testing lab. Example: 'NutraStar Inc'."
        ),
    )
    brand: Optional[str] = Field(
        None,
        description=(
            "The brand or customer the product was manufactured for. Example: 'Natural Cure labs'."
        ),
    )
    product_name: Optional[str] = Field(
        None,
        description="The full name of the dietary supplement product.",
    )
    lot_number: Optional[str] = Field(
        None,
        description=(
            "The FINISHED PRODUCT lot number, and nothing else — the code that ends up on "
            "the bottle. When the certificate prints several lots (In-Process, Bulk, "
            "Packaging, Manufacturing), take the one labelled finished product or finished "
            "good, and put every other one in other_lots_noted. If no lot is labelled as "
            "finished, leave this null and record what IS printed in other_lots_noted rather "
            "than promoting a guess. Null when the certificate prints no lot at all — the "
            "consumer treats an absent lot differently from a wrong one."
        ),
    )
    other_lots_noted: Optional[str] = Field(
        None,
        description=(
            "Every other lot identifier on the certificate, verbatim and WITH the label the "
            "document gives it, so a human or downstream agent can judge. Example: "
            "'IN-PROCESS LOT # 2025-27721; Packaging Lot 22137'. Null when the certificate "
            "prints only one lot."
        ),
    )
    report_number: Optional[str] = Field(
        None,
        description=(
            "The laboratory's own certificate, report, or work-order number, exactly as "
            "printed. This identifies the DOCUMENT, not the batch — a third-party lab report "
            "and the manufacturer's own COA for one lot carry different report numbers. "
            "Never copy the lot number here, and never promote a report number into "
            "lot_number. Null when none is printed."
        ),
    )
    po_number: Optional[str] = Field(
        None,
        description="Purchase Order number associated with the batch. Leave null if absent.",
    )
    date_report: Optional[str] = Field(
        None,
        description=(
            "The date the certificate itself was issued, reported, or approved — distinct "
            "from the manufacture and expiration dates. Extract the exact text "
            "(e.g., '11/14/2026', '2026-11-14'). Leave null if the certificate shows only "
            "manufacture and expiration dates."
        ),
    )
    date_manufactured: Optional[str] = Field(
        None,
        description=(
            "The date the product was manufactured. Extract the exact text "
            "(e.g., '02/2026', '07/2023')."
        ),
    )
    date_expiration: Optional[str] = Field(
        None,
        description=(
            "The expiration or best by date. Extract the exact text (e.g., '02/2029', '11/2028')."
        ),
    )
    serving_size_text: Optional[str] = Field(
        None,
        description="The defined serving size as printed text. Example: '2 Capsules', '1'.",
    )
    other_ingredients: Optional[str] = Field(
        None,
        description=(
            "The full text block listing 'Other Ingredients' or excipients. "
            "Example: 'Vegetable (Hypromellose) Capsule, Rice Flour.' Leave null if not present."
        ),
    )


class CoaExtraction(BaseModel):
    """Root schema for COA extraction. Represents a complete Certificate of Analysis."""

    model_config = ConfigDict(use_enum_values=True)

    header_data: CoaHeader = Field(
        ...,
        description="The document-level metadata establishing product identity and chain of custody.",
    )
    test_results: list[TestResult] = Field(
        ...,
        description="An array containing every individual test performed on the certificate. Do not skip any rows.",
    )
    footnotes: list[Footnote] = Field(
        default_factory=list,
        description=(
            "Every marked footnote printed anywhere on the certificate, verbatim. These "
            "change what the numbers mean — one can redefine an acceptance criterion, "
            "another can justify a result that sits outside its printed limit. Capture them "
            "even when no row appears to reference them. Empty list when the document has none."
        ),
    )
