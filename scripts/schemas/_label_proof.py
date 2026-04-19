"""Label proof schema."""

from __future__ import annotations

from typing import Optional

from pydantic import Field

from ._label import LabelPayload
from ._shared import TechnicalLabelSpecs


class LabelProofPayload(LabelPayload):
    """Label proof sent by the printer for review before production.

    A proof IS a label artwork — same content fields — plus print-job metadata
    (date, printer, vendor/buyer SKUs) and technical print specifications.
    All consumer-facing label fields (brand, supplements_fact_panel,
    other_ingredients, capsule_material, flow_agents, certifications, etc.)
    are inherited from LabelPayload and should be extracted with the same
    semantics.
    """

    date: Optional[str] = Field(
        default=None, description="Proof date in YYYY-MM-DD format"
    )
    manufacturer_name: Optional[str] = Field(
        default=None, description="Name of the printing company producing the proof"
    )
    vendor_product_id: Optional[str] = Field(
        default=None, description="Product code or SKU used by the printer/manufacturer"
    )
    buyer_product_id: Optional[str] = Field(
        default=None, description="Product code or SKU used by the buyer"
    )
    label_specs: Optional[TechnicalLabelSpecs] = Field(
        default=None, description="Technical print specifications"
    )
