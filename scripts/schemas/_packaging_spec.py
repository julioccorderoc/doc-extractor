"""Packaging specification sheet schema."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from ._shared import LabelSpecs, SpecSheetHeader


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
        description="Packing material inside the bottle (e.g. 'Cotton Coil')",
    )
    desiccant: Optional[str] = Field(
        default=None, description="Desiccant or moisture absorber specification"
    )
    neck_band: Optional[str] = Field(
        default=None,
        description="Outer safety seal, neck band, or shrink band specification",
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


class PackagingLabelSpecs(LabelSpecs):
    """Label roll specifications as tracked on a packaging spec sheet.
    Extends the base dimensional specs with a barcode slot and an escape hatch."""

    barcode_text: Optional[str] = Field(
        default=None,
        description="Human-readable digits printed beneath the barcode (UPC/EAN/FNSKU text) on the label",
    )
    extras: list[str] = Field(
        default_factory=list,
        description="Additional label specifications not covered by standard fields",
    )


class PackagingSpecSheetPayload(SpecSheetHeader):
    packaging_components: PackagingComponents = Field(
        default_factory=PackagingComponents,
        description="Normalized packaging components",
    )
    label_specs: PackagingLabelSpecs = Field(
        default_factory=PackagingLabelSpecs,
        description="Label roll specification details",
    )
