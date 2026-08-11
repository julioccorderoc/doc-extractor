"""Top-level extraction envelope and routing map."""

from __future__ import annotations

import datetime
from typing import Optional, Union

from pydantic import BaseModel, Field

from ._coa import CoaExtraction
from ._enums import DocumentType
from ._generic import GenericPayload
from ._invoice import InvoicePayload
from ._label import LabelPayload
from ._label_proof import LabelProofPayload
from ._label_order_ack import LabelOrderAckPayload
from ._packaging_spec import PackagingSpecSheetPayload
from ._packing_list import PackingListPayload
from ._packout import PackoutSheetPayload
from ._payment_proof import PaymentProofPayload
from ._product_spec import ProductSpecSheetPayload
from ._quote import QuotePayload

PayloadUnion = Union[
    PaymentProofPayload,
    CoaExtraction,
    LabelOrderAckPayload,
    InvoicePayload,
    QuotePayload,
    PackagingSpecSheetPayload,
    ProductSpecSheetPayload,
    LabelProofPayload,
    LabelPayload,
    PackoutSheetPayload,
    PackingListPayload,
    GenericPayload,
]


class TokenUsage(BaseModel):
    """Tokens billed for one extraction, summed across both passes.

    Present so a caller running this in production can attribute cost per
    document. Absent (null) when the model returned no usage metadata — a
    missing block means unknown, never zero.
    """

    model: str = Field(description="Model id that produced the extraction")
    prompt_tokens: Optional[int] = Field(
        default=None, description="Input tokens across classification and extraction"
    )
    output_tokens: Optional[int] = Field(
        default=None, description="Generated tokens across classification and extraction"
    )
    total_tokens: Optional[int] = Field(
        default=None, description="Total billed tokens as reported by the API"
    )
    calls: int = Field(
        default=0, description="Model calls made for this document (1 with --type, else 2)"
    )


class ExtractionResult(BaseModel):
    document_type: DocumentType = Field(description="Classified document type")
    confidence: float = Field(
        description="Classification confidence score from 0.0 to 1.0",
        ge=0.0,
        le=1.0,
    )
    extracted_date: Optional[datetime.date] = Field(
        default=None, description="Extraction date in YYYY-MM-DD format"
    )
    payload: Optional[PayloadUnion] = Field(  # type: ignore[valid-type]  # mypy cannot resolve Union type alias used in Optional with PEP 563 deferred annotations
        default=None,
        description="Extracted document data (schema varies by document_type)",
    )
    raw_text_fallback: Optional[str] = Field(
        default=None,
        description="Raw text extraction used when structured extraction fails",
    )
    usage: Optional[TokenUsage] = Field(
        default=None,
        description="Tokens billed for this document. Null when the API reported none.",
    )
    text_context_chars: Optional[int] = Field(
        default=None,
        description=(
            "Characters of local text handed to the model alongside the image. 0 means "
            "liteparse ran and found nothing — a scan it could not read; null means it "
            "did not run or was skipped. Success otherwise has no signal at all, only "
            "the absence of a warning, so a caller cannot tell a hybrid extraction from "
            "a vision-only one after the fact."
        ),
    )


class ClassificationResult(BaseModel):
    document_type: DocumentType = Field(description="Classified document type")
    confidence: float = Field(
        description="Classification confidence score from 0.0 to 1.0",
        ge=0.0,
        le=1.0,
    )


# Mapping from document type to its payload schema (pass 2 routing).
PAYLOAD_SCHEMA_MAP: dict[DocumentType, type[BaseModel]] = {
    DocumentType.PAYMENT_PROOF: PaymentProofPayload,
    DocumentType.COA: CoaExtraction,
    DocumentType.INVOICE: InvoicePayload,
    DocumentType.QUOTE: QuotePayload,
    DocumentType.PACKAGING_SPEC_SHEET: PackagingSpecSheetPayload,
    DocumentType.PRODUCT_SPEC_SHEET: ProductSpecSheetPayload,
    DocumentType.LABEL_PROOF: LabelProofPayload,
    DocumentType.LABEL_ORDER_ACK: LabelOrderAckPayload,
    DocumentType.LABEL: LabelPayload,
    DocumentType.PACKOUT_SHEET: PackoutSheetPayload,
    DocumentType.PACKING_LIST: PackingListPayload,
    DocumentType.UNKNOWN: GenericPayload,
}
