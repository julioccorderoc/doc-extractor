"""Document extraction engine using Google Gemini/Gemma models.

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
import time
from pathlib import Path
import argparse
import pydantic
import requests
import tempfile
import urllib.parse
from pypdf import PdfReader, PdfWriter

from typing import Any, Callable, TypeVar

from google import genai
from google.genai import errors as genai_errors
from google.genai.types import GenerateContentConfig

from prompts import build_classification_prompt, build_extraction_prompt_for_type
from schemas import (
    ClassificationResult,
    DocumentType,
    ExtractionResult,
    PAYLOAD_SCHEMA_MAP,
)

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".xlsx", ".docx", ".txt", ".md", ".csv"}
DEFAULT_MODEL = "gemini-3.1-pro-preview"
MAX_RETRIES = 3
RETRYABLE_CODES = {429, 500, 503}
UPLOAD_TIMEOUT_SECS = 300  # 5 minutes max for file processing


def print_err(msg: str) -> None:
    """Print to stderr (stdout is reserved for JSON output)."""
    print(msg, file=sys.stderr)



def preprocess_file(file_path: Path, temp_dir: Path) -> Path:
    """Convert unsupported formats (.xlsx, .docx, .csv) to markdown text using MarkItDown."""
    if file_path.suffix.lower() in {".xlsx", ".docx", ".csv"}:
        print_err(f"Converting {file_path.suffix} to markdown via MarkItDown...")
        try:
            from markitdown import MarkItDown
            md = MarkItDown()
            result = md.convert(str(file_path))
            md_path = temp_dir / f"{file_path.stem}.txt"
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(result.text_content)
            return md_path
        except ImportError:
            print_err("Error: markitdown is required to process .xlsx/.docx/.csv files. (uv add markitdown)")
            sys.exit(2)
        except Exception as e:
            print_err(f"Error converting file: {e}")
            sys.exit(2)
    return file_path


def download_url(url: str, dest_dir: Path) -> Path:
    print_err(f"Downloading {url}...")
    try:
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        
        # Try to get filename from Content-Disposition or URL
        filename = "downloaded_file.pdf"
        if "content-disposition" in response.headers:
            cd = response.headers["content-disposition"]
            if "filename=" in cd:
                filename = cd.split("filename=")[1].strip('"\'')
        else:
            parsed = urllib.parse.urlparse(url)
            if parsed.path:
                name = parsed.path.split("/")[-1]
                if name:
                    filename = name
                    
        dest_path = dest_dir / filename
        with open(dest_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                
        return dest_path
    except Exception as e:
        print_err(f"Error downloading URL: {e}")
        sys.exit(2)


def slice_pdf(file_path: Path, pages_spec: str, dest_dir: Path) -> Path:
    print_err(f"Slicing PDF to pages: {pages_spec}")
    try:
        reader = PdfReader(file_path)
        writer = PdfWriter()
        
        # Parse pages_spec: "1-3", "1,3,5"
        pages_to_keep = set()
        for part in pages_spec.split(","):
            part = part.strip()
            if "-" in part:
                start, end = part.split("-")
                start_idx = int(start) - 1
                end_idx = int(end) - 1
                for i in range(start_idx, end_idx + 1):
                    pages_to_keep.add(i)
            else:
                pages_to_keep.add(int(part) - 1)
        
        num_pages = len(reader.pages)
        added_any = False
        for i in sorted(pages_to_keep):
            if 0 <= i < num_pages:
                writer.add_page(reader.pages[i])
                added_any = True
            else:
                print_err(f"Warning: Page {i + 1} is out of range (PDF has {num_pages} pages).")
                
        if not added_any:
            print_err("Error: No valid pages selected for slicing.")
            sys.exit(2)
            
        dest_path = dest_dir / f"sliced_{file_path.name}"
        with open(dest_path, "wb") as f:
            writer.write(f)
            
        return dest_path
    except Exception as e:
        print_err(f"Error slicing PDF: {e}")
        sys.exit(2)

T = TypeVar("T")


def with_retry(fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """Execute fn with exponential backoff for retryable API errors (429, 500, 503)."""
    for attempt in range(MAX_RETRIES):
        try:
            return fn(*args, **kwargs)
        except genai_errors.APIError as e:
            if e.code not in RETRYABLE_CODES or attempt == MAX_RETRIES - 1:
                raise
            wait = 2**attempt  # 1s, 2s, 4s
            print_err(
                f"API error {e.code}, retrying in {wait}s "
                f"(attempt {attempt + 1}/{MAX_RETRIES})..."
            )
            time.sleep(wait)


def upload_file(client: genai.Client, file_path: Path) -> genai.types.File:
    """Upload a file to Google's storage. Returns immediately after upload."""
    print_err(f"Uploading {file_path.name}...")
    return client.files.upload(file=str(file_path))


