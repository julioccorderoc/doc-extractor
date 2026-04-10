"""Unit tests for the extraction engine — no API key or real network calls required."""

import datetime
import sys
from unittest.mock import MagicMock, patch

import pytest

import parse_vision
import ingestion
import gemini
from google.genai import errors as genai_errors


# ---------------------------------------------------------------------------
# Minimal APIError subclass for testing
# APIError.__init__(code, response_json, response=None)
# ---------------------------------------------------------------------------


class _FakeAPIError(genai_errors.APIError):
    """Concrete APIError subclass that avoids real HTTP response objects."""

    def __init__(self, code: int):
        super().__init__(code, {"message": "fake error", "status": "TEST_ERROR"})


# ---------------------------------------------------------------------------
# validate_file (now in ingestion module)
# ---------------------------------------------------------------------------


def test_validate_file_exits_2_for_missing_file(tmp_path):
    with pytest.raises(SystemExit) as exc:
        ingestion.validate_file(str(tmp_path / "nonexistent.pdf"))
    assert exc.value.code == 2


def test_validate_file_exits_2_for_unsupported_extension(tmp_path):
    bad_file = tmp_path / "file.xyz"
    bad_file.touch()
    with pytest.raises(SystemExit) as exc:
        ingestion.validate_file(str(bad_file))
    assert exc.value.code == 2


def test_validate_file_accepts_allowed_extensions(tmp_path):
    for ext in (".pdf", ".png", ".jpg", ".jpeg", ".webp"):
        f = tmp_path / f"doc{ext}"
        f.touch()
        result = ingestion.validate_file(str(f))
        assert result == f


def test_validate_file_or_dir_accepts_directory(tmp_path):
    # validate_file only handles files; directories go through main() logic.
    # Verify validate_file rejects a directory path (no extension match).
    with pytest.raises(SystemExit) as exc:
        ingestion.validate_file(str(tmp_path))
    assert exc.value.code == 2


# ---------------------------------------------------------------------------
# build_extraction_prompt_for_type
# ---------------------------------------------------------------------------


def test_build_extraction_prompt_for_type_contains_today():
    from schemas import DocumentType
    from prompts import build_extraction_prompt_for_type

    today = datetime.date.today().isoformat()
    prompt = build_extraction_prompt_for_type(DocumentType.COA)
    assert today in prompt


# ---------------------------------------------------------------------------
# with_retry (now in gemini module)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("code", [429, 500, 503])
def test_with_retry_retries_on_retryable_codes(code):
    failing_fn = MagicMock(side_effect=_FakeAPIError(code))
    with patch("time.sleep"):
        with pytest.raises(_FakeAPIError):
            gemini.with_retry(failing_fn)
    assert failing_fn.call_count == gemini.MAX_RETRIES


@pytest.mark.parametrize("code", [400, 404])
def test_with_retry_does_not_retry_non_retryable_codes(code):
    failing_fn = MagicMock(side_effect=_FakeAPIError(code))
    with pytest.raises(_FakeAPIError):
        gemini.with_retry(failing_fn)
    assert failing_fn.call_count == 1


def test_with_retry_returns_result_on_success():
    succeeding_fn = MagicMock(return_value="ok")
    result = gemini.with_retry(succeeding_fn, "arg1", key="val")
    assert result == "ok"
    succeeding_fn.assert_called_once_with("arg1", key="val")


# ---------------------------------------------------------------------------
# main() — exit code paths
# ---------------------------------------------------------------------------


def test_main_exits_1_when_api_key_unset(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["parse_vision.py", "some_file.pdf"])
    monkeypatch.delenv("GEMINI_DOC_EXTRACTOR_KEY", raising=False)
    with pytest.raises(SystemExit) as exc:
        parse_vision.main()
    assert exc.value.code == 1


# ---------------------------------------------------------------------------
# main() — cleanup always runs in finally
# ---------------------------------------------------------------------------


