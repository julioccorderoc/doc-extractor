from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class LabelOrderAckLineItem(BaseModel):
    description: Optional[str] = Field(
        default=None, description="Line item description"
    )
    quantity: Optional[float] = Field(
        default=None, description="Quantity ordered as a number"
    )
    quantity_unit: Optional[str] = Field(
        default=None, description="Unit for quantity (e.g. 'label', 'roll')"
    )
    unit_price: Optional[float] = Field(default=None, description="Unit price")
    total: Optional[float] = Field(default=None, description="Line item total")
    label_size: Optional[str] = Field(
        default=None, description="Label size or dimensions"
    )
    substrate: Optional[str] = Field(default=None, description="Material or substrate")
    inks: Optional[str] = Field(
        default=None, description="Ink colors or front printing specifications"
    )


class LabelOrderAckPayload(BaseModel):
    date: Optional[str] = Field(
        default=None, description="Document date in YYYY-MM-DD format"
    )
    vendor_name: Optional[str] = Field(default=None, description="Label printer name")
    acknowledgement_number: Optional[str] = Field(
        default=None, description="Vendor's internal confirmation/order number"
    )
    po_number: Optional[str] = Field(
        default=None, description="Buyer's PO number being acknowledged"
    )
    delivery_date: Optional[str] = Field(
        default=None, description="Estimated delivery or ship date in YYYY-MM-DD format"
    )
    line_items: list[LabelOrderAckLineItem] = Field(
        default_factory=list, description="Labels ordered in this acknowledgement"
    )
    grand_total: Optional[float] = Field(default=None, description="Total order amount")
