"""Label order acknowledgement schema."""

from __future__ import annotations

from typing import Optional

from pydantic import Field

from ._invoice import InvoiceLineItem
from ._shared import CommercialDocHeader, TechnicalLabelSpecs


class LabelOrderAckLineItem(InvoiceLineItem):
    label_specs: Optional[TechnicalLabelSpecs] = Field(
        default=None, description="Technical printing specifications for the label"
    )


class LabelOrderAckPayload(CommercialDocHeader):
    customer_id: Optional[str] = Field(
        default=None,
        description="Buyer's account number in the vendor's system (often labeled 'Customer #', 'Account #', or 'Ship-To ID')",
    )
    delivery_date: Optional[str] = Field(
        default=None, description="Estimated delivery or ship date in YYYY-MM-DD format"
    )
    line_items: list[LabelOrderAckLineItem] = Field(
        default_factory=list, description="Labels ordered in this acknowledgement"
    )
