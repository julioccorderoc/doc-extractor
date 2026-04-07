from __future__ import annotations

from enum import Enum


class DocumentType(str, Enum):
    COA = "COA"
    INVOICE = "INVOICE"
    QUOTE = "QUOTE"
    PRODUCT_SPEC_SHEET = "PRODUCT_SPEC_SHEET"
    PACKAGING_SPEC_SHEET = "PACKAGING_SPEC_SHEET"
    LABEL = "LABEL"
    LABEL_PROOF = "LABEL_PROOF"
    PAYMENT_PROOF = "PAYMENT_PROOF"
    UNKNOWN = "UNKNOWN"
