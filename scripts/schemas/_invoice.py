"""Invoice schema."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from ._shared import CompanyInfo


class InvoiceLineItem(BaseModel):
    vendor_product_id: Optional[str] = Field(
        default=None,
        description="The internal ID or SKU of the item for the vendor/manufacturer",
    )
    buyer_product_id: Optional[str] = Field(
        default=None,
        description="The ID or SKU of the item from the buyer's perspective",
    )
    description: Optional[str] = Field(
        default=None, description="Line item description"
    )
    quantity: Optional[float] = Field(
        default=None, description="Quantity ordered as a number"
    )
    quantity_unit: Optional[str] = Field(
        default=None,
        description="Unit for quantity (e.g. 'bottle', 'label', 'kg', 'capsule')",
    )
    unit_price: Optional[float] = Field(default=None, description="Unit price")
    total: Optional[float] = Field(default=None, description="Line item total")


class InvoicePayload(BaseModel):
    date: Optional[str] = Field(
        default=None, description="Invoice date in YYYY-MM-DD format"
    )
    vendor_name: Optional[str] = Field(
        default=None, description="Vendor or supplier name"
    )
    invoice_number: Optional[str] = Field(default=None, description="Invoice number")
    po_number: Optional[str] = Field(default=None, description="Purchase order number")
    bill_to: Optional[CompanyInfo] = Field(
        default=None, description="Name and address of the company being billed"
    )
    ship_to: Optional[CompanyInfo] = Field(
        default=None, description="Name and address of the company being shipped to"
    )
    line_items: list[InvoiceLineItem] = Field(
        default_factory=list, description="Individual line items on the invoice"
    )
    shipping_handling: Optional[float] = Field(
        default=None, description="Shipping, handling, or freight charges"
    )
    tax_amount: Optional[float] = Field(default=None, description="Tax amount")
    grand_total: Optional[float] = Field(
        default=None, description="Total invoice amount"
    )
    deposit_number: Optional[int] = Field(
        default=None,
        description="Deposit sequence number (e.g. 1 for 'Deposit 1', 2 for 'Deposit 2')",
    )
    deposit_percentage: Optional[float] = Field(
        default=None,
        description="Fraction of total being invoiced (e.g. 0.5 for a 50% deposit)",
    )
    due_amount: Optional[float] = Field(
        default=None,
        description="Remaining balance due after this payment",
    )
