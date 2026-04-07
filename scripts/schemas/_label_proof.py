"""Label proof schema."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from ._shared import CompanyInfo, SupplementsFact


class LabelProofPayload(BaseModel):
    """Label proof sent by the printer for review before production.

    Combines label content fields with technical print specifications.
    """

    date: Optional[str] = Field(
        default=None, description="Proof date in YYYY-MM-DD format"
    )
    manufacturer_name: Optional[str] = Field(
        default=None, description="Name of the printing company producing the proof"
    )
    brand: Optional[str] = Field(default=None, description="Brand name on the label")
    product_name: Optional[str] = Field(default=None, description="Product name")
    vendor_product_id: Optional[str] = Field(
        default=None, description="Product code or SKU used by the printer/manufacturer"
    )
    buyer_product_id: Optional[str] = Field(
        default=None, description="Product code or SKU used by the buyer"
    )
    barcode: Optional[str] = Field(default=None, description="Barcode or FNSKU")
    version: Optional[str] = Field(
        default=None, description="Label version or revision"
    )
    count: Optional[int] = Field(
        default=None, description="Number of units per container"
    )
    count_unit: Optional[str] = Field(
        default=None, description="Unit type (e.g. 'capsule', 'tablet', 'softgel')"
    )
    servings: Optional[int] = Field(
        default=None, description="Number of servings per container"
    )
    # Technical print specifications
    label_size: Optional[str] = Field(
        default=None,
        description="Label dimensions (e.g. '2.75\" x 7\"' or '70mm x 178mm')",
    )
    corner_radius: Optional[str] = Field(
        default=None, description="Corner radius (e.g. '0.125 in.')"
    )
    substrate: Optional[str] = Field(
        default=None,
        description="Label material/substrate (e.g. '2M Metallized BOPP/S7000ER/1.2 Mil PET')",
    )
    inks: Optional[str] = Field(
        default=None,
        description="Ink colors used (e.g. 'Cyan, Magenta, Yellow, Black, Premium White')",
    )
    core_size: Optional[str] = Field(
        default=None, description="Inner core diameter of the label roll"
    )
    max_outer_diameter: Optional[str] = Field(
        default=None, description="Maximum outer diameter of the label roll"
    )
    wind_position: Optional[str] = Field(
        default=None, description="Wind direction/position"
    )
    # Label content
    supplements_fact_panel: list[SupplementsFact] = Field(
        default_factory=list, description="Supplement facts panel rows"
    )
    other_ingredients: Optional[str] = Field(
        default=None, description="Other ingredients list"
    )
    allergens: Optional[str] = Field(default=None, description="Allergen statement")
    company: Optional[CompanyInfo] = Field(
        default=None, description="Company contact information on the label"
    )
    suggested_use: Optional[str] = Field(
        default=None, description="Suggested use / directions"
    )
    marketing_text: Optional[str] = Field(
        default=None, description="Marketing or product description text"
    )
