"""Product specification sheet schema."""

from __future__ import annotations

from typing import Optional

from pydantic import Field

from ._packaging_spec import PackagingComponents
from ._shared import FormulaComponent, SpecSheetHeader


class ProductSpecSheetPayload(SpecSheetHeader):
    product_formula: list[FormulaComponent] = Field(
        default_factory=list,
        description="Active ingredients with their amounts and units",
    )
    capsule_type: Optional[str] = Field(
        default=None,
        description="Capsule or tablet form (e.g. 'Size 00 Vegetable Capsule', 'Hard Gelatin Capsule')",
    )
    excipients: list[str] = Field(
        default_factory=list,
        description="Non-active ingredients listed without amounts. NCL specs typically list natural-source flow agents and the capsule shell (e.g. ['Hypromellose (Veggie Capsule)', 'Rice Flour', 'L-Leucine']). Extract whatever is printed verbatim.",
    )
    packaging_components: Optional[PackagingComponents] = Field(
        default=None,
        description="Full packaging specification when the manufacturer embeds packaging details (bottle, closure, label, etc.) alongside the product formula on the same document. Leave null when the document only specifies the product.",
    )
