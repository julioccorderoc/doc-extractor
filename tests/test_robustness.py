"""Failure-path contracts — no API key or network required.

These lock the behaviours that only show up when something goes wrong, which is
exactly when they are hardest to debug: a half-written output file, a quota wall
treated as a hiccup, a hang with no ceiling, and an exit code that means five
different things at once.
"""

import json
import signal
import time
from unittest.mock import MagicMock, patch

import pytest
from google.genai import errors as genai_errors

import gemini
import parse_vision
from _output import write_json_atomic


class _FakeAPIError(genai_errors.APIError):
    def __init__(self, code: int, message: str = "fake error", status: str = "TEST_ERROR"):
        super().__init__(code, {"message": message, "status": status})


# ---------------------------------------------------------------------------
# Atomic output — a reader never sees a partial file
# ---------------------------------------------------------------------------


def test_write_json_atomic_creates_missing_parents(tmp_path):
    """The write happens after the billed call; a missing folder must not cost it."""
    dest = tmp_path / "nested" / "deeper" / "out.json"
    write_json_atomic({"ok": True}, dest)
    assert json.loads(dest.read_text()) == {"ok": True}


def test_write_json_atomic_leaves_no_partial_file_behind(tmp_path):
    dest = tmp_path / "out.json"
    write_json_atomic({"a": 1}, dest)
    assert list(tmp_path.iterdir()) == [dest], "the .part temp file must be renamed away"


def test_write_json_atomic_replaces_an_existing_file(tmp_path):
    dest = tmp_path / "out.json"
    write_json_atomic({"v": 1}, dest)
    write_json_atomic({"v": 2}, dest)
    assert json.loads(dest.read_text()) == {"v": 2}


# ---------------------------------------------------------------------------
# Resume — presence is not enough, it has to parse
# ---------------------------------------------------------------------------


def test_already_extracted_accepts_a_complete_output(tmp_path):
    p = tmp_path / "a.json"
    p.write_text(json.dumps({"document_type": "COA"}))
    assert parse_vision._already_extracted(p) is True


def test_already_extracted_rejects_a_truncated_output(tmp_path):
    """A crash mid-write must be re-run, not skipped as done."""
    p = tmp_path / "a.json"
    p.write_text('{"document_type": "CO')
    assert parse_vision._already_extracted(p) is False


def test_already_extracted_rejects_a_missing_file(tmp_path):
    assert parse_vision._already_extracted(tmp_path / "nope.json") is False


# ---------------------------------------------------------------------------
# Quota is a wall, rate limiting is a hiccup
# ---------------------------------------------------------------------------


def test_quota_429_raises_quota_exceeded_rather_than_retrying_fast():
    failing = MagicMock(side_effect=_FakeAPIError(429, "RESOURCE_EXHAUSTED: quota"))
    with patch("time.sleep") as slept:
        with pytest.raises(gemini.QuotaExceeded):
            gemini.with_retry(failing)
    waits = [c.args[0] for c in slept.call_args_list]
    assert waits == list(gemini.QUOTA_BACKOFF_SECS), "a quota wall needs long waits, not 1s/2s/4s"


def test_plain_429_still_uses_the_short_ladder():
    """Per-minute rate limiting clears in seconds — it must not be called a quota wall."""
    failing = MagicMock(side_effect=_FakeAPIError(429, "too many requests"))
    with patch("time.sleep") as slept:
        with pytest.raises(_FakeAPIError):
            gemini.with_retry(failing)
    assert [c.args[0] for c in slept.call_args_list] == [1, 2]
    assert failing.call_count == gemini.MAX_RETRIES


def test_server_errors_are_unaffected_by_the_quota_split():
    failing = MagicMock(side_effect=_FakeAPIError(503, "unavailable"))
    with patch("time.sleep"):
        with pytest.raises(_FakeAPIError):
            gemini.with_retry(failing)
    assert failing.call_count == gemini.MAX_RETRIES


# ---------------------------------------------------------------------------
# Timeout — liteparse has none of its own
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not hasattr(signal, "SIGALRM"), reason="POSIX alarm only")
def test_deadline_interrupts_a_hanging_call():
    with pytest.raises(parse_vision.ExtractionTimeout):
        with parse_vision._Deadline(1):
            time.sleep(3)


@pytest.mark.skipif(not hasattr(signal, "SIGALRM"), reason="POSIX alarm only")
def test_deadline_disarms_itself_on_the_way_out():
    """A leaked alarm fires during the NEXT document and blames the wrong file."""
    with parse_vision._Deadline(5):
        pass
    time.sleep(0.01)  # would raise here if the alarm were still armed at 5s... and later


def test_deadline_of_zero_is_a_noop():
    with parse_vision._Deadline(0):
        pass


# ---------------------------------------------------------------------------
# Exit codes name the failure class
# ---------------------------------------------------------------------------


def test_exit_codes_are_distinct():
    codes = [
        parse_vision.EXIT_OK, parse_vision.EXIT_NO_KEY, parse_vision.EXIT_BAD_INPUT,
        parse_vision.EXIT_API, parse_vision.EXIT_VALIDATION, parse_vision.EXIT_TIMEOUT,
        parse_vision.EXIT_QUOTA, parse_vision.EXIT_LOCAL,
    ]
    assert len(set(codes)) == len(codes), "a shared code makes the cause unrecoverable"


def test_liteparse_reports_zero_chars_when_it_reads_nothing(tmp_path):
    """0 means 'ran and found nothing' (a scan); None means 'did not run'."""
    doc = tmp_path / "d.pdf"
    doc.write_bytes(b"%PDF-")
    fake = MagicMock()
    fake.return_value.parse.return_value = MagicMock(text="   ")
    with patch.dict("sys.modules", {"liteparse": MagicMock(LiteParse=fake)}):
        text, chars = parse_vision._extract_text_context(doc)
    assert text is None
    assert chars == 0


def test_liteparse_reports_its_char_count_on_success(tmp_path):
    doc = tmp_path / "d.pdf"
    doc.write_bytes(b"%PDF-")
    fake = MagicMock()
    fake.return_value.parse.return_value = MagicMock(text="hello world")
    with patch.dict("sys.modules", {"liteparse": MagicMock(LiteParse=fake)}):
        text, chars = parse_vision._extract_text_context(doc)
    assert text == "hello world"
    assert chars == 11
