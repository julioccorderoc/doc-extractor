from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from ._shared import CompanyInfo, TechnicalLabelSpecs


class LabelOrderAckLineItem(BaseModel):
    vendor_product_id: Optional[str] = Field(
        default=None,
        description="The internal ID of the label for the printer/manufacturer/vendor",
    )
    buyer_product_id: Optional[str] = Field(
        default=None, description="The ID of the item from the buyer's perspective"
    )
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
    label_specs: Optional[TechnicalLabelSpecs] = Field(
        default=None, description="Technical printing specifications for the label"
    )


class LabelOrderAckPayload(BaseModel):
    date: Optional[str] = Field(
        default=None, description="Document date in YYYY-MM-DD format"
    )
    vendor_name: Optional[str] = Field(default=None, description="Label printer name")
    doc_number: Optional[str] = Field(
        default=None, description="Vendor's internal confirmation/order number"
    )
    po_number: Optional[str] = Field(
        default=None, description="Buyer's PO number being acknowledged"
    )
    customer_id: Optional[str] = Field(
        default=None, description="The ID of the buyer in the manufacturer's system"
    )
    bill_to: Optional[CompanyInfo] = Field(
        default=None, description="Name and address of the company being billed"
    )
    ship_to: Optional[CompanyInfo] = Field(
        default=None, description="Name and address of the company being shipped to"
    )
    delivery_date: Optional[str] = Field(
        default=None, description="Estimated delivery or ship date in YYYY-MM-DD format"
    )
    line_items: list[LabelOrderAckLineItem] = Field(
        default_factory=list, description="Labels ordered in this acknowledgement"
    )
    shipping_handling: Optional[float] = Field(
        default=None, description="Cost of shipping and handling"
    )
    grand_total: Optional[float] = Field(default=None, description="Total order amount")
