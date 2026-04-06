"""Pydantic v2 models for document extraction schemas.

The PRD (docs/PRD.md) is the source of truth for field definitions.
These models generate JSON Schema via .model_json_schema() which is passed
to the Gemini API's response_schema parameter.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional, Union

from pydantic import BaseModel, Field


class DocumentType(str, Enum):
    COA = "COA"
    INVOICE = "INVOICE"
    QUOTE = "QUOTE"
    PRODUCT_SPEC_SHEET = "PRODUCT_SPEC_SHEET"
    PACKAGING_SPEC_SHEET = "PACKAGING_SPEC_SHEET"
    LABEL = "LABEL"
    LABEL_PROOF = "LABEL_PROOF"
    PAYMENT_PROOF = "PAYMENT_PROOF"
    UNKNOWN = "UNKNOWN"


# ---------------------------------------------------------------------------
# Shared sub-models
# ---------------------------------------------------------------------------


class FormulaComponent(BaseModel):
    ingredient: str = Field(description="Ingredient name")
    amount: Optional[float] = Field(default=None, description="Amount per serving as a number")
    unit: Optional[str] = Field(default=None, description="Unit of measurement (e.g. 'mg', 'g', 'mcg', 'IU')")


# ---------------------------------------------------------------------------
# PAYMENT_PROOF payload
# ---------------------------------------------------------------------------


class PaymentProofPayload(BaseModel):
    date: Optional[str] = Field(default=None, description="Payment date in YYYY-MM-DD format")
    payer: Optional[str] = Field(default=None, description="Name or account of the entity making the payment")
    payee: Optional[str] = Field(default=None, description="Name or account of the entity receiving the payment")
    amount: Optional[float] = Field(default=None, description="Payment amount as a number")
    confirmation_number: Optional[str] = Field(default=None, description="Payment confirmation or reference number")
    payment_method: Optional[str] = Field(default=None, description="Payment method or bank name (e.g. 'Zelle', 'ACH', 'Wire Transfer')")


# ---------------------------------------------------------------------------
# COA payload
# ---------------------------------------------------------------------------


class COATestResult(BaseModel):
    test_name: Optional[str] = Field(default=None, description="Name of the test (e.g. 'Moisture Content')")
    method: Optional[str] = Field(default=None, description="Test method (e.g. 'USP <921>')")
    specification: Optional[str] = Field(default=None, description="Specification or acceptance criteria")
    result: Optional[str] = Field(default=None, description="Actual test result value")
    pass_fail_status: Optional[str] = Field(default=None, description="Pass or Fail status")


class COAPayload(BaseModel):
    date: Optional[str] = Field(default=None, description="Document date in YYYY-MM-DD format")
    manufacturer_name: Optional[str] = Field(default=None, description="Manufacturer or testing lab name")
    product_name: Optional[str] = Field(default=None, description="Product name")
    lot_number: Optional[str] = Field(default=None, description="Lot or batch number")
    expiration_date: Optional[str] = Field(default=None, description="Expiration date in YYYY-MM-DD format")
    test_results: list[COATestResult] = Field(
        default_factory=list, description="Array of test results from the COA table"
    )


# ---------------------------------------------------------------------------
# Invoice payload
# ---------------------------------------------------------------------------


class InvoiceLineItem(BaseModel):
    description: Optional[str] = Field(default=None, description="Line item description")
    quantity: Optional[float] = Field(default=None, description="Quantity ordered as a number")
    quantity_unit: Optional[str] = Field(default=None, description="Unit for quantity (e.g. 'bottle', 'label', 'kg', 'capsule')")
    unit_price: Optional[float] = Field(default=None, description="Unit price")
    total: Optional[float] = Field(default=None, description="Line item total")


class InvoicePayload(BaseModel):
    date: Optional[str] = Field(default=None, description="Invoice date in YYYY-MM-DD format")
    vendor_name: Optional[str] = Field(default=None, description="Vendor or supplier name")
    invoice_number: Optional[str] = Field(default=None, description="Invoice number")
    po_number: Optional[str] = Field(default=None, description="Purchase order number")
    line_items: list[InvoiceLineItem] = Field(
        default_factory=list, description="Individual line items on the invoice"
    )
    grand_total: Optional[float] = Field(default=None, description="Total invoice amount")
    deposit_number: Optional[int] = Field(
        default=None, description="Deposit sequence number (e.g. 1 for 'Deposit 1', 2 for 'Deposit 2')"
    )
    deposit_percentage: Optional[float] = Field(
        default=None, description="Fraction of total being invoiced (e.g. 0.5 for a 50% deposit)"
    )
    due_amount: Optional[float] = Field(
        default=None, description="Remaining balance due after this payment"
    )


# ---------------------------------------------------------------------------
# Quote payload
# ---------------------------------------------------------------------------


class QuoteLineItem(BaseModel):
    description: Optional[str] = Field(default=None, description="Item description")
    quantity: Optional[float] = Field(default=None, description="Quantity as a number")
    quantity_unit: Optional[str] = Field(default=None, description="Unit for quantity (e.g. 'bottle', 'label', 'kg')")
    unit_price: Optional[float] = Field(default=None, description="Unit price")
    total: Optional[float] = Field(default=None, description="Line item total")


class QuotePayload(BaseModel):
    date: Optional[str] = Field(default=None, description="Quote date in YYYY-MM-DD format")
    vendor_name: Optional[str] = Field(default=None, description="Vendor name")
    quote_number: Optional[str] = Field(default=None, description="Quote or RFQ number")
    line_items: list[QuoteLineItem] = Field(
        default_factory=list, description="Quoted line items"
    )
    total: Optional[float] = Field(default=None, description="Total quoted amount")


# ---------------------------------------------------------------------------
# PRODUCT_SPEC_SHEET payload
# ---------------------------------------------------------------------------


class ProductSpecSheetPayload(BaseModel):
    date: Optional[str] = Field(default=None, description="Document date in YYYY-MM-DD format")
    manufacturer_name: Optional[str] = Field(default=None, description="Manufacturer or company name")
    product_name: Optional[str] = Field(default=None, description="Product name")
    product_code: Optional[str] = Field(default=None, description="Product code or SKU")
    product_description: Optional[str] = Field(default=None, description="Product description")
    product_formula: list[FormulaComponent] = Field(
        default_factory=list, description="Active ingredients with their amounts and units"
    )
    capsule_type: Optional[str] = Field(
        default=None, description="Capsule or tablet form (e.g. 'Size 00 Vegetable Capsule', 'Hard Gelatin Capsule')"
    )
    excipients: list[str] = Field(
        default_factory=list,
        description="Non-active ingredients listed without amounts (e.g. ['Magnesium Stearate', 'Silicon Dioxide'])"
    )
    count: Optional[int] = Field(default=None, description="Number of units per container")
    count_unit: Optional[str] = Field(
        default=None, description="Unit type for count (e.g. 'capsule', 'tablet', 'softgel', 'gummy')"
    )
    servings: Optional[int] = Field(default=None, description="Number of servings per container")
    includes_packaging: bool = Field(
        default=False,
        description="True if this document also specifies packaging components (bottle, label, etc.)"
    )


# ---------------------------------------------------------------------------
# PACKAGING_SPEC_SHEET payload
# ---------------------------------------------------------------------------


class ExtraPackagingComponent(BaseModel):
    component_name: str = Field(description="Name of the non-standard packaging component")
    description: Optional[str] = Field(default=None, description="Component specification or description")


class PackagingComponents(BaseModel):
    """Normalized packaging components. Known components have dedicated fields;
    anything else goes in extras."""

    container: Optional[str] = Field(default=None, description="Bottle or container specification")
    closure: Optional[str] = Field(default=None, description="Cap or closure specification")
    filler: Optional[str] = Field(default=None, description="Packing material inside the bottle (e.g. rayon packing)")
    desiccant: Optional[str] = Field(default=None, description="Desiccant or moisture absorber specification")
    neck_band: Optional[str] = Field(
        default=None, description="Outer safety seal, neck band, or shrink band specification"
    )
    label: Optional[str] = Field(default=None, description="Label description (size, barcode, FNSKU)")
    master_shipper: Optional[str] = Field(default=None, description="Outer carton or master shipper specification")
    inner_shipper: Optional[str] = Field(
        default=None, description="Inner shipper, divider, or inner box specification"
    )
    pallet: Optional[str] = Field(default=None, description="Pallet configuration specification")
    extras: list[ExtraPackagingComponent] = Field(
        default_factory=list, description="Components not covered by standard fields above"
    )


class LabelSpecs(BaseModel):
    """Normalized label roll specifications. Known fields have dedicated slots;
    anything else goes in extras."""

    label_size: Optional[str] = Field(
        default=None, description="Label dimensions (e.g. '3\" x 8\"' or '70mm x 178mm')"
    )
    barcode: Optional[str] = Field(default=None, description="Barcode or FNSKU printed on the label")
    core_size: Optional[str] = Field(default=None, description="Inner core diameter of the label roll")
    max_outer_diameter: Optional[str] = Field(default=None, description="Maximum outer diameter of the label roll")
    wind_position: Optional[str] = Field(
        default=None, description="Rewind/wind direction (e.g. 'left to right')"
    )
    extras: list[str] = Field(
        default_factory=list, description="Additional label specifications not covered by standard fields"
    )


class PackagingSpecSheetPayload(BaseModel):
    date: Optional[str] = Field(default=None, description="Document date in YYYY-MM-DD format")
    manufacturer_name: Optional[str] = Field(default=None, description="Manufacturer or company name")
    product_name: Optional[str] = Field(default=None, description="Product name")
    product_code: Optional[str] = Field(default=None, description="Product code or SKU")
    product_description: Optional[str] = Field(default=None, description="Product description")
    count: Optional[int] = Field(default=None, description="Number of units per container")
    count_unit: Optional[str] = Field(
        default=None, description="Unit type (e.g. 'capsule', 'tablet', 'softgel')"
    )
    servings: Optional[int] = Field(default=None, description="Number of servings per container")
    packaging_components: PackagingComponents = Field(
        default_factory=PackagingComponents,
        description="Normalized packaging components"
    )
    label_specs: LabelSpecs = Field(
        default_factory=LabelSpecs,
        description="Label roll specification details"
    )


# ---------------------------------------------------------------------------
# LABEL payload
# ---------------------------------------------------------------------------


class SupplementsFact(BaseModel):
    ingredient: Optional[str] = Field(default=None, description="Ingredient name")
    amount_per_serving: Optional[str] = Field(default=None, description="Amount per serving with unit")
    daily_value_percent: Optional[str] = Field(default=None, description="Percent daily value (%DV)")


class CompanyInfo(BaseModel):
    name: Optional[str] = Field(default=None, description="Company name")
    address: Optional[str] = Field(default=None, description="Full address")
    email: Optional[str] = Field(default=None, description="Contact email")
    phone: Optional[str] = Field(default=None, description="Contact phone")


class LabelPayload(BaseModel):
    brand: Optional[str] = Field(default=None, description="Brand name")
    product_name: Optional[str] = Field(default=None, description="Product name")
    barcode: Optional[str] = Field(default=None, description="Barcode or UPC")
    version: Optional[str] = Field(default=None, description="Label version or revision")
    count: Optional[int] = Field(default=None, description="Number of units per container")
    count_unit: Optional[str] = Field(
        default=None, description="Unit type (e.g. 'capsule', 'tablet', 'softgel', 'gummy')"
    )
    servings: Optional[int] = Field(default=None, description="Number of servings per container")
    supplements_fact_panel: list[SupplementsFact] = Field(
        default_factory=list, description="Supplement facts panel rows"
    )
    other_ingredients: Optional[str] = Field(
        default=None, description="Other ingredients list as printed on label"
    )
    allergens: Optional[str] = Field(default=None, description="Allergen statement")
    company: Optional[CompanyInfo] = Field(default=None, description="Company contact information")
    suggested_use: Optional[str] = Field(default=None, description="Suggested use / directions")
    marketing_text: Optional[str] = Field(default=None, description="Marketing or product description text")


# ---------------------------------------------------------------------------
# LABEL_PROOF payload
# ---------------------------------------------------------------------------


class LabelProofPayload(BaseModel):
    """Label proof sent by the printer for review before production.

    Combines label content fields with technical print specifications.
    """

    date: Optional[str] = Field(default=None, description="Proof date in YYYY-MM-DD format")
    manufacturer_name: Optional[str] = Field(
        default=None, description="Name of the printing company producing the proof"
    )
    brand: Optional[str] = Field(default=None, description="Brand name on the label")
    product_name: Optional[str] = Field(default=None, description="Product name")
    product_code: Optional[str] = Field(default=None, description="Product code or SKU")
    barcode: Optional[str] = Field(default=None, description="Barcode or FNSKU")
    version: Optional[str] = Field(default=None, description="Label version or revision")
    count: Optional[int] = Field(default=None, description="Number of units per container")
    count_unit: Optional[str] = Field(
        default=None, description="Unit type (e.g. 'capsule', 'tablet', 'softgel')"
    )
    servings: Optional[int] = Field(default=None, description="Number of servings per container")
    # Technical print specifications
    label_size: Optional[str] = Field(
        default=None, description="Label dimensions (e.g. '2.75\" x 7\"' or '70mm x 178mm')"
    )
    corner_radius: Optional[str] = Field(default=None, description="Corner radius (e.g. '0.125 in.')")
    substrate: Optional[str] = Field(
        default=None, description="Label material/substrate (e.g. '2M Metallized BOPP/S7000ER/1.2 Mil PET')"
    )
    inks: Optional[str] = Field(
        default=None, description="Ink colors used (e.g. 'Cyan, Magenta, Yellow, Black, Premium White')"
    )
    core_size: Optional[str] = Field(default=None, description="Inner core diameter of the label roll")
    max_outer_diameter: Optional[str] = Field(default=None, description="Maximum outer diameter of the label roll")
    wind_position: Optional[str] = Field(default=None, description="Wind direction/position")
    # Label content
    supplements_fact_panel: list[SupplementsFact] = Field(
        default_factory=list, description="Supplement facts panel rows"
    )
    other_ingredients: Optional[str] = Field(default=None, description="Other ingredients list")
    allergens: Optional[str] = Field(default=None, description="Allergen statement")
    company: Optional[CompanyInfo] = Field(default=None, description="Company contact information on the label")
    suggested_use: Optional[str] = Field(default=None, description="Suggested use / directions")
    marketing_text: Optional[str] = Field(default=None, description="Marketing or product description text")


# ---------------------------------------------------------------------------
# Top-level extraction envelope
# ---------------------------------------------------------------------------

PayloadUnion = Union[
    PaymentProofPayload,
    COAPayload,
    InvoicePayload,
    QuotePayload,
    PackagingSpecSheetPayload,
    ProductSpecSheetPayload,
    LabelProofPayload,
    LabelPayload,
]


class ExtractionResult(BaseModel):
    document_type: DocumentType = Field(description="Classified document type")
    confidence: float = Field(
        description="Classification confidence score from 0.0 to 1.0",
        ge=0.0,
        le=1.0,
    )
    extracted_date: Optional[str] = Field(
        default=None, description="Extraction date in YYYY-MM-DD format"
    )
    payload: Optional[PayloadUnion] = Field(  # type: ignore[valid-type]
        default=None, description="Extracted document data (schema varies by document_type)"
    )
    raw_text_fallback: Optional[str] = Field(
        default=None,
        description="Raw text extraction used when structured extraction fails or document_type is UNKNOWN",
    )