def wait_for_processing(
    client: genai.Client, uploaded: genai.types.File
) -> genai.types.File:
    """Poll until the uploaded file finishes processing. Raises on failure or timeout."""
    deadline = time.monotonic() + UPLOAD_TIMEOUT_SECS
    while uploaded.state.name == "PROCESSING":
        if time.monotonic() > deadline:
            raise TimeoutError(
                f"File processing timed out after {UPLOAD_TIMEOUT_SECS}s"
            )
        print_err("Waiting for file processing...")
        time.sleep(2)
        uploaded = client.files.get(name=uploaded.name)

    if uploaded.state.name == "FAILED":
        raise RuntimeError(f"File processing failed: {uploaded.name}")

    print_err(f"File ready: {uploaded.name}")
    return uploaded


def classify(
    client: genai.Client, uploaded_file: genai.types.File, model: str
) -> ClassificationResult:
    """Pass 1: classify document type. Cheap call with a minimal response schema."""
    print_err("Pass 1: classifying document...")
    response = client.models.generate_content(
        model=model,
        contents=[build_classification_prompt(), uploaded_file],
        config=GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ClassificationResult,
        ),
    )
    return ClassificationResult.model_validate_json(response.text)


def extract_typed(
    client: genai.Client,
    uploaded_file: genai.types.File,
    model: str,
    doc_type: DocumentType,
    text_context: str | None = None,
) -> str:
    """Pass 2: extract payload using the exact schema for the classified type."""
    print_err(f"Pass 2: extracting {doc_type.value} fields...")
    payload_class = PAYLOAD_SCHEMA_MAP[doc_type]

    contents = [
        build_extraction_prompt_for_type(doc_type, has_text_context=bool(text_context)),
        uploaded_file,
    ]
    if text_context:
        contents.append(f"PRE-PROCESSED TEXT EXTRACTION:\n{text_context}")

    response = client.models.generate_content(
        model=model,
        contents=contents,
        config=GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=payload_class,
        ),
    )
    return response.text


def cleanup(client: genai.Client, uploaded_file: genai.types.File) -> None:
    """Delete the uploaded file from Google's storage."""
    try:
        client.files.delete(name=uploaded_file.name)
        print_err(f"Cleaned up: {uploaded_file.name}")
    except genai_errors.APIError as e:
        print_err(f"Warning: Cleanup failed: {e}")



def process_single_file(
    file_path: Path,
    client: genai.Client,
    model: str,
    hint_type: DocumentType | None,
    args: argparse.Namespace,
    temp_dir_path: Path
) -> ExtractionResult | None:
    # 1. Preprocess (Convert .xlsx/.docx to .txt)
    processed_path = preprocess_file(file_path, temp_dir_path)

    # 2. Slice PDF if requested
    if args.pages:
        if processed_path.suffix.lower() == ".pdf":
            processed_path = slice_pdf(processed_path, args.pages, temp_dir_path)
        else:
            print_err(f"Warning: --pages only applies to PDF files. Ignoring for {processed_path.name}")

    # 3. Extract text locally if requested
    text_context: str | None = None
    if args.use_liteparse:
        try:
            from liteparse import LiteParse
            print_err(f"Extracting local text context for {processed_path.name} via liteparse...")
            lp = LiteParse()
            lp_result = lp.parse(str(processed_path))
            if hasattr(lp_result, "text") and lp_result.text.strip():
                text_context = lp_result.text
            else:
                print_err("Warning: liteparse returned empty text.")
        except ImportError:
            print_err("Warning: liteparse is not installed. Skipping local text extraction.")
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
            print_err(f"Using caller-supplied type: {doc_type.value}")
        else:
            classification = with_retry(classify, client, uploaded_file, model)
            doc_type = classification.document_type
            confidence = classification.confidence
            print_err(f"Classified as: {doc_type.value} (confidence: {confidence:.2f})")

        # Pass 2 — extract with specific schema
        payload = None
        if doc_type in PAYLOAD_SCHEMA_MAP:
            payload_json = with_retry(
                extract_typed, client, uploaded_file, model, doc_type, text_context
            )
            try:
                payload = PAYLOAD_SCHEMA_MAP[doc_type].model_validate_json(payload_json)
            except pydantic.ValidationError as e:
                if args.debug:
                    print_err(f"\n--- DEBUG: RAW LLM RESPONSE ---\n{payload_json}\n--- END DEBUG ---\n")
                raise e

        return ExtractionResult(
            document_type=doc_type,
            confidence=confidence,
            extracted_date=datetime.date.today().isoformat(),
            payload=payload,
        )

    except genai_errors.APIError as e:
        print_err(f"Error processing {file_path.name}: API failure after {MAX_RETRIES} retries (HTTP {e.code}): {e.message}")
        return None
    except Exception as e:
        print_err(f"Error processing {file_path.name}: {e}")
        return None
    finally:
        if uploaded_file is not None:
            cleanup(client, uploaded_file)


