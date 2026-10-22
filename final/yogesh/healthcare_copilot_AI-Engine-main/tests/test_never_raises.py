"""
test_never_raises.py — Verify extract_record() NEVER raises an exception.
Tests real corrupt file, empty file, wrong MIME, missing file, and mock mode segregation.
Run: pytest tests/test_never_raises.py -v
"""
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from ai_engine.models import DISCLAIMER


def _call_real(file_path: str, mime: str = "image/jpeg") -> dict:
    """Call extract_record with real validation (mock disabled)."""
    with patch.dict(os.environ, {"USE_MOCK_AI": "false"}):
        from ai_engine import extract_record
        return extract_record(file_path, mime)


def _call_mock(file_path: str, mime: str = "image/jpeg") -> dict:
    """Call extract_record with mock mode enabled."""
    with patch.dict(os.environ, {"USE_MOCK_AI": "true"}):
        from ai_engine import extract_record
        return extract_record(file_path, mime)


class TestNeverRaises:
    """Verify that real pipeline execution handles corrupt/missing inputs without raising."""

    def test_missing_file(self):
        result = _call_real("/nonexistent/path/to/file.jpg")
        assert isinstance(result, dict)
        assert "record_id" in result
        assert "disclaimer" in result
        assert result.get("error") is not None
        assert result.get("status") == "REJECTED"

    def test_empty_file(self):
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(b"")
            tmp = f.name
        try:
            result = _call_real(tmp, "image/jpeg")
            assert isinstance(result, dict)
            assert result.get("error") is not None
            assert result.get("status") == "REJECTED"
        finally:
            Path(tmp).unlink(missing_ok=True)

    def test_corrupt_image(self):
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(b"NOT_VALID_IMAGE_DATA_\x00\xff\xfe" * 100)
            tmp = f.name
        try:
            result = _call_real(tmp, "image/jpeg")
            assert isinstance(result, dict)
            assert "record_id" in result
            assert result.get("error") is not None
            assert result.get("status") == "REJECTED"
        finally:
            Path(tmp).unlink(missing_ok=True)

    def test_wrong_mime_type(self):
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(b"FAKE_DATA")
            tmp = f.name
        try:
            result = _call_real(tmp, "application/x-unknown-binary")
            assert isinstance(result, dict)
            assert result.get("error") is not None
            assert result.get("status") == "REJECTED"
        finally:
            Path(tmp).unlink(missing_ok=True)

    def test_binary_random_data(self):
        import random
        data = bytes([random.randint(0, 255) for _ in range(2048)])
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(data)
            tmp = f.name
        try:
            result = _call_real(tmp, "application/pdf")
            assert isinstance(result, dict)
            assert result.get("error") is not None
            assert result.get("status") == "REJECTED"
        finally:
            Path(tmp).unlink(missing_ok=True)

    def test_disclaimer_always_present(self):
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(b"BAD_DATA")
            tmp = f.name
        try:
            result = _call_real(tmp)
            assert result.get("disclaimer") == DISCLAIMER
        finally:
            Path(tmp).unlink(missing_ok=True)


class TestMockMode:
    """Verify mock mode contract integrity."""

    def test_mock_lab_report(self):
        result = _call_mock("samples/lab1.jpg", "image/jpeg")
        assert isinstance(result, dict)
        assert result.get("doc_type") in {"lab_report", "prescription", "discharge_summary", "diagnostic_report"}
        assert result.get("disclaimer") == DISCLAIMER
        assert result.get("status") == "ACCEPTED"

    def test_mock_prescription(self):
        result = _call_mock("samples/prescription1.jpg", "image/jpeg")
        assert isinstance(result, dict)
        assert result.get("doc_type") == "prescription"
        assert result.get("status") == "ACCEPTED"

    def test_mock_discharge(self):
        result = _call_mock("samples/discharge1.pdf", "application/pdf")
        assert isinstance(result, dict)
        assert result.get("doc_type") == "discharge_summary"
        assert result.get("status") == "ACCEPTED"

    def test_mock_always_has_record_id(self):
        r1 = _call_mock("samples/lab1.jpg")
        r2 = _call_mock("samples/lab2.jpg")
        assert r1["record_id"] != r2["record_id"]
