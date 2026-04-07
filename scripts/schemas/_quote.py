"""Quote schema."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from ._shared import CompanyInfo


class PricingTier(BaseModel):
    quantity: Optional[float] = Field(
        default=None, description="Quantity as a number for this pricing tier"
    )
    quantity_unit: Optional[str] = Field(
        default=None,
        description="Unit for quantity (e.g. 'bottle', 'label', 'kg', 'capsule')",
    )
    unit_price: Optional[float] = Field(
        default=None, description="Unit price at this quantity tier"
    )
    total_price: Optional[float] = Field(
        default=None, description="Total price for this tier (if calculated/provided)"
    )


class QuoteTechnicalDetail(BaseModel):
    specification_name: Optional[str] = Field(
        default=None,
        description="Name of the technical specification or property (e.g. 'Bottle Size', 'Capsule Size', 'Material')",
    )
    specification_value: Optional[str] = Field(
        default=None,
        description="Value of the specification (e.g. '120cc', 'Size 0', 'PET')",
    )


class QuotedItem(BaseModel):
    vendor_product_id: Optional[str] = Field(
        default=None, description="The internal ID or SKU of the item for the vendor/manufacturer"
    )
    buyer_product_id: Optional[str] = Field(
        default=None, description="The ID or SKU of the item from the buyer's perspective"
    )
    description: Optional[str] = Field(
        default=None, description="Main product or item being quoted"
    )
    technical_details: list[QuoteTechnicalDetail] = Field(
        default_factory=list,
        description="List of technical specifications, dimensions, formula details, or product characteristics",
    )
    pricing_tiers: list[PricingTier] = Field(
        default_factory=list, description="Volume-based pricing tiers for this item"
    )


class AdditionalFee(BaseModel):
    description: Optional[str] = Field(
        default=None,
        description="Description of the fee (e.g. 'Tooling fee', 'Setup', 'Freight')",
    )
    amount: Optional[float] = Field(default=None, description="Amount of the fee")


class QuotePayload(BaseModel):
    date: Optional[str] = Field(
        default=None, description="Quote date in YYYY-MM-DD format"
    )
    vendor_name: Optional[str] = Field(default=None, description="Vendor name")
    quote_number: Optional[str] = Field(default=None, description="Quote or RFQ number")
    bill_to: Optional[CompanyInfo] = Field(
        default=None, description="Name and address of the company requesting the quote"
    )
    ship_to: Optional[CompanyInfo] = Field(
        default=None, description="Name and address where goods would be shipped"
    )
    quoted_items: list[QuotedItem] = Field(
        default_factory=list,
        description="Products being quoted with tiered pricing and technical details",
    )
    additional_fees: list[AdditionalFee] = Field(
        default_factory=list,
        description="Extra line items like setup fees, tooling, or freight",
    )
    grand_total: Optional[float] = Field(
        default=None,
        description="Total quoted amount, if the quote resolves to a single fixed price",
    )
