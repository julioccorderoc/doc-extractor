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

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}
DEFAULT_MODEL = "gemini-2.5-flash"
MAX_RETRIES = 3
RETRYABLE_CODES = {429, 500, 503}
UPLOAD_TIMEOUT_SECS = 300  # 5 minutes max for file processing


def print_err(msg: str) -> None:
    """Print to stderr (stdout is reserved for JSON output)."""
    print(msg, file=sys.stderr)


def validate_file(file_path: str) -> Path:
    """Validate that the file exists and has an allowed extension."""
    path = Path(file_path)
    if not path.exists():
        print_err(f"Error: File not found: {file_path}")
        sys.exit(2)
    if path.suffix.lower() not in ALLOWED_EXTENSIONS:
        print_err(
            f"Error: Unsupported file type '{path.suffix}'. "
            f"Supported: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )
        sys.exit(2)
    return path


def with_retry(fn, *args, **kwargs):
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
    except Exception as e:
        print_err(f"Warning: Cleanup failed: {e}")


def main() -> None:
    # Parse args: <file_path> [--type TYPE] [--use-liteparse]
    args = sys.argv[1:]
    hint_type: DocumentType | None = None
    use_liteparse: bool = False

    if "--use-liteparse" in args:
        use_liteparse = True
        args.remove("--use-liteparse")

    if "--type" in args:
        idx = args.index("--type")
        if idx + 1 >= len(args):
            print_err("Error: --type requires a document type value.")
            sys.exit(2)
        raw_type = args[idx + 1].upper()
        try:
            hint_type = DocumentType(raw_type)
        except ValueError:
            valid = ", ".join(t.value for t in DocumentType)
            print_err(f"Error: Unknown document type '{raw_type}'. Valid: {valid}")
            sys.exit(2)
        args = args[:idx] + args[idx + 2 :]

    if len(args) != 1:
        print_err(
            "Usage: python scripts/parse_vision.py <file_path> [--type TYPE] [--use-liteparse]"
        )
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

    file_path = validate_file(args[0])
    client = genai.Client(api_key=api_key)

    # Extract text locally if requested
    text_context: str | None = None
    if use_liteparse:
        try:
            from liteparse import LiteParse
            print_err("Extracting local text context via liteparse...")
            lp = LiteParse()
            lp_result = lp.parse(str(file_path))
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
        uploaded_file = with_retry(upload_file, client, file_path)
        uploaded_file = wait_for_processing(client, uploaded_file)

        # Pass 1 — classify (skip if caller supplied --type)
        if hint_type is not None:
            doc_type = hint_type
            confidence = 1.0
            print_err(f"Using caller-supplied type: {doc_type.value}")
        else:
            classification = with_retry(classify, client, uploaded_file, model)
            doc_type = classification.document_type
            confidence = classification.confidence
            print_err(f"Classified as: {doc_type.value} (confidence: {confidence:.2f})")

        # Pass 2 — extract with the specific schema (skip for UNKNOWN)
        payload = None
        if doc_type in PAYLOAD_SCHEMA_MAP:
            payload_json = with_retry(
                extract_typed, client, uploaded_file, model, doc_type, text_context
            )
            payload = PAYLOAD_SCHEMA_MAP[doc_type].model_validate_json(payload_json)

        result = ExtractionResult(
            document_type=doc_type,
            confidence=confidence,
            extracted_date=datetime.date.today().isoformat(),
            payload=payload,
        )
        print(result.model_dump_json(indent=2))

    except genai_errors.APIError as e:
        print_err(
            f"Error: API failure after {MAX_RETRIES} retries "
            f"(HTTP {e.code}): {e.message}"
        )
        sys.exit(3)
    except TimeoutError as e:
        print_err(f"Error: {e}")
        sys.exit(3)
    except RuntimeError as e:
        print_err(f"Error: {e}")
        sys.exit(3)
    finally:
        if uploaded_file is not None:
            cleanup(client, uploaded_file)


if __name__ == "__main__":
    main()
