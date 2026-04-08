"""Label schema."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from ._shared import CompanyInfo, SupplementsFact


class LabelPayload(BaseModel):
    brand: Optional[str] = Field(default=None, description="Brand name")
    product_name: Optional[str] = Field(default=None, description="Product name")
    barcode: Optional[str] = Field(default=None, description="Barcode or UPC")
    version: Optional[str] = Field(
        default=None,
        description="Label version or revision. Must always be prefixed with 'FNSKU ' or 'REV ' (e.g. 'REV V.3' or 'FNSKU V.3').",
    )
    count: Optional[int] = Field(
        default=None, description="Number of units per container"
    )
    count_unit: Optional[str] = Field(
        default=None,
        description="Unit type (e.g. 'capsule', 'tablet', 'softgel', 'gummy')",
    )
    servings: Optional[int] = Field(
        default=None, description="Number of servings per container"
    )
    supplements_fact_panel: list[SupplementsFact] = Field(
        default_factory=list, description="Supplement facts panel rows"
    )
    other_ingredients: Optional[str] = Field(
        default=None, description="Other ingredients list as printed on label"
    )
    allergens: Optional[str] = Field(default=None, description="Allergen statement")
    company: Optional[CompanyInfo] = Field(
        default=None, description="Company contact information"
    )
    suggested_use: Optional[str] = Field(
        default=None, description="Suggested use / directions"
    )
    marketing_text: Optional[str] = Field(
        default=None, description="Marketing or product description text"
    )
