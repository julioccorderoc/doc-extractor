"""Packing list schema — the generic manifest enclosed with a shipment.

Deliberately thin, and deliberately separate from PACKOUT_SHEET
(`_packout.py`). A packing list answers a commercial question: what shipped,
how much of it, from whom, to whom. A packout sheet answers a physical one:
which lot filled which case, how many units per case, what the pallets weigh.

Keeping them apart is what stops a freight packing list from being extracted
into case/pallet fields it does not have — which would report empty geometry as
if the manufacturer had omitted it.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from ._shared import CompanyInfo, ProductIdentifiers


class PackingListLineItem(ProductIdentifiers):
    description: Optional[str] = Field(
        default=None, description="Line item description as printed"
    )
    lot_code: Optional[str] = Field(
        default=None, description="Lot or batch code for this line, when printed"
    )
    quantity: Optional[float] = Field(
        default=None, description="Quantity shipped for this line as a number"
    )
    quantity_unit: Optional[str] = Field(
        default=None,
        description="Unit for quantity (e.g. 'bottle', 'case', 'carton', 'each')",
    )
    carton_count: Optional[int] = Field(
        default=None,
        description="Cartons/cases this line covers, when the document states it separately",
    )


class PackingListPayload(BaseModel):
    """Root schema for a shipment packing list / manifest."""

    date: Optional[str] = Field(
        default=None, description="Document date in YYYY-MM-DD format"
    )
    doc_number: Optional[str] = Field(
        default=None, description="Packing list or manifest number"
    )
    po_number: Optional[str] = Field(
        default=None, description="Purchase order number referenced on the document"
    )
    shipment_ref: Optional[str] = Field(
        default=None,
        description="Carrier tracking, BOL, container, or shipment reference number",
    )
    carrier: Optional[str] = Field(default=None, description="Carrier or freight forwarder name")
    ship_from: Optional[CompanyInfo] = Field(
        default=None, description="Origin party name and address"
    )
    ship_to: Optional[CompanyInfo] = Field(
        default=None, description="Destination party name and address"
    )
    line_items: list[PackingListLineItem] = Field(
        default_factory=list, description="Every line on the manifest. Do not skip rows."
    )
    total_cartons: Optional[int] = Field(
        default=None, description="Total cartons/cases as stated on the document"
    )
    total_weight_lbs: Optional[float] = Field(
        default=None, description="Total shipment weight in pounds as stated"
    )
    notes: Optional[str] = Field(
        default=None, description="Free-text remarks that do not fit another field"
    )