def test_main_cleanup_runs_on_extraction_failure(tmp_path, monkeypatch):
    """Cleanup must be called even when extract() raises an APIError."""
    dummy_file = tmp_path / "doc.pdf"
    dummy_file.write_bytes(b"%PDF-")
    monkeypatch.setattr(sys, "argv", ["parse_vision.py", str(dummy_file)])
    monkeypatch.setenv("GEMINI_DOC_EXTRACTOR_KEY", "fake-key")

    mock_uploaded = MagicMock()
    mock_client = MagicMock()

    def fake_with_retry(fn, *args, **kwargs):
        if fn is parse_vision.upload_file:
            return mock_uploaded
        if fn is parse_vision.classify:
            raise _FakeAPIError(500)
        return fn(*args, **kwargs)

    with (
        patch("parse_vision.genai.Client", return_value=mock_client),
        patch("parse_vision.with_retry", side_effect=fake_with_retry),
        patch("parse_vision.wait_for_processing", return_value=mock_uploaded),
        patch("parse_vision.cleanup") as mock_cleanup,
    ):
        with pytest.raises(SystemExit) as exc:
            parse_vision.main()

    assert exc.value.code == 3
    mock_cleanup.assert_called_once_with(mock_client, mock_uploaded)


# ---------------------------------------------------------------------------
# model_dump(mode="json") — date serialization
# ---------------------------------------------------------------------------


def test_model_dump_json_mode_serializes_dates():
    """model_dump(mode='json') must convert date objects to ISO strings
    so json.dumps() does not raise TypeError."""
    import json
    from schemas import ExtractionResult, DocumentType

    result = ExtractionResult(
        document_type=DocumentType.COA,
        confidence=0.95,
        extracted_date=datetime.date(2026, 4, 10),
        payload=None,
    )
    dumped = result.model_dump(mode="json")
    # Must not raise TypeError
    serialized = json.dumps(dumped)
    assert "2026-04-10" in serialized


# ---------------------------------------------------------------------------
# download_url (now in ingestion module)
# ---------------------------------------------------------------------------


@patch("ingestion.requests.get")
def test_download_url_success(mock_get, tmp_path):
    mock_resp = MagicMock()
    mock_resp.headers = {"content-disposition": 'attachment; filename="remote_doc.pdf"'}
    mock_resp.iter_content.return_value = [b"pdf content"]
    mock_get.return_value = mock_resp

    dest_path = ingestion.download_url("http://example.com/file", tmp_path)

    assert dest_path == tmp_path / "remote_doc.pdf"
    assert dest_path.read_bytes() == b"pdf content"
    mock_get.assert_called_once_with("http://example.com/file", stream=True, timeout=30)


@patch("ingestion.requests.get")
def test_download_url_fallback_filename(mock_get, tmp_path):
    mock_resp = MagicMock()
    mock_resp.headers = {}
    mock_resp.iter_content.return_value = [b"content"]
    mock_get.return_value = mock_resp

    dest_path = ingestion.download_url(
        "http://example.com/some/path/my_file.pdf", tmp_path
    )

    assert dest_path == tmp_path / "my_file.pdf"
    assert dest_path.read_bytes() == b"content"


# ---------------------------------------------------------------------------
# slice_pdf (now in ingestion module)
# ---------------------------------------------------------------------------


@patch("ingestion.PdfWriter")
@patch("ingestion.PdfReader")
def test_slice_pdf(mock_reader_class, mock_writer_class, tmp_path):
    # Setup mock reader with 5 pages
    mock_reader = MagicMock()
    mock_reader.pages = [
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
    ]
    mock_reader_class.return_value = mock_reader

    # Setup mock writer
    mock_writer = MagicMock()
    mock_writer_class.return_value = mock_writer

    file_path = tmp_path / "original.pdf"
    file_path.touch()

    # Slice to pages 1, 3, and 5 (indices 0, 2, 4)
    dest_path = ingestion.slice_pdf(file_path, "1,3,5", tmp_path)

    assert dest_path == tmp_path / "sliced_original.pdf"
    assert mock_writer.add_page.call_count == 3

    # Slicing with ranges "1-3,5" -> indices 0,1,2, 4
    mock_writer.reset_mock()
    dest_path = ingestion.slice_pdf(file_path, "1-3,5", tmp_path)
    assert mock_writer.add_page.call_count == 4
