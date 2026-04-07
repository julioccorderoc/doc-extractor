"""Product specification sheet schema."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from ._shared import FormulaComponent


class ProductSpecSheetPayload(BaseModel):
    date: Optional[str] = Field(default=None, description="Document date in YYYY-MM-DD format")
    manufacturer_name: Optional[str] = Field(default=None, description="Manufacturer or company name")
    product_name: Optional[str] = Field(default=None, description="Product name")
    product_code: Optional[str] = Field(default=None, description="Product code or SKU")
    product_description: Optional[str] = Field(default=None, description="Product description")
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
        description="Non-active ingredients listed without amounts (e.g. ['Magnesium Stearate', 'Silicon Dioxide'])",
    )
    count: Optional[int] = Field(default=None, description="Number of units per container")
    count_unit: Optional[str] = Field(
        default=None,
        description="Unit type for count (e.g. 'capsule', 'tablet', 'softgel', 'gummy')",
    )
    servings: Optional[int] = Field(default=None, description="Number of servings per container")
    includes_packaging: bool = Field(
        default=False,
        description="True if this document also specifies packaging components (bottle, label, etc.)",
    )
