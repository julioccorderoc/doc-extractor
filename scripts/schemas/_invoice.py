"""Invoice schema."""

from __future__ import annotations

from typing import Optional

from pydantic import Field

from ._shared import CommercialDocHeader, ProductIdentifiers


class InvoiceLineItem(ProductIdentifiers):
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


class InvoicePayload(CommercialDocHeader):
    line_items: list[InvoiceLineItem] = Field(
        default_factory=list, description="Individual line items on the invoice"
    )
    tax_amount: Optional[float] = Field(default=None, description="Tax amount")
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
