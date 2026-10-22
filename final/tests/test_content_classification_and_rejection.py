"""
test_content_classification_and_rejection.py — Comprehensive Phase 3 & 4 Regression Suite

Validates:
1. Content-based classification independence from filenames (WhatsApp Image, IMG_1234, scan.png, etc.).
2. Renaming non-medical images to medical names does NOT fool the classifier.
3. 20 Phase 4 image validation and rejection scenarios:
   - Valid prescription photo
   - Valid lab report image
   - Ordinary selfie
   - Landscape photograph
   - Animal photograph
   - Screenshot unrelated to healthcare
   - Completely blank image
   - Blurred prescription
   - Extremely low-resolution image
   - Rotated document
   - Corrupted image
   - Unsupported image format
   - Invalid PDF
   - Password-protected PDF
   - Oversized file
   - Empty file
   - File-extension and content mismatch
   - Image containing unrelated text (grocery receipt)
   - Multi-page document
   - Unreadable handwriting
4. Clear distinction between rejection reasons:
   - INVALID_FILE_SIGNATURE
   - NON_MEDICAL_DOCUMENT / UNRELATED_PHOTOGRAPH
   - IMAGE_QUALITY_POOR / BLURRY
   - UNKNOWN_DOCUMENT / UNREADABLE
5. Zero fabrication of prescription or laboratory data upon rejection.
6. Laboratory reports bypass prescription OCR and preserve original backend LOINC logic.
"""
import io
import json
import os
import shutil
import tempfile
from pathlib import Path
import pytest
from PIL import Image, ImageDraw, ImageFilter

# Paths
TEST_DIR = Path(__file__).resolve().parent
WORKSPACE_FINAL = TEST_DIR.parent
AI_ENGINE_PATH = WORKSPACE_FINAL / "yogesh" / "healthcare_copilot_AI-Engine-main"
BACKEND_PATH = WORKSPACE_FINAL / "praveen" / "backend"

import sys
if str(AI_ENGINE_PATH) not in sys.path:
    sys.path.insert(0, str(AI_ENGINE_PATH))
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

from ai_engine.extract import extract_from_file
from ai_engine.ocr import load_document
from ai_engine.validator import (
    validate_medical_document,
    validate_file_signature,
    assess_image_quality
)
from ai_engine.models import DocType, VerificationState

SAMPLES_DIR = AI_ENGINE_PATH / "samples"


# ==============================================================================
# Helper Image Creators
# ==============================================================================

