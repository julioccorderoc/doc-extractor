"""Packout sheet schema — a manufacturer's finished-goods pack-out record.

Distinct from PACKING_LIST (`_packing_list.py`). A packing list is the generic
line-item manifest any shipper encloses with a shipment: what SKU, how many,
ship-to, ship-from. A packout sheet is what a contract manufacturer issues after
a production run, and its grain is physical rather than commercial — cases and
pallets, each carrying the lot it was filled from, the units inside it, and the
dimensions and weight a freight quote needs.

Two rules run through every field here, and both exist because filling a gap is
a worse failure than leaving one open:

- **Unknown is null, never zero.** A blank units-per-case column means nobody
  stated it. Writing 0 reports a phantom shortfall to whoever reads it next.
- **Never compute a value the document does not print.** If a document states a
  total and a case count but not a case size, leave `units_per_case` null. The
  consumer derives it and flags the derivation; a value filled in here arrives
  indistinguishable from one the manufacturer actually stated, and the operator
  loses the only signal that the document was incomplete.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class PackoutDocumentKind(str, Enum):
    """Whether the document reports new production or restates old geometry."""

    PACKOUT = "PACKOUT"  # new production run
    REWORK = "REWORK"  # re-cases goods already packed; adds no new units


class PackoutCaseType(str, Enum):
    """Shape of one case line."""

    FULL = "FULL"  # a standard case at the stated units-per-case
    PARTIAL = "PARTIAL"  # a remainder case; units_per_case is its ACTUAL content
    UNKNOWN = "UNKNOWN"  # the default — see the extraction notes, never guess


class PackoutWeightBasis(str, Enum):
    """What a stated pallet weight MEANS — manufacturers use one word for both."""

    GROSS = "GROSS"  # the loaded pallet
    TARE = "TARE"  # the empty pallet
    NET = "NET"  # contents only
    UNKNOWN = "UNKNOWN"  # the default when the document does not say


class PackoutCase(BaseModel):
    """One line from the document's CASES section, as printed."""

    model_config = ConfigDict(use_enum_values=True)

    sku_ref: Optional[str] = Field(
        None,
        description=(
            "The product string the document itself uses — a vendor item code or free "
            "text. Copy it verbatim; do not translate it to another code."
        ),
    )
    lot_code_raw: Optional[str] = Field(
        None, description="The lot/batch code printed for this line, exactly as shown."
    )
    exp_date: Optional[str] = Field(
        None,
        description=(
            "Expiration/best-by date for this line in YYYY-MM-DD form. If the document "
            "prints it on the first row of a group only, leave it null on the other "
            "rows — do NOT copy it down."
        ),
    )
    case_type: PackoutCaseType = Field(
        PackoutCaseType.UNKNOWN,
        description=(
            "FULL only when the document says the case is full or standard, PARTIAL only "
            "when it says remainder/partial/odd. Otherwise UNKNOWN. Do not infer this "
            "from the numbers."
        ),
    )
    case_count: int = Field(
        ...,
        ge=1,
        description="How many cases this line covers. Always stated; never zero.",
    )
    units_per_case: Optional[int] = Field(
        None,
        ge=1,
        description=(
            "Units inside ONE case, only when the document states it. If the document "
            "gives a line total and a case count but no case size, leave this NULL — do "
            "NOT divide to fill it in."
        ),
    )
    pallet_ref: Optional[str] = Field(
        None,
        description="The document's own pallet label for this line (e.g. 'Pallet 1', 'A').",
    )
    length_in: Optional[float] = Field(None, ge=0, description="Case length in inches.")
    width_in: Optional[float] = Field(None, ge=0, description="Case width in inches.")
    height_in: Optional[float] = Field(None, ge=0, description="Case height in inches.")
    weight_lbs: Optional[float] = Field(None, ge=0, description="Case weight in pounds.")
    line_no: Optional[int] = Field(
        None, description="1-based position of this line within the cases section."
    )


