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


def _md_header() -> str:
    """Return a markdown table header + separator (call once before first row)."""
    return "| File | Type | Details | Confidence |\n| --- | --- | --- | --- |"


def build_summary(
    res: ExtractionResult, filename: str, *, fmt: str = "plain",
) -> str:
    """Build a compact one-line summary string for a single extraction result.

    Args:
        res: The extraction result to summarize.
        filename: Source filename.
        fmt: Output format — ``"plain"`` (pipe-delimited) or ``"markdown"`` (table row).
    """
    doc_type = res.document_type
    conf = res.confidence
    p = res.payload

    if doc_type == DocumentType.COA and p is not None:
        assert isinstance(p, CoaExtraction)
        lot = p.header_data.lot_number if p.header_data else "?"
        product = p.header_data.product_name if p.header_data else "?"
        total = len(p.test_results)
        passed = sum(1 for t in p.test_results if t.lab_conclusion == LabConclusion.PASS)
        details = f"{lot} / {product} / {passed}/{total} PASS"
        if fmt == "markdown":
            return f"| {filename} | COA | {details} | {conf} |"
        return f"{filename} | COA | {lot} | {product} | {passed}/{total} PASS | confidence={conf}"

    if doc_type == DocumentType.INVOICE and p is not None:
        assert isinstance(p, InvoicePayload)
        inv_num = p.doc_number or "?"
        vendor = p.vendor_name or "?"
        items = len(p.line_items)
        total_val = p.grand_total
        total_str = f"${total_val}" if total_val is not None else "?"
        details = f"#{inv_num} / {vendor} / {items} items / {total_str}"
        if fmt == "markdown":
            return f"| {filename} | INVOICE | {details} | {conf} |"
        return f"{filename} | INVOICE | #{inv_num} | {vendor} | {items} items | {total_str} | confidence={conf}"

    if doc_type == DocumentType.QUOTE and p is not None:
        assert isinstance(p, QuotePayload)
        vendor = p.vendor_name or "?"
        items = len(p.quoted_items)
        details = f"{vendor} / {items} items"
        if fmt == "markdown":
            return f"| {filename} | QUOTE | {details} | {conf} |"
        return f"{filename} | QUOTE | {vendor} | {items} items | confidence={conf}"

    # Generic fallback for all other types
    # Try common identifying fields
    for field in ("product_name", "brand", "vendor_name", "doc_number"):
        val = getattr(p, field, None) if p else None
        if val:
            if fmt == "markdown":
                return f"| {filename} | {doc_type} | {val} | {conf} |"
            return f"{filename} | {doc_type} | {val} | confidence={conf}"

    if fmt == "markdown":
        return f"| {filename} | {doc_type} | - | {conf} |"
    return f"{filename} | {doc_type} | confidence={conf}"