def main() -> None:
    parser = argparse.ArgumentParser(description="Document extraction engine using Google Gemini/Gemma models.")
    parser.add_argument("file_path", nargs="?", help="Local file path")
    parser.add_argument("--url", help="Remote URL to download and extract")
    parser.add_argument("--type", help="Skip pass 1 and use the supplied document type directly")
    parser.add_argument("--use-liteparse", action="store_true", help="Use liteparse for local text extraction")
    parser.add_argument("--output", help="Write JSON directly to this file instead of stdout")
    parser.add_argument("--pages", help="Pages to extract (e.g., '1-3' or '1,3,5'). Only applies to PDFs.")
    parser.add_argument("--debug", action="store_true", help="Dump raw LLM response string on validation failure")

    args = parser.parse_args()

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
    is_gemma = model.lower().startswith("gemma")
    if is_gemma:
        api_key = os.environ.get("GEMMA_FREE_API")
        if not api_key:
            print_err(
                f"Error: GEMMA_FREE_API is not set (required for Gemma models).\n"
                f"Gemma models only work on free-tier accounts. Get a free key at\n"
                f"https://aistudio.google.com/apikey and run:\n"
                f"  export GEMMA_FREE_API='your-free-key-here'"
            )
            sys.exit(1)
    else:
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

        files_to_process = []
        if args.url:
            file_path = download_url(args.url, temp_dir_path)
            if file_path.suffix.lower() not in ALLOWED_EXTENSIONS:
                print_err(f"Error: Unsupported file type '{file_path.suffix}'. Supported: {', '.join(sorted(ALLOWED_EXTENSIONS))}")
                sys.exit(2)
            files_to_process.append(file_path)
        else:
            input_path = Path(args.file_path)
            if not input_path.exists():
                print_err(f"Error: Path not found: {input_path}")
                sys.exit(2)
            
            if input_path.is_dir():
                for f in input_path.iterdir():
                    if f.is_file() and f.suffix.lower() in ALLOWED_EXTENSIONS:
                        files_to_process.append(f)
                if not files_to_process:
                    print_err(f"Error: No supported files found in directory {input_path}")
                    sys.exit(2)
                # Sort files to ensure deterministic output order
                files_to_process.sort()
            else:
                if input_path.suffix.lower() not in ALLOWED_EXTENSIONS:
                    print_err(f"Error: Unsupported file type '{input_path.suffix}'. Supported: {', '.join(sorted(ALLOWED_EXTENSIONS))}")
                    sys.exit(2)
                files_to_process.append(input_path)

        results = []
        for fp in files_to_process:
            res = process_single_file(fp, client, model, hint_type, args, temp_dir_path)
            if res:
                res_dict = res.model_dump()
                res_dict["source_file"] = fp.name
                results.append(res_dict)

        import json
        if len(results) == 1:
            output_json = json.dumps(results[0], indent=2)
        else:
            output_json = json.dumps(results, indent=2)

        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output_json)
            print_err(f"Output successfully written to {args.output}")
        else:
            print(output_json)

        if not results:
            print_err("No files were successfully processed.")
            sys.exit(3)

if __name__ == "__main__":
    main()
