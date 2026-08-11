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

QUOTA_MARKERS = ("resource_exhausted", "quota", "billing", "free tier")
"""A 429 carries two different meanings that need opposite responses.

Per-minute rate limiting clears in seconds, so a short backoff is right. A daily
or project quota does not clear inside a run at all — retrying 1s/2s/4s against
it burns the attempts and then reports the wrong cause. These markers split them.
"""

QUOTA_BACKOFF_SECS = (30, 90)
"""Longer waits for a quota 429, still bounded: a hard wall needs a human, not
more waiting. The caller gets QuotaExceeded and can stop the batch."""

T = TypeVar("T")


class QuotaExceeded(Exception):
    """A 429 that is a quota wall rather than transient rate limiting.

    Distinct from a bare APIError so a batch driver can circuit-break the whole
    run instead of discovering the same wall once per remaining document.
    """


def _is_quota_error(err: genai_errors.APIError) -> bool:
    blob = f"{getattr(err, 'message', '')} {getattr(err, 'status', '')}".lower()
    return err.code == 429 and any(marker in blob for marker in QUOTA_MARKERS)


class UsageTally:
    """Accumulates billed tokens across the passes made for one document.

    Passed into `classify` and `extract_typed` rather than returned from them,
    so a retried call adds its real cost instead of overwriting the first
    attempt's — every attempt is billed, and a caller reading cost needs the
    sum, not the last one.

    `seen` stays False when the API reports no usage metadata at all, which is
    how the caller distinguishes "no usage reported" from "zero tokens".
    """

    def __init__(self) -> None:
        self.prompt_tokens = 0
        self.output_tokens = 0
        self.total_tokens = 0
        self.calls = 0
        self.seen = False

    def add(self, response: Any) -> None:
        """Fold one API response's usage metadata into the tally."""
        self.calls += 1
        meta = getattr(response, "usage_metadata", None)
        if meta is None:
            return
        self.seen = True
        self.prompt_tokens += getattr(meta, "prompt_token_count", None) or 0
        self.output_tokens += getattr(meta, "candidates_token_count", None) or 0
        self.total_tokens += getattr(meta, "total_token_count", None) or 0


def with_retry(fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """Execute fn with backoff for retryable API errors (429, 500, 503).

    Quota 429s get their own longer, shorter-count ladder and then surface as
    QuotaExceeded, so the caller can tell "the service hiccuped" apart from
    "there is no budget left" without grepping stderr.
    """
    for attempt in range(MAX_RETRIES):
        try:
            return fn(*args, **kwargs)
        except genai_errors.APIError as e:
            quota = _is_quota_error(e)
            if quota:
                if attempt >= len(QUOTA_BACKOFF_SECS):
                    raise QuotaExceeded(
                        f"quota exhausted after {attempt} waits: {e.message}"
                    ) from e
                wait = QUOTA_BACKOFF_SECS[attempt]
                print_err(
                    f"Quota error {e.code}, waiting {wait}s "
                    f"(attempt {attempt + 1}/{len(QUOTA_BACKOFF_SECS) + 1})..."
                )
            else:
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
    client: genai.Client,
    uploaded_file: genai.types.File,
    model: str,
    tally: UsageTally | None = None,
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
    if tally is not None:
        tally.add(response)
    return ClassificationResult.model_validate_json(response.text)


def extract_typed(
    client: genai.Client,
    uploaded_file: genai.types.File,
    model: str,
    doc_type: DocumentType,
    payload_class: type,
    text_context: str | None = None,
    tally: UsageTally | None = None,
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
    if tally is not None:
        tally.add(response)
    return response.text


def cleanup(client: genai.Client, uploaded_file: genai.types.File) -> None:
    """Delete the uploaded file from Google's storage."""
    try:
        client.files.delete(name=uploaded_file.name)
        print_progress(f"Cleaned up: {uploaded_file.name}")
    except genai_errors.APIError as e:
        print_err(f"Warning: Cleanup failed: {e}")
