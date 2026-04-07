"""Pydantic v2 models for document extraction schemas.

The PRD (docs/PRD.md) is the source of truth for field definitions.
These models generate JSON Schema via .model_json_schema() which is passed
to the Gemini API's response_schema parameter.
"""

from ._coa import CoaExtraction, CoaHeader, LabConclusion, ResultOperator, TestCategory, TestResult
from ._enums import DocumentType
from ._envelope import ClassificationResult, ExtractionResult, PAYLOAD_SCHEMA_MAP, PayloadUnion
from ._invoice import InvoiceLineItem, InvoicePayload
from ._label import LabelPayload
from ._label_proof import LabelProofPayload
from ._packaging_spec import ExtraPackagingComponent, LabelSpecs, PackagingComponents, PackagingSpecSheetPayload
from ._payment_proof import PaymentProofPayload
from ._product_spec import ProductSpecSheetPayload
from ._quote import QuoteLineItem, QuotePayload
from ._shared import CompanyInfo, FormulaComponent, SupplementsFact

__all__ = [
    # Enums
    "DocumentType",
    # COA
    "CoaExtraction",
    "CoaHeader",
    "LabConclusion",
    "ResultOperator",
    "TestCategory",
    "TestResult",
    # Invoice
    "InvoiceLineItem",
    "InvoicePayload",
    # Label
    "LabelPayload",
    # Label proof
    "LabelProofPayload",
    # Packaging spec
    "ExtraPackagingComponent",
    "LabelSpecs",
    "PackagingComponents",
    "PackagingSpecSheetPayload",
    # Payment proof
    "PaymentProofPayload",
    # Product spec
    "ProductSpecSheetPayload",
    # Quote
    "QuoteLineItem",
    "QuotePayload",
    # Shared
    "CompanyInfo",
    "FormulaComponent",
    "SupplementsFact",
    # Envelope
    "ClassificationResult",
    "ExtractionResult",
    "PAYLOAD_SCHEMA_MAP",
    "PayloadUnion",
]
