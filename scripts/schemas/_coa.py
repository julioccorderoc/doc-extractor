"""Certificate of Analysis (COA) schema."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


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
    specification_target: str = Field(
        ...,
        description=(
            "The exact text defining the acceptable limit or range. Combine Low/Target/High limits "
            "into a single string if separated on the document. "
            "Examples: 'NMT 10.00 mcg/ 2 Capsules', '835.00 mg ± 10%'."
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
    lab_conclusion: LabConclusion = Field(
        ...,
        description=(
            "Assess if the result meets the specification_target. If the result conforms to the spec, "
            "output PASS. If it violates the spec, output FAIL. If no spec exists, output INFO_ONLY."
        ),
    )


class CoaHeader(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    testing_lab_name: str = Field(
        ...,
        description=(
            "The name of the laboratory that performed the testing and issued the certificate. "
            "Examples: 'ProTab Laboratories', 'NutraStar', 'VitaNorth'."
        ),
    )
    manufacturer_name: Optional[str] = Field(
        None,
        description=(
            "The entity that manufactured the physical product, if explicitly distinct from the "
            "testing lab. Example: 'NutraStar Inc'."
        ),
    )
    customer_name: Optional[str] = Field(
        None,
        description=(
            "The brand or customer the product was manufactured for. Example: 'Natural Cure labs'."
        ),
    )
    product_name: str = Field(
        ...,
        description="The full name of the dietary supplement product.",
    )
    vendor_product_id: Optional[str] = Field(
        None,
        description="The internal ID, formula number, or SKU of the item for the testing lab or manufacturer.",
    )
    buyer_product_id: Optional[str] = Field(
        None,
        description="The ID or SKU of the item from the customer's/buyer's perspective.",
    )
    lot_number: str = Field(
        ...,
        description=(
            "The primary lot number for the finished good. If multiple lots exist "
            "(e.g., Packaging Lot vs Manufacturing Lot), prioritize the Finished Product / "
            "Manufacturing Lot."
        ),
    )
    po_number: Optional[str] = Field(
        None,
        description="Purchase Order number associated with the batch. Leave null if absent.",
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
    serving_size: Optional[str] = Field(
        None,
        description="The defined serving size for the product. Example: '2 Capsules', '1'.",
    )
    other_ingredients_statement: Optional[str] = Field(
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
