"""Gemini API interaction: upload, wait, classify, extract, cleanup, and retry logic."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable, TypeVar

from google import genai
from google.genai import errors as genai_errors
from google.genai.types import GenerateContentConfig

from _output import print_err, print_progress
from prompts import build_classification_prompt, build_extraction_prompt_for_type
from schemas import ClassificationResult, DocumentType

MAX_RETRIES = 3
RETRYABLE_CODES = {429, 500, 503}
UPLOAD_TIMEOUT_SECS = 300  # 5 minutes max for file processing

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
    raise RuntimeError("unreachable: with_retry exhausted loop without returning")


def upload_file(client: genai.Client, file_path: Path) -> genai.types.File:
    """Upload a file to Google's storage. Returns immediately after upload."""
    print_progress(f"Uploading {file_path.name}...")
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
        print_progress("Waiting for file processing...")
        time.sleep(2)
        uploaded = client.files.get(name=uploaded.name)

    if uploaded.state.name == "FAILED":
        raise RuntimeError(f"File processing failed: {uploaded.name}")

    print_progress(f"File ready: {uploaded.name}")
    return uploaded


def classify(
    client: genai.Client, uploaded_file: genai.types.File, model: str
) -> ClassificationResult:
    """Pass 1: classify document type. Cheap call with a minimal response schema."""
    print_progress("Pass 1: classifying document...")
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
    payload_class: type,
    text_context: str | None = None,
) -> str:
    """Pass 2: extract payload using the exact schema for the classified type."""
    print_progress(f"Pass 2: extracting {doc_type.value} fields...")

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
        print_progress(f"Cleaned up: {uploaded_file.name}")
    except genai_errors.APIError as e:
        print_err(f"Warning: Cleanup failed: {e}")