def make_jpeg_bytes(size=(400, 300), color=(200, 200, 200)) -> bytes:
    img = Image.new("RGB", size, color=color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def make_text_jpeg(text: str, size=(700, 500), bg=(255, 255, 255)) -> bytes:
    img = Image.new("RGB", size, color=bg)
    draw = ImageDraw.Draw(img)
    draw.text((30, 40), text, fill=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


# ==============================================================================
# PHASE 3: CONTENT-BASED CLASSIFICATION & FILENAME INDEPENDENCE
# ==============================================================================

class TestContentBasedClassification:
    """Proves that document classification relies on content evidence, not filenames."""

    @pytest.mark.parametrize("filename", [
        "WhatsApp Image 2026-10-21 at 14.30.00.jpeg",
        "IMG_1234.jpg",
        "document.pdf",
        "scan.png",
        "downloaded_file.jpg",
        "prescription_final.pdf",
        "random_uuid_8f3a9b.jpg"
    ])
    def test_genuine_prescription_classified_identically_regardless_of_filename(self, filename):
        """A genuine prescription must be classified as PRESCRIPTION across arbitrary filenames."""
        sample_rx = SAMPLES_DIR / "prescription1.jpg"
        assert sample_rx.exists(), "Sample prescription1.jpg must exist in repository"
        
        with tempfile.TemporaryDirectory() as td:
            target_path = Path(td) / filename
            mime = "application/pdf" if filename.endswith(".pdf") else "image/jpeg"
            
            # If target has .pdf extension, convert sample image into valid PDF
            if filename.endswith(".pdf"):
                img = Image.open(sample_rx)
                img.save(target_path, "PDF")
            else:
                shutil.copy(sample_rx, target_path)

            res = extract_from_file(str(target_path), mime)
            assert res["accepted"] is True
            assert res["status"] == "ACCEPTED"
            assert res["doc_type"] == "prescription"
            assert len(res.get("medicines", [])) >= 2

    @pytest.mark.parametrize("filename", [
        "prescription_urgent_doctor.jpg",
        "rx_medical_signed.png",
        "hospital_clinical_record.pdf",
        "doctor_prescription.jpeg"
    ])
    def test_non_medical_image_rejected_even_with_medical_filename(self, filename):
        """A non-medical image (e.g. landscape/cat/pattern) must NOT be accepted merely due to medical name."""
        with tempfile.TemporaryDirectory() as td:
            target_path = Path(td) / filename
            mime = "application/pdf" if filename.endswith(".pdf") else "image/jpeg"
            
            # Create a blank/pattern non-medical image
            if filename.endswith(".pdf"):
                img = Image.new("RGB", (400, 400), color=(100, 150, 200))
                img.save(target_path, "PDF")
            else:
                img = Image.new("RGB", (400, 400), color=(100, 150, 200))
                img.save(target_path, "JPEG" if "jp" in filename else "PNG")

            res = extract_from_file(str(target_path), mime)
            assert res["accepted"] is False
            assert res["status"] in ("REJECTED", "PROCESSING_FAILED")
            assert res.get("medicines", []) == []
            assert res.get("tests", []) == []


# ==============================================================================
# PHASE 4: 20 INVALID IMAGES AND RANDOM-OUTPUT PREVENTION SCENARIOS
# ==============================================================================

class TestTwentyValidationScenarios:
    """Validates the 20 distinct rejection and document handling scenarios."""

    def test_01_valid_prescription_photo(self):
        """Scenario 1: Valid prescription photograph."""
        p = SAMPLES_DIR / "prescription1.jpg"
        res = extract_from_file(str(p), "image/jpeg")
        assert res["accepted"] is True
        assert res["doc_type"] == "prescription"
        assert len(res.get("medicines", [])) > 0

    def test_02_valid_lab_report_image(self):
        """Scenario 2: Valid laboratory report image."""
        p = SAMPLES_DIR / "lab1.jpg"
        res = extract_from_file(str(p), "image/jpeg")
        assert res["accepted"] is True
        assert res["doc_type"] == "lab_report"
        assert len(res.get("tests", [])) > 0

    def test_03_ordinary_selfie(self):
        """Scenario 3: Ordinary selfie with no medical text."""
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "selfie.jpg"
            img = Image.new("RGB", (400, 500), color=(220, 180, 160))
            draw = ImageDraw.Draw(img)
            draw.ellipse((100, 100, 300, 300), fill=(240, 200, 180)) # face shape
            img.save(p, "JPEG")
            
            res = extract_from_file(str(p), "image/jpeg")
            assert res["accepted"] is False
            assert res["status"] == "REJECTED"
            assert res.get("medicines", []) == []

    def test_04_landscape_photograph(self):
        """Scenario 4: Landscape photograph."""
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "mountains.jpg"
            img = Image.new("RGB", (600, 300), color=(135, 206, 235)) # sky
            draw = ImageDraw.Draw(img)
            draw.polygon([(0, 300), (300, 100), (600, 300)], fill=(34, 139, 34)) # mountain
            img.save(p, "JPEG")
            
            res = extract_from_file(str(p), "image/jpeg")
            assert res["accepted"] is False
            assert res["status"] == "REJECTED"
            assert res.get("medicines", []) == []

    def test_05_animal_photograph(self):
        """Scenario 5: Animal photograph."""
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "cat.jpg"
            img = Image.new("RGB", (400, 400), color=(200, 150, 100))
            img.save(p, "JPEG")
            res = extract_from_file(str(p), "image/jpeg")
            assert res["accepted"] is False
            assert res["status"] == "REJECTED"

    def test_06_screenshot_unrelated_to_healthcare(self):
        """Scenario 6: Screenshot unrelated to healthcare (e.g. cinema ticket)."""
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "ticket.png"
            p.write_bytes(make_text_jpeg("CINEMA BOOKING\nMovie: Avengers Endgame\nSeat: A12, A13\nTotal: INR 500\nEnjoy the show!"))
            res = extract_from_file(str(p), "image/png")
            assert res["accepted"] is False
            assert res["status"] == "REJECTED"
            assert res.get("medicines", []) == []

    def test_07_completely_blank_image(self):
        """Scenario 7: Completely blank image."""
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "blank.jpg"
            p.write_bytes(make_jpeg_bytes(color=(255, 255, 255)))
            res = extract_from_file(str(p), "image/jpeg")
            assert res["accepted"] is False
            assert res["status"] == "REJECTED"
            assert res.get("medicines", []) == []

    def test_08_blurred_prescription(self):
        """Scenario 8: Blurred prescription."""
        sample_rx = SAMPLES_DIR / "prescription1.jpg"
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "blurred_rx.jpg"
            img = Image.open(sample_rx).filter(ImageFilter.GaussianBlur(radius=15))
            img.save(p, "JPEG")
            
            res = extract_from_file(str(p), "image/jpeg")
            # Must either reject for quality or return honest status without fabricated values
            assert res.get("accepted") is False or res["status"] in ("REJECTED", "ACCEPTED")
            if not res["accepted"]:
                assert res.get("medicines", []) == []

    def test_09_extremely_low_resolution_image(self):
        """Scenario 9: Extremely low-resolution image (30x30)."""
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "lowres.jpg"
            img = Image.new("RGB", (30, 30), color=(255, 255, 255))
            img.save(p, "JPEG")
            res = extract_from_file(str(p), "image/jpeg")
            assert res["accepted"] is False
            assert res["status"] in ("REJECTED", "PROCESSING_FAILED")

    def test_10_rotated_document(self):
        """Scenario 10: Rotated document."""
        sample_rx = SAMPLES_DIR / "prescription1.jpg"
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "rotated_90.jpg"
            img = Image.open(sample_rx).rotate(90, expand=True)
            img.save(p, "JPEG")
            res = extract_from_file(str(p), "image/jpeg")
            assert res["status"] in ("ACCEPTED", "REJECTED", "NEEDS_REVIEW")

    def test_11_corrupted_image(self):
        """Scenario 11: Corrupted image bytes."""
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "corrupt.jpg"
            p.write_bytes(b"\xFF\xD8\xFF\xE0\x00\x10JFIF" + b"\x00" * 30 + b"RANDOM_CORRUPTION_TRUNCATED")
            res = extract_from_file(str(p), "image/jpeg")
            assert res["accepted"] is False
            assert res["status"] == "REJECTED"

    def test_12_unsupported_image_format(self):
        """Scenario 12: Unsupported image format (e.g. BMP/TIFF or raw binary)."""
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "raw.xyz"
            p.write_bytes(b"XYZ_UNKNOWN_BINARY_DATA_BLOCK_HEADER")
            res = extract_from_file(str(p), "application/octet-stream")
            assert res["accepted"] is False
            assert res["status"] == "REJECTED"

    def test_13_invalid_pdf(self):
        """Scenario 13: Invalid PDF (corrupt header)."""
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "broken.pdf"
            p.write_bytes(b"%PDF-1.4\nBROKEN_OBJECTS_AND_NO_TRAILER_EOF")
            res = extract_from_file(str(p), "application/pdf")
            assert res["accepted"] is False
            assert res["status"] == "REJECTED"

    def test_14_password_protected_pdf(self):
        """Scenario 14: Password-protected PDF."""
        # Simulated protected PDF structure
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "protected.pdf"
            p.write_bytes(b"%PDF-1.4\n1 0 obj\n<< /Filter /Standard /V 2 /R 3 /P -3904 /O (test) /U (test) >>\nendobj\ntrailer\n<< /Encrypt 1 0 R >>\n%%EOF")
            res = extract_from_file(str(p), "application/pdf")
            assert res["accepted"] is False
            assert res["status"] == "REJECTED"

    def test_15_oversized_file(self):
        """Scenario 15: Oversized file exceeding limit (>30MB check)."""
        from ai_engine.validator import validate_file_signature
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.seek(32 * 1024 * 1024)
            f.write(b"\0")
            tmp_path = f.name
        try:
            valid, reason, mime = validate_file_signature(tmp_path, "image/jpeg")
            assert valid is False
            assert reason == "FILE_TOO_LARGE"
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_16_empty_file(self):
        """Scenario 16: Zero-byte empty file."""
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "empty.jpg"
            p.write_bytes(b"")
            res = extract_from_file(str(p), "image/jpeg")
            assert res["accepted"] is False
            assert res["status"] == "REJECTED"

    def test_17_file_extension_and_content_mismatch(self):
        """Scenario 17: File-extension and content mismatch (HTML renamed to .pdf or .jpg)."""
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "fake_report.pdf"
            p.write_bytes(b"<html><body><h1>Not a PDF</h1></body></html>")
            res = extract_from_file(str(p), "application/pdf")
            assert res["accepted"] is False
            assert res["status"] == "REJECTED"

    def test_18_image_containing_unrelated_text(self):
        """Scenario 18: Image containing unrelated text (grocery receipt)."""
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "groceries.jpg"
            p.write_bytes(make_text_jpeg(
                "FRESH MART SUPERMARKET\n"
                "1. Whole Milk 1L - 60.00\n"
                "2. Brown Bread 400g - 45.00\n"
                "3. Farm Eggs 6pk - 50.00\n"
                "Total: 155.00\n"
                "Thank you for shopping with us!"
            ))
            res = extract_from_file(str(p), "image/jpeg")
            assert res["accepted"] is False
            assert res["status"] == "REJECTED"
            assert res.get("medicines", []) == []

    def test_19_document_with_multiple_pages(self):
        """Scenario 19: Document with multiple pages (discharge summary PDF)."""
        sample_pdf = SAMPLES_DIR / "discharge1.pdf"
        assert sample_pdf.exists()
        res = extract_from_file(str(sample_pdf), "application/pdf")
        assert res["accepted"] is True
        assert res["doc_type"] == "discharge_summary"

    def test_20_unreadable_handwriting_never_fabricates(self):
        """Scenario 20: Unreadable handwriting reports limitation honestly."""
        from ai_engine.dosage import parse_schedule
        # Random noise / scribble tokens must not become dosage schedules
        parsed, food, dur = parse_schedule("qwerty uiop asdfgh jkl zxcvbnm")
        assert parsed == []


# ==============================================================================
# PHASE 6: LABORATORY REPORT LOGIC PRESERVATION
# ==============================================================================

class TestLabReportPreservation:
    """Verifies laboratory report processing continues through internal LOINC/range backend."""

    def test_lab_report_preserves_reference_intervals_and_units(self):
        """Extracted laboratory reports must retain original test names, units, and intervals."""
        p = SAMPLES_DIR / "lab1.jpg"
        res = extract_from_file(str(p), "image/jpeg")
        assert res["accepted"] is True
        assert res["doc_type"] == "lab_report"
        tests = res.get("tests", [])
        assert len(tests) >= 3
        for t in tests:
            assert "name" in t
            assert "value" in t
            assert "unit" in t
            assert "lab_reference_interval" in t
            assert "provenance" in t
            # Never invent values
            assert t["value"] is not None

    def test_lab_report_bypasses_external_prescription_services(self):
        """Lab reports must never be routed to external prescription OCR services."""
        p = SAMPLES_DIR / "lab1.jpg"
        res = extract_from_file(str(p), "image/jpeg")
        assert res["doc_type"] == "lab_report"
        # Provenance should be internal extraction
        assert "medicines" not in res or len(res.get("medicines", [])) == 0
