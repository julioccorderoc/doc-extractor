"""Document extraction engine using Google Gemini models.

Two-pass extraction:
  Pass 1 — classify the document type (cheap, small schema)
  Pass 2 — extract payload fields using the exact schema for that type

Usage:
    python scripts/parse_vision.py <absolute_file_path> [--type TYPE]

    --type TYPE   Skip pass 1 and use the supplied document type directly.
                  Useful when the caller already knows the document type.
                  Valid values: COA, INVOICE, QUOTE, PRODUCT_SPEC_SHEET,
                  PACKAGING_SPEC_SHEET, LABEL, LABEL_PROOF, PAYMENT_PROOF, UNKNOWN

Exit codes:
    0 - Success (JSON printed to stdout)
    1 - Missing GEMINI_DOC_EXTRACTOR_KEY
    2 - Bad file type, file not found, or invalid --type value
    3 - API failure after retries
"""

from __future__ import annotations

import datetime
import os
import sys
import tempfile
from pathlib import Path

import pydantic
from google import genai
from google.genai import errors as genai_errors

from _cli import build_parser, handle_schema
from _output import print_err, print_progress, set_quiet, write_output
from gemini import (
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
)
from summary import _md_header, build_summary

__version__ = "0.1.0"

DEFAULT_MODEL = "gemini-3.1-pro-preview"


def _extract_text_context(file_path: Path) -> str | None:
    """Run liteparse locally to get deterministic text for hybrid extraction.

    Returns extracted text or None if liteparse is unavailable/fails.
    """
    try:
        from liteparse import LiteParse

        print_progress(f"Extracting local text context for {file_path.name} via liteparse...")
        lp = LiteParse()
        lp_result = lp.parse(str(file_path))
        if hasattr(lp_result, "text") and lp_result.text.strip():
            return lp_result.text
        print_err("Warning: liteparse returned empty text.")
        return None
    except ImportError:
        print_err("Warning: liteparse is not installed. Skipping local text extraction.")
        return None
    except Exception as e:
        print_err(f"Warning: liteparse extraction failed: {e}")
        return None


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
) -> ExtractionResult | None:
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
    text_context = None if skip_liteparse else _extract_text_context(processed_path)

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
            classification = with_retry(classify, client, uploaded_file, model)
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
            )

        # Pass 2 — extract with specific schema
        payload = None
        if doc_type in PAYLOAD_SCHEMA_MAP:
            payload_class = PAYLOAD_SCHEMA_MAP[doc_type]
            payload_json = with_retry(
                extract_typed, client, uploaded_file, model, doc_type, payload_class, text_context
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
        )

    except genai_errors.APIError as e:
        print_err(
            f"Error processing {file_path.name}: API failure after retries (HTTP {e.code}): {e.message}"
        )
        return None
    except pydantic.ValidationError as e:
        print_err(
            f"Error processing {file_path.name}: LLM response failed schema validation: {e}"
        )
        return None
    except Exception as e:
        print_err(f"Error processing {file_path.name}: {e}")
        return None
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
        for fp in files_to_process:
            try:
                res = process_single_file(
                    fp, client, model, hint_type, temp_dir_path,
                    pages=args.pages, skip_liteparse=args.skip_liteparse, debug=args.debug,
                    summary_only=args.summary_only,
                )
            except IngestionError:
                continue
            if res:
                res_dict = res.model_dump(mode="json")
                res_dict["source_file"] = fp.name
                results.append(res_dict)
                if not args.no_summary:
                    summaries.append(build_summary(res, fp.name, fmt=summary_fmt))

        if not results:
            print_err("No files were successfully processed.")
            sys.exit(3)

        if args.summary_only:
            # Print only summaries to stderr, no JSON output
            if summary_fmt == "markdown" and summaries:
                print_err(_md_header())
            for s in summaries:
                print_err(s)
        else:
            if summary_fmt == "markdown" and summaries:
                summaries.insert(0, _md_header())
            write_output(results, summaries, args.output)


if __name__ == "__main__":
    main()
