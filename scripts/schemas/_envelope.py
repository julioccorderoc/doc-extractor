"""Top-level extraction envelope and routing map."""

from __future__ import annotations

from typing import Optional, Union

from pydantic import BaseModel, Field

from ._coa import CoaExtraction
from ._enums import DocumentType
from ._invoice import InvoicePayload
from ._label import LabelPayload
from ._label_proof import LabelProofPayload
from ._packaging_spec import PackagingSpecSheetPayload
from ._payment_proof import PaymentProofPayload
from ._product_spec import ProductSpecSheetPayload
from ._quote import QuotePayload

PayloadUnion = Union[
    PaymentProofPayload,
    CoaExtraction,
    InvoicePayload,
    QuotePayload,
    PackagingSpecSheetPayload,
    ProductSpecSheetPayload,
    LabelProofPayload,
    LabelPayload,
]


class ExtractionResult(BaseModel):
    document_type: DocumentType = Field(description="Classified document type")
    confidence: float = Field(
        description="Classification confidence score from 0.0 to 1.0",
        ge=0.0,
        le=1.0,
    )
    extracted_date: Optional[str] = Field(
        default=None, description="Extraction date in YYYY-MM-DD format"
    )
    payload: Optional[PayloadUnion] = Field(  # type: ignore[valid-type]
        default=None,
        description="Extracted document data (schema varies by document_type)",
    )
    raw_text_fallback: Optional[str] = Field(
        default=None,
        description="Raw text extraction used when structured extraction fails or document_type is UNKNOWN",
    )


class ClassificationResult(BaseModel):
    document_type: DocumentType = Field(description="Classified document type")
    confidence: float = Field(
        description="Classification confidence score from 0.0 to 1.0",
        ge=0.0,
        le=1.0,
    )


# Mapping from document type to its payload schema (pass 2 routing).
# UNKNOWN is intentionally omitted — no structured payload.
PAYLOAD_SCHEMA_MAP: dict[DocumentType, type[BaseModel]] = {
    DocumentType.PAYMENT_PROOF: PaymentProofPayload,
    DocumentType.COA: CoaExtraction,
    DocumentType.INVOICE: InvoicePayload,
    DocumentType.QUOTE: QuotePayload,
    DocumentType.PACKAGING_SPEC_SHEET: PackagingSpecSheetPayload,
    DocumentType.PRODUCT_SPEC_SHEET: ProductSpecSheetPayload,
    DocumentType.LABEL_PROOF: LabelProofPayload,
    DocumentType.LABEL: LabelPayload,
}
