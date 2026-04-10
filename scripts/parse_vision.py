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

import argparse
import datetime
import json
import os
import sys
import tempfile
from pathlib import Path

import pydantic
from google import genai
from google.genai import errors as genai_errors

from _output import print_err, print_progress, set_quiet
from gemini import (
    cleanup,
    classify,
    extract_typed,
    upload_file,
    wait_for_processing,
    with_retry,
)
from ingestion import (
    ALLOWED_EXTENSIONS,
    IngestionError,
    download_url,
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
    text_context: str | None = None
    if not skip_liteparse:
        try:
            from liteparse import LiteParse

            print_progress(
                f"Extracting local text context for {processed_path.name} via liteparse..."
            )
            lp = LiteParse()
            lp_result = lp.parse(str(processed_path))
            if hasattr(lp_result, "text") and lp_result.text.strip():
                text_context = lp_result.text
            else:
                print_err("Warning: liteparse returned empty text.")
        except ImportError:
            print_err(
                "Warning: liteparse is not installed. Skipping local text extraction."
            )
        except Exception as e:
            print_err(f"Warning: liteparse extraction failed: {e}")

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


def build_files_to_process(
    args: argparse.Namespace, temp_dir_path: Path,
) -> list[Path]:
    """Resolve CLI inputs (file, directory, or URL) into a list of extractable file paths."""
    if args.url:
        file_path = download_url(args.url, temp_dir_path)
        if file_path.suffix.lower() not in ALLOWED_EXTENSIONS:
            print_err(
                f"Error: Unsupported file type '{file_path.suffix}'. "
                f"Supported: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
            )
            sys.exit(2)
        return [file_path]

    input_path = Path(args.file_path)
    if not input_path.exists():
        print_err(f"Error: Path not found: {input_path}")
        sys.exit(2)

    if input_path.is_dir():
        files = sorted(
            f for f in input_path.iterdir()
            if f.is_file() and f.suffix.lower() in ALLOWED_EXTENSIONS
        )
        if not files:
            print_err(f"Error: No supported files found in directory {input_path}")
            sys.exit(2)
        return files

    if input_path.suffix.lower() not in ALLOWED_EXTENSIONS:
        print_err(
            f"Error: Unsupported file type '{input_path.suffix}'. "
            f"Supported: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )
        sys.exit(2)
    return [input_path]


def write_output(
    results: list[dict], summaries: list[str], output_path: str | None,
) -> None:
    """Serialize extraction results to stdout or a file, then print summaries."""
    output_json = json.dumps(results[0] if len(results) == 1 else results, indent=2)

    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(output_json)
        print_progress(f"Output written to {output_path}")
    else:
        print(output_json)

    for s in summaries:
        print_err(s)


def handle_schema(type_arg: str) -> None:
    """Print JSON schema for a document type (or all types) to stdout."""
    if type_arg.lower() == "all":
        all_schemas = {}
        for doc_type, model_cls in PAYLOAD_SCHEMA_MAP.items():
            all_schemas[doc_type.value] = model_cls.model_json_schema()
        print(json.dumps(all_schemas, indent=2))
        return

    raw = type_arg.upper()
    try:
        doc_type = DocumentType(raw)
    except ValueError:
        valid = ", ".join(t.value for t in DocumentType)
        print_err(f"Error: Unknown type '{raw}'. Valid: {valid}")
        sys.exit(2)

    if doc_type not in PAYLOAD_SCHEMA_MAP:
        print_err(f"Error: No schema for type '{raw}' (type exists but has no payload model)")
        sys.exit(2)

    print(json.dumps(PAYLOAD_SCHEMA_MAP[doc_type].model_json_schema(), indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Document extraction engine using Google Gemini models."
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("file_path", nargs="?", help="Local file path")
    parser.add_argument("--url", help="Remote URL to download and extract")
    parser.add_argument(
        "--type", help="Skip pass 1 and use the supplied document type directly"
    )
    parser.add_argument(
        "--skip-liteparse",
        action="store_true",
        help="Skip liteparse local text extraction (vision-only)",
    )
    parser.add_argument(
        "--output", help="Write JSON directly to this file instead of stdout"
    )
    parser.add_argument(
        "--pages",
        help="Pages to extract (e.g., '1-3' or '1,3,5'). Only applies to PDFs.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Dump raw LLM response string on validation failure",
    )
    parser.add_argument(
        "--no-summary",
        action="store_true",
        help="Disable the compact one-line summary printed to stderr after each extraction",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show progress messages on stderr (suppressed by default; warnings and errors always shown)",
    )
    parser.add_argument(
        "--format",
        choices=["plain", "markdown"],
        default="plain",
        help="Summary output format: plain (pipe-delimited) or markdown (table row)",
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Classify only (skip extraction pass 2). Print summaries to stderr, no JSON output",
    )
    parser.add_argument(
        "--schema",
        help="Print JSON schema for a document type and exit. Use a TYPE name or 'all'.",
    )

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
            files_to_process = build_files_to_process(args, temp_dir_path)
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
