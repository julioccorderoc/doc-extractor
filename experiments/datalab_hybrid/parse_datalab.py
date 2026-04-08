"""Datalab Hybrid Extraction Engine.

Pass 1 — Classify using Google Gemini.
Pass 2 — Extract using Datalab.to /extract API.
"""

from __future__ import annotations

import datetime
import json
import os
import sys
import time
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from google import genai
from google.genai import errors as genai_errors
from google.genai.types import GenerateContentConfig

from datalab_sdk.client import DatalabClient
from datalab_sdk.models import ExtractOptions
from datalab_sdk.exceptions import DatalabError

from scripts.prompts import build_classification_prompt
from scripts.schemas import (
    ClassificationResult,
    DocumentType,
    ExtractionResult,
    PAYLOAD_SCHEMA_MAP,
)

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}
DEFAULT_MODEL = "gemini-2.5-flash"
MAX_RETRIES = 3


def print_err(msg: str) -> None:
    print(msg, file=sys.stderr)


def validate_file(file_path: str) -> Path:
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


def classify(
    client: genai.Client, uploaded_file: genai.types.File, model: str
) -> ClassificationResult:
    print_err("Pass 1: classifying document via Gemini...")
    for attempt in range(MAX_RETRIES):
        try:
            response = client.models.generate_content(
                model=model,
                contents=[build_classification_prompt(), uploaded_file],
                config=GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ClassificationResult,
                ),
            )
            return ClassificationResult.model_validate_json(response.text)
        except genai_errors.APIError as e:
            if attempt == MAX_RETRIES - 1:
                raise
            time.sleep(2**attempt)


def extract_datalab(file_path: Path, doc_type: DocumentType) -> dict:
    """Pass 2: Extract using Datalab.to"""
    api_key = os.environ.get("DATALAB_API_KEY")
    if not api_key:
        print_err("Error: DATALAB_API_KEY is not set.")
        sys.exit(1)

    client = DatalabClient(api_key=api_key)
    payload_class = PAYLOAD_SCHEMA_MAP[doc_type]
    json_schema = payload_class.model_json_schema()

    print_err(f"Pass 2: extracting {doc_type.value} fields via Datalab...")
    options = ExtractOptions(page_schema=json.dumps(json_schema))

    try:
        result = client.extract(
            file_path=str(file_path), options=options, max_polls=600, poll_interval=2
        )

        if hasattr(result, "extraction_schema_json") and result.extraction_schema_json:
            # Datalab sometimes returns the JSON string in 'extraction_schema_json'
            extracted = json.loads(result.extraction_schema_json)
            # The structure might be nested under the schema's title
            title = json_schema.get("title", "")
            if title and title in extracted:
                return extracted[title]
            return extracted
        elif hasattr(result, "json") and result.json is not None:
            extracted = result.json
            title = json_schema.get("title", "")
            if title and title in extracted:
                return extracted[title]
            return extracted
        elif hasattr(result, "data") and result.data is not None:
            if isinstance(result.data, str):
                extracted = json.loads(result.data)
            else:
                extracted = result.data
            title = json_schema.get("title", "")
            if title and title in extracted:
                return extracted[title]
            return extracted
        else:
            # Let's inspect the object closely
            # wait, Datalab's conversion response might have result.conversion.json or similar?
            if hasattr(result, "json") and result.json:
                return result.json
            elif getattr(result, "output_format", "") == "json" and hasattr(
                result, "json"
            ):
                return result.json
            elif getattr(result, "output_format", "") == "json" and hasattr(
                result, "markdown"
            ):
                # some older versions store JSON string in markdown attribute
                if isinstance(result.markdown, str):
                    try:
                        return json.loads(result.markdown)
                    except:
                        pass

            print_err("Warning: Datalab result doesn't have 'json' attribute.")
            print_err(f"Result type: {type(result)}")
            print_err(f"Result dir: {dir(result)}")
            if hasattr(result, "model_dump"):
                return result.model_dump()
            elif hasattr(result, "__dict__"):
                return result.__dict__
            return result
    except Exception as e:
        print_err(f"Datalab extraction error: {e}")
        sys.exit(3)


def main() -> None:
    import sys

    args = sys.argv[1:]
    hint_type: DocumentType | None = None

    # Handle basic args
    if "--use-liteparse" in args:
        args.remove("--use-liteparse")

    if "--type" in args:
        idx = args.index("--type")
        if idx + 1 >= len(args):
            sys.exit(2)
        raw_type = args[idx + 1].upper()
        try:
            hint_type = DocumentType(raw_type)
        except ValueError:
            sys.exit(2)
        args = args[:idx] + args[idx + 2 :]

    if len(args) != 1:
        sys.exit(2)

    file_path = validate_file(args[0])

    gemini_key = os.environ.get("GEMINI_DOC_EXTRACTOR_KEY")
    if not gemini_key:
        print_err("Error: GEMINI_DOC_EXTRACTOR_KEY is not set.")
        sys.exit(1)

    gemini_client = genai.Client(api_key=gemini_key)
    model = os.environ.get("GEMINI_MODEL", DEFAULT_MODEL)

    uploaded_file = None
    try:
        if hint_type is not None:
            doc_type = hint_type
            confidence = 1.0
            print_err(f"Using caller-supplied type: {doc_type.value}")
        else:
            import scripts.prompts
            import scripts.schemas
            import sys

            if "prompts" not in sys.modules:
                sys.modules["prompts"] = scripts.prompts
            if "schemas" not in sys.modules:
                sys.modules["schemas"] = scripts.schemas
            from scripts.parse_vision import upload_file, wait_for_processing

            print_err(f"Uploading {file_path.name}...")
            uploaded_file = upload_file(gemini_client, file_path)
            uploaded_file = wait_for_processing(gemini_client, uploaded_file)
            classification = classify(gemini_client, uploaded_file, model)
            doc_type = classification.document_type
            confidence = classification.confidence
            print_err(f"Classified as: {doc_type.value} (confidence: {confidence:.2f})")

        payload = None
        if doc_type in PAYLOAD_SCHEMA_MAP:
            raw_payload = extract_datalab(file_path, doc_type)
            payload_class = PAYLOAD_SCHEMA_MAP[doc_type]

            # Map enum values to strings if Datalab returned names instead of values
            if (
                doc_type == DocumentType.COA
                and isinstance(raw_payload, dict)
                and "test_results" in raw_payload
            ):
                operator_map = {
                    "EQ": "=",
                    "LT": "<",
                    "GT": ">",
                    "LTE": "<=",
                    "GTE": ">=",
                    "ND": "ND",
                    "ABSENT": "ABSENT",
                    "CONFORMS": "CONFORMS",
                }
                for result in raw_payload.get("test_results", []):
                    if (
                        "result_operator" in result
                        and result["result_operator"] in operator_map
                    ):
                        result["result_operator"] = operator_map[
                            result["result_operator"]
                        ]

            if isinstance(raw_payload, str):
                payload = payload_class.model_validate_json(raw_payload)
            else:
                payload = payload_class.model_validate(raw_payload)

        result = ExtractionResult(
            document_type=doc_type,
            confidence=confidence,
            extracted_date=datetime.date.today().isoformat(),
            payload=payload,
        )
        print(result.model_dump_json(indent=2))

    finally:
        if uploaded_file is not None:
            from scripts.parse_vision import cleanup

            cleanup(gemini_client, uploaded_file)


if __name__ == "__main__":
    main()
