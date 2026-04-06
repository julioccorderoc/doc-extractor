"""Pydantic v2 models for document extraction schemas.

The PRD (docs/PRD.md) is the source of truth for field definitions.
These models generate JSON Schema via .model_json_schema() which is passed
to the Gemini API's response_json_schema parameter.
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
    UNKNOWN = "UNKNOWN"


# --- Shared sub-models ---


class FormulaComponent(BaseModel):
    ingredient: str = Field(description="Ingredient name")
    amount: Optional[str] = Field(default=None, description="Amount per serving")
    unit: Optional[str] = Field(default=None, description="Unit of measurement")


# --- COA payload ---


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


# --- Invoice payload ---


class InvoiceLineItem(BaseModel):
    description: Optional[str] = Field(default=None, description="Line item description")
    quantity: Optional[str] = Field(default=None, description="Quantity ordered")
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


# --- Quote payload ---


class QuoteLineItem(BaseModel):
    description: Optional[str] = Field(default=None, description="Item description")
    quantity: Optional[str] = Field(default=None, description="Quantity")
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


# --- PRODUCT_SPEC_SHEET payload (EPIC-001) ---


class ProductSpecSheetPayload(BaseModel):
    date: Optional[str] = Field(default=None, description="Document date in YYYY-MM-DD format")
    manufacturer_name: Optional[str] = Field(default=None, description="Manufacturer or company name")
    product_name: Optional[str] = Field(default=None, description="Product name")
    product_code: Optional[str] = Field(default=None, description="Product code or SKU")
    product_description: Optional[str] = Field(default=None, description="Product description")
    product_formula: list[FormulaComponent] = Field(
        default_factory=list, description="Product formula / ingredient list"
    )
    count: Optional[str] = Field(default=None, description="Count (capsules, gummies, pellets, etc.)")
    servings: Optional[str] = Field(default=None, description="Number of servings")


# --- PACKAGING_SPEC_SHEET payload ---


class PackagingComponent(BaseModel):
    component_name: Optional[str] = Field(default=None, description="Component name (e.g. 'bottle', 'cap')")
    description: Optional[str] = Field(default=None, description="Component description or specification")


class PackagingSpecSheetPayload(ProductSpecSheetPayload):
    """Extends ProductSpecSheetPayload with packaging-specific fields.

    IMPORTANT: Must appear before ProductSpecSheetPayload in PayloadUnion.
    Packaging is a superset of Product; Pydantic tries Union members left-to-right
    and stops at the first successful validation. If ProductSpecSheetPayload came
    first, packaging-specific fields would be silently dropped.
    """

    packaging_components: list[PackagingComponent] = Field(
        default_factory=list, description="List of packaging components"
    )
    label_specs: list[str] = Field(
        default_factory=list, description="Label specifications (size, material, print specs)"
    )
    closure_specs: list[str] = Field(
        default_factory=list, description="Closure/cap specifications"
    )
    bottle_specs: list[str] = Field(
        default_factory=list, description="Bottle/container specifications"
    )
    carton_specs: list[str] = Field(
        default_factory=list, description="Carton/outer box specifications"
    )
    pallet_specs: list[str] = Field(
        default_factory=list, description="Pallet configuration specifications"
    )


# --- Label payload ---


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
    count: Optional[str] = Field(default=None, description="Count (capsules, gummies, etc.)")
    servings: Optional[str] = Field(default=None, description="Number of servings")
    supplements_fact_panel: list[SupplementsFact] = Field(
        default_factory=list, description="Supplement facts panel rows"
    )
    other_ingredients: Optional[str] = Field(default=None, description="Other ingredients list")
    allergens: Optional[str] = Field(default=None, description="Allergen statement")
    company: Optional[CompanyInfo] = Field(default=None, description="Company contact information")
    suggested_use: Optional[str] = Field(default=None, description="Suggested use / directions")
    marketing_text: Optional[str] = Field(default=None, description="Marketing or product description text")


# --- Top-level extraction envelope ---

PayloadUnion = Union[
    COAPayload,
    InvoicePayload,
    QuotePayload,
    PackagingSpecSheetPayload,  # Must come before ProductSpecSheetPayload (superset)
    ProductSpecSheetPayload,
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
