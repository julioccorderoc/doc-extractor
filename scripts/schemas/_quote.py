"""Quote schema."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class QuoteLineItem(BaseModel):
    description: Optional[str] = Field(default=None, description="Item description")
    quantity: Optional[float] = Field(default=None, description="Quantity as a number")
    quantity_unit: Optional[str] = Field(
        default=None,
        description="Unit for quantity (e.g. 'bottle', 'label', 'kg')",
    )
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
