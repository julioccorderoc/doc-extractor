"""Document extraction engine using Google Gemini models.

Two-pass extraction:
  Pass 1 — classify the document type (cheap, small schema)
  Pass 2 — extract payload fields using the exact schema for that type

Usage:
    python scripts/parse_vision.py <absolute_file_path> [--type TYPE]

    --type TYPE   Skip pass 1 and use the supplied document type directly.
                  Useful when the caller already knows the document type.
                  Valid values: COA, INVOICE, QUOTE, PRODUCT_SPEC_SHEET,
                  PACKAGING_SPEC_SHEET, LABEL, LABEL_PROOF, LABEL_ORDER_ACK,
                  PAYMENT_PROOF, PACKING_LIST, PACKOUT_SHEET, UNKNOWN

Exit codes:
    0 - Success
    1 - Missing GEMINI_DOC_EXTRACTOR_KEY
    2 - Bad file type, file not found, or invalid --type value
    3 - API failure after retries
    4 - Model response failed schema validation
    5 - Timed out on a single document
    6 - Quota exhausted (a wall, not a hiccup — stop the batch)
    7 - Local processing failure (anything else)

Codes 4-7 used to be indistinguishable from 3: one bare `except Exception`
collapsed API failure, validation error, timeout and local crash into a single
code, so a caller had to grep stderr to learn what happened. In a batch, the
worst class seen is the one returned.
"""

from __future__ import annotations

import datetime
import json
import os
import signal
import sys
import tempfile
from pathlib import Path

import pydantic
from google import genai
from google.genai import errors as genai_errors

from _cli import build_parser, handle_schema
from _output import print_err, print_progress, set_quiet, write_json_atomic, write_output
from gemini import (
    QuotaExceeded,
    UsageTally,
    cleanup,
    classify,
    extract_typed,
    upload_file,
    wait_for_processing,
    with_retry,
)
from ingestion import (
    IngestionError,
    build_files_to_process,
    preprocess_file,
    slice_pdf,
)
from schemas import (
    DocumentType,
    ExtractionResult,
    PAYLOAD_SCHEMA_MAP,
    TokenUsage,
)
from summary import _md_header, build_summary

__version__ = "0.3.0"

DEFAULT_MODEL = "gemini-3.1-pro-preview"

EXIT_OK = 0
EXIT_NO_KEY = 1
EXIT_BAD_INPUT = 2
EXIT_API = 3
EXIT_VALIDATION = 4
EXIT_TIMEOUT = 5
EXIT_QUOTA = 6
EXIT_LOCAL = 7


class ExtractionTimeout(Exception):
    """One document exceeded its wall-clock budget."""


class _Deadline:
    """SIGALRM wall-clock guard for a single document.

    Local text extraction has no timeout of its own and the upload/poll loop only
    bounds processing, not the whole call — so one pathological PDF can hang a
    batch forever. An alarm covers every phase including the parts this module
    does not own. No-ops when disabled or off the main thread, where signal
    cannot arm.
    """

    def __init__(self, seconds: int):
        self.seconds = seconds
        self._previous = None

    def __enter__(self):
        if self.seconds and self.seconds > 0 and hasattr(signal, "SIGALRM"):
            try:
                self._previous = signal.signal(signal.SIGALRM, self._fire)
                signal.alarm(self.seconds)
            except ValueError:
                self._previous = None  # not the main thread; run unguarded
        return self

    def __exit__(self, *exc):
        if self._previous is not None:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, self._previous)
        return False

    def _fire(self, _signum, _frame):
        raise ExtractionTimeout(f"exceeded {self.seconds}s wall clock")


def _extract_text_context(file_path: Path) -> tuple[str | None, int | None]:
    """Run liteparse locally to get deterministic text for hybrid extraction.

    Returns (text, char_count). char_count is 0 when liteparse ran and found
    nothing, None when it could not run — success previously had no positive
    signal at all, only the absence of a warning, which left callers unable to
    tell a hybrid extraction from a vision-only one after the fact.
    """
    try:
        from liteparse import LiteParse

        print_progress(f"Extracting local text context for {file_path.name} via liteparse...")
        lp = LiteParse()
        lp_result = lp.parse(str(file_path))
        text = getattr(lp_result, "text", "") or ""
        if text.strip():
            print_progress(f"liteparse: {len(text)} chars of text context")
            return text, len(text)
        print_err("Warning: liteparse returned empty text.")
        return None, 0
    except ImportError:
        print_err("Warning: liteparse is not installed. Skipping local text extraction.")
        return None, None
    except Exception as e:
        print_err(f"Warning: liteparse extraction failed: {e}")
        return None, None


