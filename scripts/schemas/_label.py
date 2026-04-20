"""Label schema."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from ._shared import CompanyInfo, SupplementsFact


class LabelPayload(BaseModel):
    brand: str = Field(description="Brand name")
    product_name: str = Field(description="Product name")
    barcode_text: Optional[str] = Field(
        default=None,
        description="Human-readable digits printed beneath the barcode (UPC/EAN/FNSKU text), NOT the scanned barcode image",
    )
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
    serving_size: Optional[int] = Field(
        default=None,
        description="Units per serving (e.g. 2 means '2 capsules per serving')",
    )
    servings: Optional[int] = Field(
        default=None, description="Number of servings per container"
    )
    supplements_fact_panel: list[SupplementsFact] = Field(
        default_factory=list, description="Supplement facts panel rows"
    )
    other_ingredients: Optional[str] = Field(
        default=None,
        description="Verbatim 'Other Ingredients' line as printed on the label, including capsule material and flow agents. Use this for fidelity; capsule_material and flow_agents below provide the structured breakdown.",
    )
    capsule_material: Optional[str] = Field(
        default=None,
        description="Capsule shell composition extracted from other_ingredients (e.g. 'Hypromellose (Veggie Capsule)', 'HPMC', 'Bovine Gelatin'). Singular — one capsule per product. Null for non-encapsulated forms (tablets, gummies, powders).",
    )
    flow_agents: list[str] = Field(
        default_factory=list,
        description="Flow agents / anti-caking agents / fillers extracted from other_ingredients. Natural Cure Labs uses natural-source flow agents — typical entries: 'Rice Flour', 'Rice Bran Extract', 'Rice Extract', 'L-Leucine', 'Ascorbyl Palmitate'. Excludes the capsule material. Extract whatever is printed verbatim, even if it falls outside the typical list.",
    )
    allergens: Optional[str] = Field(default=None, description="Allergen statement")
    certifications: list[str] = Field(
        default_factory=list,
        description="Seals/badges printed on the label (e.g. 'GMP', 'Laboratory Tested', 'Made in U.S.A.', 'Non-GMO', 'Vegan')",
    )
    product_claims: list[str] = Field(
        default_factory=list,
        description="Discrete marketing/benefit claims printed on the label (e.g. 'Immune System Support', 'No artificial colors', 'Gluten free'). May overlap with marketing_text.",
    )
    company: Optional[CompanyInfo] = Field(
        default=None, description="Company contact information"
    )
    suggested_use: Optional[str] = Field(
        default=None, description="Suggested use / directions"
    )
    marketing_text: Optional[str] = Field(
        default=None, description="Marketing or product description text"
    )
