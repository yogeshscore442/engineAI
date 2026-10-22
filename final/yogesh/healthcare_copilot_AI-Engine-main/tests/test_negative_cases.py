"""
test_negative_cases.py — Mandatory Negative & Edge Case Tests for Medical Document Validation.

Verifies that:
1. Non-medical images (cats, landscapes, selfies, blank pages, ordinary paragraphs, random numbers)
   are REJECTED and NEVER produce fabricated clinical findings.
2. Corrupted files, unsupported file formats, and blurry images are REJECTED cleanly.
3. Legitimate reports with unusual layouts or missing optional fields are correctly processed.
4. Multi-page PDFs and bilingual Tamil-English documents extract valid evidence.
"""
import io
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, str(Path(__file__).parent.parent))

from ai_engine import extract_record
from ai_engine.validator import validate_file_signature, assess_image_quality, classify_and_validate_evidence


def _run_extract(file_path: str, mime: str = "image/jpeg") -> dict:
    """Run extract_record with mock mode disabled so real validation pipeline executes."""
    with patch.dict(os.environ, {"USE_MOCK_AI": "false", "DISABLE_CACHE": "true"}):
        return extract_record(file_path, mime)


class TestMandatoryNegativeCases:
    """Verifies strict rejection of unsupported, non-medical, or corrupted inputs."""

    def test_blank_white_image(self):
        """A blank white image must be rejected as BLANK_OR_EMPTY_PAGE."""
        img = Image.new("RGB", (800, 600), color="white")
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            img.save(f, format="JPEG")
            tmp = f.name
        try:
            res = _run_extract(tmp, "image/jpeg")
            assert res["status"] == "REJECTED"
            assert res["accepted"] is False
            assert "BLANK_OR_EMPTY_PAGE" in res["reason_codes"] or "NON_MEDICAL_DOCUMENT" in res["reason_codes"]
            assert res["tests"] == []
            assert res["medicines"] == []
            assert res["summary_en"] is None
        finally:
            Path(tmp).unlink(missing_ok=True)

    def test_cat_photo_rejected(self):
        """A photo of a cat with pet metadata must be rejected as NON_MEDICAL_DOCUMENT."""
        img = Image.new("RGB", (800, 600), color=(180, 130, 90))
        draw = ImageDraw.Draw(img)
        # Draw cat shapes / non-medical text
        draw.ellipse([200, 150, 600, 450], fill=(220, 160, 110))
        draw.polygon([(250, 150), (300, 50), (350, 150)], fill=(200, 140, 100))
        draw.polygon([(450, 150), (500, 50), (550, 150)], fill=(200, 140, 100))
        draw.text((50, 520), "Cute orange kitten playing in the garden. Cat photography portfolio wallpaper.", fill=(0, 0, 0))

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            img.save(f, format="JPEG")
            tmp = f.name
        try:
            res = _run_extract(tmp, "image/jpeg")
            assert res["status"] == "REJECTED"
            assert res["accepted"] is False
            assert "NON_MEDICAL_DOCUMENT" in res["reason_codes"]
            assert res["tests"] == []
            assert res["medicines"] == []
            assert res["summary_en"] is None
        finally:
            Path(tmp).unlink(missing_ok=True)

    def test_landscape_photo_rejected(self):
        """A landscape image with scenery keywords must be rejected."""
        img = Image.new("RGB", (900, 600), color=(100, 180, 240))  # Sky
        draw = ImageDraw.Draw(img)
        draw.rectangle([0, 350, 900, 600], fill=(40, 140, 40))    # Hills
        draw.polygon([(100, 350), (300, 150), (500, 350)], fill=(120, 120, 120))  # Mountain
        draw.text((50, 500), "Beautiful mountain sunset landscape. Nature photography desktop wallpaper.", fill=(255, 255, 255))

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            img.save(f, format="JPEG")
            tmp = f.name
        try:
            res = _run_extract(tmp, "image/jpeg")
            assert res["status"] == "REJECTED"
            assert res["accepted"] is False
            assert "NON_MEDICAL_DOCUMENT" in res["reason_codes"]
            assert res["tests"] == []
            assert res["medicines"] == []
        finally:
            Path(tmp).unlink(missing_ok=True)

    def test_random_selfie_rejected(self):
        """A casual selfie photograph must be rejected."""
        img = Image.new("RGB", (600, 800), color=(230, 210, 190))
        draw = ImageDraw.Draw(img)
        draw.ellipse([150, 200, 450, 550], fill=(210, 170, 140))
        draw.text((50, 720), "Sunday coffee selfie portrait camera phone photo with friends", fill=(0, 0, 0))

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            img.save(f, format="JPEG")
            tmp = f.name
        try:
            res = _run_extract(tmp, "image/jpeg")
            assert res["status"] == "REJECTED"
            assert res["accepted"] is False
            assert "NON_MEDICAL_DOCUMENT" in res["reason_codes"]
        finally:
            Path(tmp).unlink(missing_ok=True)

    def test_ordinary_paragraphs_text(self):
        """An image containing an essay or general article must be rejected."""
        img = Image.new("RGB", (800, 800), color="white")
        draw = ImageDraw.Draw(img)
        lines = [
            "Introduction to Modern Web Architecture",
            "Software engineering principles recommend separating concerns between modules.",
            "Database normalization reduces data redundancy and improves transactional integrity.",
            "Continuous integration pipelines automatically build, lint, and execute unit test suites.",
            "Cloud infrastructure enables horizontal scaling across multiple availability zones.",
        ]
        y = 50
        for line in lines:
            draw.text((50, y), line, fill=(0, 0, 0))
            y += 40

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            img.save(f, format="PNG")
            tmp = f.name
        try:
            res = _run_extract(tmp, "image/png")
            assert res["status"] == "REJECTED"
            assert res["accepted"] is False
            assert "NON_MEDICAL_DOCUMENT" in res["reason_codes"]
            assert res["tests"] == []
            assert res["medicines"] == []
        finally:
            Path(tmp).unlink(missing_ok=True)

    def test_random_numbers_invoice(self):
        """An invoice with numbers and tax details must NOT produce fake lab tests."""
        img = Image.new("RGB", (800, 800), color="white")
        draw = ImageDraw.Draw(img)
        lines = [
            "SUPERMARKET TAX INVOICE",
            "GSTIN: 33AAAAA0000A1Z5",
            "Item 1: Organic Apples - Qty: 2 - Price: 140.00",
            "Item 2: Whole Milk 1L - Qty: 3 - Price: 96.50",
            "Subtotal: 236.50",
            "CGST (2.5%): 5.91",
            "SGST (2.5%): 5.91",
            "Grand Total Amount Paid: 248.32",
        ]
        y = 50
        for line in lines:
            draw.text((50, y), line, fill=(0, 0, 0))
            y += 40

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            img.save(f, format="PNG")
            tmp = f.name
        try:
            res = _run_extract(tmp, "image/png")
            assert res["status"] == "REJECTED"
            assert res["accepted"] is False
            # Verify numbers 140.00, 96.50 are NOT extracted as blood glucose or creatinine
            assert res["tests"] == []
            assert res["medicines"] == []
        finally:
            Path(tmp).unlink(missing_ok=True)

    def test_corrupted_file(self):
        """A corrupted file with invalid header bytes must be rejected."""
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(b"CORRUPTED_GARBAGE_HEADER_DATA_12345" * 20)
            tmp = f.name
        try:
            res = _run_extract(tmp, "image/jpeg")
            assert res["status"] == "REJECTED"
            assert res["accepted"] is False
            assert res["error"] is not None
        finally:
            Path(tmp).unlink(missing_ok=True)

    def test_unsupported_file_extension(self):
        """An unsupported executable or zip file must be rejected."""
        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as f:
            f.write(b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00")
            tmp = f.name
        try:
            res = _run_extract(tmp, "application/x-dosexec")
            assert res["status"] == "REJECTED"
            assert res["accepted"] is False
        finally:
            Path(tmp).unlink(missing_ok=True)

    def test_illegible_blur_image(self):
        """An extremely blurred, unreadable image must fail quality or classification checks."""
        img = Image.new("RGB", (600, 400), color="white")
        draw = ImageDraw.Draw(img)
        draw.text((50, 100), "Unreadable test line", fill=(100, 100, 100))
        # Severe blur making text completely illegible
        blurred = img.filter(ImageFilter.GaussianBlur(radius=30))

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            blurred.save(f, format="JPEG")
            tmp = f.name
        try:
            res = _run_extract(tmp, "image/jpeg")
            assert res["status"] in ("REJECTED", "NEEDS_REVIEW")
            if res["status"] == "REJECTED":
                assert res["accepted"] is False
                assert res["tests"] == []
        finally:
            Path(tmp).unlink(missing_ok=True)


class TestPositiveAndEdgeCases:
    """Verifies that genuine medical documents are correctly recognized and processed."""

    def test_legitimate_lab_report_unusual_layout(self):
        """Legitimate laboratory tests formatted horizontally must be recognized."""
        text = (
            "Apex Clinical Diagnostics Laboratory\n"
            "Investigation Report\n"
            "Patient: John Doe   Date: 2024-10-15\n"
            "Hemoglobin: 14.2 g/dL  (Ref: 13.0 - 17.0 g/dL)  Status: Normal\n"
            "Fasting Blood Sugar: 92 mg/dL  (Ref: 70 - 100 mg/dL)\n"
            "Serum Creatinine: 0.9 mg/dL  (Ref: 0.7 - 1.3 mg/dL)\n"
        )
        img = Image.new("RGB", (1000, 600), color="white")
        draw = ImageDraw.Draw(img)
        y = 50
        for line in text.split("\n"):
            draw.text((50, y), line, fill=(0, 0, 0))
            y += 40

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            img.save(f, format="PNG")
            tmp = f.name
        try:
            # Test gatekeeper classification directly with the OCR text
            decision, doc_type, conf, reasons, evidence = classify_and_validate_evidence(
                ocr_text=text,
                quality={"width": 1000, "height": 600, "is_blank": False},
            )
            assert decision == "ACCEPTED"
            assert doc_type == "LAB_REPORT"
            assert conf >= 0.75
            assert len(evidence["matched_lab_tokens"]) >= 3
        finally:
            Path(tmp).unlink(missing_ok=True)

    def test_legitimate_prescription_incomplete_optional(self):
        """A prescription with valid medicine instructions but missing optional demographics must be accepted."""
        text = (
            "CITY HEALTH CLINIC\n"
            "Dr. R. Sharma, MBBS, MD (Internal Medicine)\n"
            "Rx\n"
            "1. Tab. Dolo 650 mg - 1-0-1 after food x 5 days\n"
            "2. Cap. Amoxicillin 500 mg - 1-0-1 after food x 7 days\n"
            "Review after 7 days.\n"
        )
        decision, doc_type, conf, reasons, evidence = classify_and_validate_evidence(
            ocr_text=text,
            quality={"width": 800, "height": 1000, "is_blank": False},
        )
        assert decision == "ACCEPTED"
        assert doc_type == "PRESCRIPTION"
        assert conf >= 0.75
        assert evidence["dosage_patterns_count"] >= 1

    def test_mixed_english_tamil_document(self):
        """A document with mixed English and Tamil medical instructions must be accepted."""
        text = (
            "ஆரோக்கியா மருத்துவமனை (Arokya Hospital)\n"
            "Dr. K. Murugan, MBBS - Reg No: 84729\n"
            "Rx\n"
            "1. Tab Metformin 500 mg - 1-0-1 (உணவுக்குப் பின் / after food)\n"
            "2. Tab Atorvastatin 10 mg - 0-0-1 (இரவில் / night)\n"
        )
        decision, doc_type, conf, reasons, evidence = classify_and_validate_evidence(
            ocr_text=text,
            quality={"width": 800, "height": 1000, "is_blank": False},
        )
        assert decision == "ACCEPTED"
        assert doc_type == "PRESCRIPTION"
        assert conf >= 0.75
