"""Packaging specification sheet schema."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ExtraPackagingComponent(BaseModel):
    component_name: str = Field(
        description="Name of the non-standard packaging component"
    )
    description: Optional[str] = Field(
        default=None, description="Component specification or description"
    )


class PackagingComponents(BaseModel):
    """Normalized packaging components. Known components have dedicated fields;
    anything else goes in extras."""

    container: Optional[str] = Field(
        default=None, description="Bottle or container specification"
    )
    closure: Optional[str] = Field(
        default=None, description="Cap or closure specification"
    )
    filler: Optional[str] = Field(
        default=None,
        description="Packing material inside the bottle (e.g. rayon packing)",
    )
    desiccant: Optional[str] = Field(
        default=None, description="Desiccant or moisture absorber specification"
    )
    neck_band: Optional[str] = Field(
        default=None,
        description="Outer safety seal, neck band, or shrink band specification",
    )
    label: Optional[str] = Field(
        default=None, description="Label description (size, barcode, FNSKU)"
    )
    master_shipper: Optional[str] = Field(
        default=None, description="Outer carton or master shipper specification"
    )
    inner_shipper: Optional[str] = Field(
        default=None,
        description="Inner shipper, divider, or inner box specification",
    )
    pallet: Optional[str] = Field(
        default=None, description="Pallet configuration specification"
    )
    extras: list[ExtraPackagingComponent] = Field(
        default_factory=list,
        description="Components not covered by standard fields above",
    )


class LabelSpecs(BaseModel):
    """Normalized label roll specifications. Known fields have dedicated slots;
    anything else goes in extras."""

    label_size: Optional[str] = Field(
        default=None,
        description="Label dimensions (e.g. '3\" x 8\"' or '70mm x 178mm')",
    )
    barcode: Optional[str] = Field(
        default=None, description="Barcode or FNSKU printed on the label"
    )
    core_size: Optional[str] = Field(
        default=None, description="Inner core diameter of the label roll"
    )
    max_outer_diameter: Optional[str] = Field(
        default=None, description="Maximum outer diameter of the label roll"
    )
    wind_position: Optional[str] = Field(
        default=None,
        description="Rewind/wind direction (e.g. 'left to right')",
    )
    extras: list[str] = Field(
        default_factory=list,
        description="Additional label specifications not covered by standard fields",
    )


class PackagingSpecSheetPayload(BaseModel):
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
        description="Unit type (e.g. 'capsule', 'tablet', 'softgel')",
    )
    servings: Optional[int] = Field(
        default=None, description="Number of servings per container"
    )
    packaging_components: PackagingComponents = Field(
        default_factory=PackagingComponents,
        description="Normalized packaging components",
    )
    label_specs: LabelSpecs = Field(
        default_factory=LabelSpecs,
        description="Label roll specification details",
    )
