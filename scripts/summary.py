"""Build compact one-line summaries for extraction results."""

from __future__ import annotations

from schemas import ExtractionResult


def build_summary(res: ExtractionResult, filename: str) -> str:
    """Build a compact one-line summary string for a single extraction result."""
    doc_type = res.document_type
    conf = res.confidence
    p = res.payload

    if doc_type == "COA" and p is not None:
        lot = getattr(getattr(p, "header_data", None), "lot_number", "?")
        product = getattr(getattr(p, "header_data", None), "product_name", "?")
        tests = getattr(p, "test_results", [])
        total = len(tests)
        passed = sum(1 for t in tests if getattr(t, "lab_conclusion", None) == "PASS")
        return f"COA | {lot} | {product} | {passed}/{total} PASS | confidence={conf}"

    if doc_type == "INVOICE" and p is not None:
        inv_num = getattr(p, "invoice_number", None) or "?"
        vendor = getattr(p, "vendor_name", None) or "?"
        items = len(getattr(p, "line_items", []))
        total = getattr(p, "grand_total", None)
        total_str = f"${total}" if total is not None else "?"
        return f"INVOICE | #{inv_num} | {vendor} | {items} items | {total_str} | confidence={conf}"

    if doc_type == "QUOTE" and p is not None:
        vendor = getattr(p, "vendor_name", None) or "?"
        items = len(getattr(p, "line_items", []))
        return f"QUOTE | {vendor} | {items} items | confidence={conf}"

    # Generic fallback for all other types
    # Try common identifying fields
    for field in ("product_name", "brand", "vendor_name", "doc_number"):
        val = getattr(p, field, None) if p else None
        if val:
            return f"{doc_type} | {val} | confidence={conf}"

    return f"{doc_type} | {filename} | confidence={conf}"
