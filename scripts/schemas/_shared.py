"""Shared sub-models reused across multiple document payload schemas."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class FormulaComponent(BaseModel):
    ingredient: str = Field(description="Ingredient name")
    amount: Optional[float] = Field(
        default=None, description="Amount per serving as a number"
    )
    unit: Optional[str] = Field(
        default=None, description="Unit of measurement (e.g. 'mg', 'g', 'mcg', 'IU')"
    )


class SupplementsFact(BaseModel):
    ingredient: Optional[str] = Field(default=None, description="Ingredient name")
    amount_per_serving: Optional[str] = Field(
        default=None, description="Amount per serving with unit"
    )
    daily_value_percent: Optional[str] = Field(
        default=None, description="Percent daily value (%DV)"
    )


class CompanyInfo(BaseModel):
    name: Optional[str] = Field(default=None, description="Company name")
    address: Optional[str] = Field(default=None, description="Full address")
    email: Optional[str] = Field(default=None, description="Contact email")
    phone: Optional[str] = Field(default=None, description="Contact phone")


class SpecSheetHeader(BaseModel):
    """Common header fields shared by product and packaging spec sheets."""

    date: Optional[str] = Field(
        default=None, description="Document date in YYYY-MM-DD format"
    )
    version: Optional[str] = Field(
        default=None,
        description="Document version or revision number (e.g. 'Rev 1', 'v2')",
    )
    manufacturer_name: Optional[str] = Field(
        default=None, description="Manufacturer or company name"
    )
    product_name: Optional[str] = Field(default=None, description="Product name")
    vendor_product_id: Optional[str] = Field(
        default=None, description="Product code or SKU used by the vendor/manufacturer"
    )
    buyer_product_id: Optional[str] = Field(
        default=None, description="Product code or SKU used by the buyer"
    )
    product_description: Optional[str] = Field(
        default=None, description="Product description"
    )
    count: Optional[int] = Field(
        default=None, description="Number of units per container"
    )
    count_unit: Optional[str] = Field(
        default=None,
        description="Unit type for count (e.g. 'capsule', 'tablet', 'softgel', 'gummy')",
    )
    servings: Optional[int] = Field(
        default=None, description="Number of servings per container"
    )


class TechnicalLabelSpecs(BaseModel):
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
