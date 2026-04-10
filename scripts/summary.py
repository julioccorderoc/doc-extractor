"""Build compact one-line summaries for extraction results."""

from __future__ import annotations

from schemas import (
    CoaExtraction,
    DocumentType,
    ExtractionResult,
    InvoicePayload,
    LabConclusion,
    QuotePayload,
)


def build_summary(res: ExtractionResult, filename: str) -> str:
    """Build a compact one-line summary string for a single extraction result."""
    doc_type = res.document_type
    conf = res.confidence
    p = res.payload

    if doc_type == DocumentType.COA and p is not None:
        assert isinstance(p, CoaExtraction)
        lot = p.header_data.lot_number if p.header_data else "?"
        product = p.header_data.product_name if p.header_data else "?"
        total = len(p.test_results)
        passed = sum(1 for t in p.test_results if t.lab_conclusion == LabConclusion.PASS)
        return f"COA | {lot} | {product} | {passed}/{total} PASS | confidence={conf}"

    if doc_type == DocumentType.INVOICE and p is not None:
        assert isinstance(p, InvoicePayload)
        inv_num = p.invoice_number or "?"
        vendor = p.vendor_name or "?"
        items = len(p.line_items)
        total = p.grand_total
        total_str = f"${total}" if total is not None else "?"
        return f"INVOICE | #{inv_num} | {vendor} | {items} items | {total_str} | confidence={conf}"

    if doc_type == DocumentType.QUOTE and p is not None:
        assert isinstance(p, QuotePayload)
        vendor = p.vendor_name or "?"
        items = len(p.quoted_items)
        return f"QUOTE | {vendor} | {items} items | confidence={conf}"

    # Generic fallback for all other types
    # Try common identifying fields
    for field in ("product_name", "brand", "vendor_name", "doc_number"):
        val = getattr(p, field, None) if p else None
        if val:
            return f"{doc_type} | {val} | confidence={conf}"

    return f"{doc_type} | {filename} | confidence={conf}"
