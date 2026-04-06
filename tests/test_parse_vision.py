"""Unit tests for parse_vision.py — no API key or real network calls required."""

import datetime
import sys
from unittest.mock import MagicMock, patch

import pytest

import parse_vision
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
# validate_file
# ---------------------------------------------------------------------------


def test_validate_file_exits_2_for_missing_file(tmp_path):
    with pytest.raises(SystemExit) as exc:
        parse_vision.validate_file(str(tmp_path / "nonexistent.pdf"))
    assert exc.value.code == 2


def test_validate_file_exits_2_for_unsupported_extension(tmp_path):
    bad_file = tmp_path / "document.txt"
    bad_file.write_text("hello")
    with pytest.raises(SystemExit) as exc:
        parse_vision.validate_file(str(bad_file))
    assert exc.value.code == 2


def test_validate_file_accepts_allowed_extensions(tmp_path):
    for ext in (".pdf", ".png", ".jpg", ".jpeg", ".webp"):
        f = tmp_path / f"doc{ext}"
        f.write_bytes(b"\x00")
        path = parse_vision.validate_file(str(f))
        assert path == f


# ---------------------------------------------------------------------------
# build_extraction_prompt
# ---------------------------------------------------------------------------


def test_build_extraction_prompt_contains_today():
    today = datetime.date.today().isoformat()
    prompt = parse_vision.build_extraction_prompt()
    assert today in prompt


# ---------------------------------------------------------------------------
# with_retry
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("code", [429, 500, 503])
def test_with_retry_retries_on_retryable_codes(code):
    failing_fn = MagicMock(side_effect=_FakeAPIError(code))
    with patch("time.sleep"):
        with pytest.raises(_FakeAPIError):
            parse_vision.with_retry(failing_fn)
    assert failing_fn.call_count == parse_vision.MAX_RETRIES


@pytest.mark.parametrize("code", [400, 404])
def test_with_retry_does_not_retry_non_retryable_codes(code):
    failing_fn = MagicMock(side_effect=_FakeAPIError(code))
    with pytest.raises(_FakeAPIError):
        parse_vision.with_retry(failing_fn)
    assert failing_fn.call_count == 1


def test_with_retry_returns_result_on_success():
    succeeding_fn = MagicMock(return_value="ok")
    result = parse_vision.with_retry(succeeding_fn, "arg1", key="val")
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
        if fn is parse_vision.extract:
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
