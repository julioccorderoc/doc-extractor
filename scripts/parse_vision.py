"""Document extraction engine using Google Gemini/Gemma models.

Usage:
    python scripts/parse_vision.py <absolute_file_path>

Exit codes:
    0 - Success (JSON printed to stdout)
    1 - Missing GEMINI_DOC_EXTRACTOR_KEY
    2 - Bad file type or file not found
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

from schemas import ExtractionResult

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}
DEFAULT_MODEL = "gemini-2.5-flash"
MAX_RETRIES = 3
RETRYABLE_CODES = {429, 500, 503}
UPLOAD_TIMEOUT_SECS = 300  # 5 minutes max for file processing


def build_extraction_prompt() -> str:
    """Build the extraction prompt with today's date injected to fix extracted_date accuracy."""
    today = datetime.date.today().isoformat()
    return f"""\
You are a document data extractor for supply chain documents.
Today's date is {today}.

STEP 1 — CLASSIFY. Choose document_type from exactly one of:
  COA, INVOICE, QUOTE, PRODUCT_SPEC_SHEET, PACKAGING_SPEC_SHEET, LABEL, UNKNOWN

STEP 2 — EXTRACT. Populate ONLY the payload fields for the classified document type.
Set all other payload fields to null. Do not mix fields from different document types.

STEP 3 — Set extracted_date to today's date: {today}
This is the date of extraction, NOT the date printed on the document.

FIELD RULES (all dates must be YYYY-MM-DD format):

COA — Certificate of Analysis:
  date, manufacturer_name, product_name, lot_number, expiration_date,
  test_results[] (extract every row: test_name, method, specification, result, pass_fail_status)

INVOICE — Invoice or Sales Order:
  date, vendor_name, invoice_number, po_number,
  line_items[] (description, quantity, unit_price, total), grand_total
  Sales orders should also be classified as INVOICE.

QUOTE — Quote or RFQ:
  date, vendor_name, quote_number, line_items[], total

PRODUCT_SPEC_SHEET — Product specification sheet:
  date, manufacturer_name, product_name, product_code, product_description,
  product_formula[] (ingredient, amount, unit), count, servings

PACKAGING_SPEC_SHEET — Packaging specification sheet:
  All PRODUCT_SPEC_SHEET fields PLUS:
  packaging_components[] (component_name, description),
  label_specs, closure_specs, bottle_specs, carton_specs, pallet_specs (one string per spec)

LABEL — Product label or label artwork:
  brand, product_name, barcode, version, count, servings,
  supplements_fact_panel[] (ingredient, amount_per_serving, daily_value_percent),
  other_ingredients, allergens, company (name, address, email, phone),
  suggested_use, marketing_text
  If the label artwork has no readable text, return UNKNOWN instead.

UNKNOWN — Unclassifiable or unreadable:
  Set payload to null.
  Populate raw_text_fallback with all readable text found in the document.

GENERAL RULES:
- Extract exactly what the document says. Do not infer or fabricate data.
- If a field cannot be found, set it to null.
- confidence: 1.0 = certain classification, 0.0 = total guess. Be honest.
"""


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
            wait = 2 ** attempt  # 1s, 2s, 4s
            print_err(
                f"API error {e.code}, retrying in {wait}s "
                f"(attempt {attempt + 1}/{MAX_RETRIES})..."
            )
            time.sleep(wait)


def upload_file(client: genai.Client, file_path: Path) -> genai.types.File:
    """Upload a file to Google's storage. Returns immediately after upload."""
    print_err(f"Uploading {file_path.name}...")
    return client.files.upload(file=str(file_path))


def wait_for_processing(client: genai.Client, uploaded: genai.types.File) -> genai.types.File:
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


def extract(client: genai.Client, uploaded_file: genai.types.File, model: str) -> str:
    """Run inference to classify and extract document data."""
    print_err(f"Running extraction with model: {model}")

    response = client.models.generate_content(
        model=model,
        contents=[build_extraction_prompt(), uploaded_file],
        config=GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ExtractionResult,
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
    if len(sys.argv) != 2:
        print_err("Usage: python scripts/parse_vision.py <file_path>")
        sys.exit(2)

    # Validate API key
    api_key = os.environ.get("GEMINI_DOC_EXTRACTOR_KEY")
    if not api_key:
        print_err(
            "Error: GEMINI_DOC_EXTRACTOR_KEY is not set.\n"
            "Get a key at https://aistudio.google.com/apikey and run:\n"
            "  export GEMINI_DOC_EXTRACTOR_KEY='your-key-here'"
        )
        sys.exit(1)

    # Validate file
    file_path = validate_file(sys.argv[1])

    # Initialize client
    client = genai.Client(api_key=api_key)
    model = os.environ.get("GEMINI_MODEL", DEFAULT_MODEL)

    # Upload is split from processing so cleanup always runs once we have a file ref.
    uploaded_file = None
    try:
        uploaded_file = with_retry(upload_file, client, file_path)
        uploaded_file = wait_for_processing(client, uploaded_file)
        result_json = with_retry(extract, client, uploaded_file, model)
        parsed = ExtractionResult.model_validate_json(result_json)
        print(parsed.model_dump_json(indent=2))
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
