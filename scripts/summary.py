"""Build compact one-line summaries for extraction results."""

from __future__ import annotations

from schemas import (
    CoaExtraction,
    DocumentType,
    ExtractionResult,
    InvoicePayload,
    LabConclusion,
    PackoutSheetPayload,
    QuotePayload,
)


def _md_header() -> str:
    """Return a markdown table header + separator (call once before first row)."""
    return "| File | Type | Details | Confidence | Tokens |\n| --- | --- | --- | --- | --- |"


def _detail_parts(res: ExtractionResult) -> list[str]:
    """Type-specific detail fields, most identifying first. Empty when unknown."""
    doc_type = res.document_type
    p = res.payload

    if p is None:
        return []

    if doc_type == DocumentType.COA and isinstance(p, CoaExtraction):
        header = p.header_data
        rows = p.test_results
        passed = sum(1 for t in rows if t.lab_conclusion == LabConclusion.PASS)
        failed = sum(
            1 for t in rows
            if t.lab_conclusion in (LabConclusion.FAIL, LabConclusion.OOS)
        )
        # '12/27 PASS' read as 15 failures when the remainder were information-only
        # rows or rows the certificate simply does not judge. Report the states
        # apart so a clean COA looks clean and a real failure stands out.
        unjudged = len(rows) - passed - failed
        verdict = f"{passed} pass"
        if failed:
            verdict += f", {failed} FAIL"
        if unjudged:
            verdict += f", {unjudged} unjudged"
        return [
            (header.lot_number if header else None) or "?",
            (header.product_name if header else None) or "?",
            f"{verdict} of {len(rows)}",
        ]

    if doc_type == DocumentType.INVOICE and isinstance(p, InvoicePayload):
        total_val = p.grand_total
        return [
            f"#{p.doc_number or '?'}",
            p.vendor_name or "?",
            f"{len(p.line_items)} items",
            f"${total_val}" if total_val is not None else "?",
        ]

    if doc_type == DocumentType.QUOTE and isinstance(p, QuotePayload):
        return [p.vendor_name or "?", f"{len(p.quoted_items)} items"]

    if doc_type == DocumentType.PACKOUT_SHEET and isinstance(p, PackoutSheetPayload):
        # Case COUNT, not row count: '12 cases' across 3 lines is 12, and that is
        # the number the operator reconciles against the document's own total.
        cases = sum(c.case_count for c in p.cases)
        pallets = sum(pl.pallet_count for pl in p.pallets)
        stated = p.stated_totals[0].units if p.stated_totals else None
        parts = [
            p.vendor_ref or "?",
            f"{cases} cases",
            f"{pallets} pallets",
        ]
        parts.append(f"stated {stated}" if stated is not None else "no stated total")
        return parts

    # Generic fallback for all other types — first identifying field that exists.
    for field in ("product_name", "brand", "vendor_name", "doc_number"):
        val = getattr(p, field, None)
        if val:
            return [str(val)]
    return []


def _token_cell(res: ExtractionResult) -> str:
    """Billed tokens for this document, or '?' when the API reported none."""
    if res.usage is None or res.usage.total_tokens is None:
        return "?"
    return str(res.usage.total_tokens)


def build_summary(
    res: ExtractionResult, filename: str, *, fmt: str = "plain",
) -> str:
    """Build a compact one-line summary string for a single extraction result.

    Args:
        res: The extraction result to summarize.
        filename: Source filename.
        fmt: Output format — ``"plain"`` (pipe-delimited) or ``"markdown"`` (table row).
    """
    doc_type = res.document_type.value
    parts = _detail_parts(res)
    tokens = _token_cell(res)

    if fmt == "markdown":
        details = " / ".join(parts) if parts else "-"
        return f"| {filename} | {doc_type} | {details} | {res.confidence} | {tokens} |"

    fields = [filename, doc_type, *parts, f"confidence={res.confidence}"]
    if tokens != "?":
        fields.append(f"tokens={tokens}")
    return " | ".join(fields)