class PackoutPallet(BaseModel):
    """One line from the document's PALLETS section.

    A group of identical pallets is ONE row: '9 Pallet x 16 Box' is
    `pallet_count=9`, never nine rows. Documents describe exemplar pallets.
    """

    model_config = ConfigDict(use_enum_values=True)

    sku_ref: Optional[str] = Field(None, description="Product string for this pallet, as printed.")
    lot_code_raw: Optional[str] = Field(None, description="Lot code for this pallet, as printed.")
    pallet_ref: Optional[str] = Field(None, description="The document's own pallet label.")
    pallet_count: int = Field(
        ..., ge=1, description="How many identical pallets this line covers."
    )
    cases_on_pallet: Optional[int] = Field(
        None, ge=1, description="Cases stacked on ONE of these pallets, when stated."
    )
    length_in: Optional[float] = Field(None, ge=0, description="Pallet length in inches.")
    width_in: Optional[float] = Field(None, ge=0, description="Pallet width in inches.")
    height_in: Optional[float] = Field(None, ge=0, description="Pallet height in inches.")
    weight_lbs: Optional[float] = Field(None, ge=0, description="Pallet weight in pounds.")
    weight_basis: PackoutWeightBasis = Field(
        PackoutWeightBasis.UNKNOWN,
        description=(
            "Set GROSS/TARE/NET only when the document labels the weight that way. If it "
            "just says 'WEIGHT', leave UNKNOWN — do not judge from the magnitude."
        ),
    )
    stackable: Optional[bool] = Field(
        None, description="Whether the document says these pallets stack. Null if unstated."
    )
    line_no: Optional[int] = Field(
        None, description="1-based position of this line within the pallets section."
    )


class PackoutStatedTotal(BaseModel):
    """A total the document asserts about itself — the cheapest correctness check.

    Copy it as printed. It is worth extracting precisely because it lets the
    consumer check the line rows against the document's own arithmetic.
    """

    model_config = ConfigDict(use_enum_values=True)

    lot_code_raw: Optional[str] = Field(
        None, description="Lot this total is scoped to, or null for a document-level total."
    )
    sku_ref: Optional[str] = Field(
        None, description="Product this total is scoped to, or null for a grand total."
    )
    units: int = Field(..., ge=1, description="The unit count as stated on the document.")


class PackoutPickupBlock(BaseModel):
    """The document's pickup/collection block, as stated."""

    model_config = ConfigDict(use_enum_values=True)

    hours: Optional[str] = Field(None, description="Pickup hours as printed.")
    contact_name: Optional[str] = Field(None, description="Pickup contact person.")
    address: Optional[str] = Field(None, description="Pickup address as one string.")
    email: Optional[str] = Field(None, description="Pickup contact email.")
    phone: Optional[str] = Field(None, description="Pickup contact phone.")


class PackoutSheetPayload(BaseModel):
    """Root schema for a manufacturer's packout sheet."""

    model_config = ConfigDict(use_enum_values=True)

    document_kind: PackoutDocumentKind = Field(
        PackoutDocumentKind.PACKOUT,
        description=(
            "REWORK when the document says it re-cases or re-measures goods already "
            "packed (titles like 'Rework', 'New Case Dims'). PACKOUT otherwise."
        ),
    )
    packed_on: Optional[str] = Field(
        None,
        description=(
            "The date the document gives for the pack-out or its readiness/ship date, "
            "YYYY-MM-DD. This is not a receipt date."
        ),
    )
    vendor_ref: Optional[str] = Field(
        None, description="What the document calls the manufacturer or shipper."
    )
    po_ref: Optional[str] = Field(
        None,
        description=(
            "Any purchase-order string printed on the document, verbatim. Often the "
            "vendor's OWN numbering rather than the buyer's — extract it, do not "
            "interpret it."
        ),
    )
    cases: list[PackoutCase] = Field(
        default_factory=list, description="Every line in the cases section. Do not skip rows."
    )
    pallets: list[PackoutPallet] = Field(
        default_factory=list, description="Every line in the pallets section. Do not skip rows."
    )
    stated_totals: list[PackoutStatedTotal] = Field(
        default_factory=list,
        description="Every total the document prints about itself, scoped where it scopes them.",
    )
    pickup: Optional[PackoutPickupBlock] = Field(
        None, description="The pickup block, when the document has one."
    )
    notes: Optional[str] = Field(
        None, description="Free-text remarks that do not fit another field."
    )
