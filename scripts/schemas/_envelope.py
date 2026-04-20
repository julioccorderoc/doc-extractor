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
    GenericPayload,
]


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
    DocumentType.UNKNOWN: GenericPayload,
}