def _already_extracted(path: Path) -> bool:
    """True when a prior run left a complete output here.

    Parsed, not merely present: a truncated file from a crash must be re-run, not
    skipped. Atomic writes make this check trustworthy as a resume marker.
    """
    try:
        return bool(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return False


def _build_usage(tally: UsageTally, model: str) -> TokenUsage | None:
    """Project the tally onto the output model. None when nothing was reported.

    A null `usage` block means the API told us nothing; it must never read as a
    free extraction.
    """
    if not tally.seen:
        return None
    return TokenUsage(
        model=model,
        prompt_tokens=tally.prompt_tokens,
        output_tokens=tally.output_tokens,
        total_tokens=tally.total_tokens,
        calls=tally.calls,
    )


def process_single_file(
    file_path: Path,
    client: genai.Client,
    model: str,
    hint_type: DocumentType | None,
    temp_dir_path: Path,
    *,
    pages: str | None = None,
    skip_liteparse: bool = False,
    debug: bool = False,
    summary_only: bool = False,
) -> tuple[ExtractionResult | None, int]:
    """Extract one document. Returns (result, exit_code) — the code names the
    failure class so a caller never has to parse stderr to learn what broke."""
    # 1. Preprocess (Convert .xlsx/.docx to .txt)
    processed_path = preprocess_file(file_path, temp_dir_path)

    # 2. Slice PDF if requested
    if pages:
        if processed_path.suffix.lower() == ".pdf":
            processed_path = slice_pdf(processed_path, pages, temp_dir_path)
        else:
            print_err(
                f"Warning: --pages only applies to PDF files. Ignoring for {processed_path.name}"
            )

    # 3. Extract text locally unless skipped
    if skip_liteparse:
        text_context, text_chars = None, None
    else:
        text_context, text_chars = _extract_text_context(processed_path)

    tally = UsageTally()
    uploaded_file = None
    try:
        uploaded_file = with_retry(upload_file, client, processed_path)
        uploaded_file = wait_for_processing(client, uploaded_file)

        # Pass 1 — classify
        if hint_type is not None:
            doc_type = hint_type
            confidence = 1.0
            print_progress(f"Using caller-supplied type: {doc_type.value}")
        else:
            classification = with_retry(classify, client, uploaded_file, model, tally)
            doc_type = classification.document_type
            confidence = classification.confidence
            print_progress(f"Classified as: {doc_type.value} (confidence: {confidence:.2f})")

        # Summary-only mode: skip pass 2 entirely
        if summary_only:
            return ExtractionResult(
                document_type=doc_type,
                confidence=confidence,
                extracted_date=datetime.date.today(),
                payload=None,
                usage=_build_usage(tally, model),
                text_context_chars=text_chars,
            ), EXIT_OK

        # Pass 2 — extract with specific schema
        payload = None
        if doc_type in PAYLOAD_SCHEMA_MAP:
            payload_class = PAYLOAD_SCHEMA_MAP[doc_type]
            payload_json = with_retry(
                extract_typed,
                client,
                uploaded_file,
                model,
                doc_type,
                payload_class,
                text_context,
                tally,
            )
            try:
                payload = payload_class.model_validate_json(payload_json)
            except pydantic.ValidationError as e:
                if debug:
                    print_err(
                        f"\n--- DEBUG: RAW LLM RESPONSE ---\n{payload_json}\n--- END DEBUG ---\n"
                    )
                raise e

        return ExtractionResult(
            document_type=doc_type,
            confidence=confidence,
            extracted_date=datetime.date.today(),
            payload=payload,
            usage=_build_usage(tally, model),
            text_context_chars=text_chars,
        ), EXIT_OK

    except QuotaExceeded as e:
        print_err(f"Error processing {file_path.name}: quota exhausted: {e}")
        return None, EXIT_QUOTA
    except ExtractionTimeout as e:
        print_err(f"Error processing {file_path.name}: timed out: {e}")
        return None, EXIT_TIMEOUT
    except genai_errors.APIError as e:
        print_err(
            f"Error processing {file_path.name}: API failure after retries (HTTP {e.code}): {e.message}"
        )
        return None, EXIT_API
    except pydantic.ValidationError as e:
        print_err(
            f"Error processing {file_path.name}: LLM response failed schema validation: {e}"
        )
        return None, EXIT_VALIDATION
    except Exception as e:
        print_err(f"Error processing {file_path.name}: {e}")
        return None, EXIT_LOCAL
    finally:
        if uploaded_file is not None:
            cleanup(client, uploaded_file)


def main() -> None:
    parser = build_parser(__version__)
    args = parser.parse_args()

    set_quiet(not args.verbose)

    if args.schema:
        handle_schema(args.schema)
        sys.exit(0)

    if not args.file_path and not args.url:
        print_err("Error: Must provide either a local file_path or --url")
        parser.print_help(sys.stderr)
        sys.exit(2)

    hint_type: DocumentType | None = None
    if args.type:
        raw_type = args.type.upper()
        try:
            hint_type = DocumentType(raw_type)
        except ValueError:
            valid = ", ".join(t.value for t in DocumentType)
            print_err(f"Error: Unknown document type '{raw_type}'. Valid: {valid}")
            sys.exit(2)

    # Determine model and API key
    model = os.environ.get("GEMINI_MODEL", DEFAULT_MODEL)
    api_key = os.environ.get("GEMINI_DOC_EXTRACTOR_KEY")
    if not api_key:
        print_err(
            "Error: GEMINI_DOC_EXTRACTOR_KEY is not set.\n"
            "Get a key at https://aistudio.google.com/apikey and run:\n"
            "  export GEMINI_DOC_EXTRACTOR_KEY='your-key-here'"
        )
        sys.exit(1)

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)

        client = genai.Client(api_key=api_key)

        try:
            files_to_process = build_files_to_process(args.file_path, args.url, temp_dir_path)
        except IngestionError:
            sys.exit(2)

        summary_fmt: str = args.format
        results = []
        summaries: list[str] = []
        worst_exit = EXIT_OK
        out_dir = Path(args.output_dir) if args.output_dir else None
        for fp in files_to_process:
            per_file_out = out_dir / f"{fp.stem}.json" if out_dir else None
            if args.skip_existing and per_file_out and _already_extracted(per_file_out):
                print_progress(f"Skipping {fp.name} — {per_file_out} already present")
                continue
            try:
                with _Deadline(args.timeout_secs):
                    res, code = process_single_file(
                        fp, client, model, hint_type, temp_dir_path,
                        pages=args.pages, skip_liteparse=args.skip_liteparse, debug=args.debug,
                        summary_only=args.summary_only,
                    )
            except IngestionError:
                worst_exit = max(worst_exit, EXIT_BAD_INPUT)
                continue
            except ExtractionTimeout as e:
                # The alarm can land between phases, outside the inner handler.
                print_err(f"Error processing {fp.name}: timed out: {e}")
                res, code = None, EXIT_TIMEOUT
            worst_exit = max(worst_exit, code)
            if code == EXIT_QUOTA:
                print_err("Stopping: quota is a wall, not a hiccup — remaining files skipped.")
                break
            if res:
                res_dict = res.model_dump(mode="json")
                res_dict["source_file"] = fp.name
                res_dict["source_path"] = str(fp.resolve())
                if args.source_id:
                    res_dict["source_id"] = args.source_id
                results.append(res_dict)
                if per_file_out:
                    write_json_atomic(res_dict, per_file_out)
                    print_progress(f"Output written to {per_file_out}")
                if not args.no_summary:
                    summaries.append(build_summary(res, fp.name, fmt=summary_fmt))

        if not results:
            print_err("No files were successfully processed.")
            sys.exit(worst_exit if worst_exit != EXIT_OK else EXIT_API)

        if args.summary_only:
            # Print only summaries to stderr, no JSON output
            if summary_fmt == "markdown" and summaries:
                print_err(_md_header())
            for s in summaries:
                print_err(s)
        elif out_dir and not args.output:
            # Per-file outputs are already on disk; stdout would duplicate them.
            for s in summaries:
                print_err(s)
        else:
            if summary_fmt == "markdown" and summaries:
                summaries.insert(0, _md_header())
            write_output(results, summaries, args.output)

        if worst_exit != EXIT_OK:
            print_err(f"Completed with failures ({len(results)} succeeded); exit {worst_exit}")
            sys.exit(worst_exit)


if __name__ == "__main__":
    main()
