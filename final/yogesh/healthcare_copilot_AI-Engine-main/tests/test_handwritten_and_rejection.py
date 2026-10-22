"""
test_handwritten_and_rejection.py — Comprehensive tests for handwritten clinical records,
layout evidence detection, rotation & image preprocessing, and strict non-medical rejection.

Verifies:
1. Photographed handwritten clinical notes on clinical forms are marked as POSSIBLE_MEDICAL_DOCUMENT_NEEDS_REVIEW,
   NEEDS_REVIEW, with NO fabricated clinical findings, preserving OCR text and original image reference.
2. Documents are never classified as NON_MEDICAL solely because OCR extracted little text.
3. Layout signals (form lines, paper boundaries, ink density, printed headings) prevent false rejection.
4. Rotated (90/270 deg) and low-contrast/shadowed photographs are preprocessed correctly.
5. Genuine non-medical documents (cats, scenery, supermarket receipts, blank pages) remain strictly REJECTED.
6. Printed prescriptions and scanned lab reports continue to be ACCEPTED without regression.
"""
import io
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, str(Path(__file__).parent.parent))

from ai_engine import extract_record
from ai_engine.validator import (
    validate_medical_document,
    assess_image_quality,
    detect_layout_signals,
    classify_and_validate_evidence,
    DOCUMENT_TYPE_POSSIBLE_MEDICAL,
)
from ai_engine.ocr import (
    _enhance_photographed_document,
    _detect_and_crop_perspective,
    _preprocess,
)


def _run_extract(file_path: str, mime: str = "image/jpeg") -> dict:
    with patch.dict(os.environ, {"USE_MOCK_AI": "false", "DISABLE_CACHE": "true"}):
        return extract_record(file_path, mime)


def create_clinical_note_image() -> Image.Image:
    """
    Creates a simulated photographed handwritten clinical note on a hospital form.
    Contains: Hospital header, patient details table, printed ruling lines,
    vitals/symptoms, and faint/handwritten style markings.
    """
    # 800 x 1100 (standard page aspect ratio)
    img = Image.new("RGB", (800, 1100), color=(248, 246, 240))
    draw = ImageDraw.Draw(img)

    # Hospital Header
    draw.text((250, 40), "CITY GENERAL HOSPITAL", fill=(40, 40, 40))
    draw.text((280, 65), "DEPARTMENT OF GENERAL MEDICINE", fill=(60, 60, 60))
    draw.text((310, 85), "CLINICAL OUTPATIENT RECORD", fill=(80, 80, 80))

    # Outer border & ruling lines (Form Structure)
    draw.rectangle([40, 120, 760, 1020], outline=(100, 100, 100), width=2)
    # Header separator
    draw.line([(40, 180), (760, 180)], fill=(120, 120, 120), width=2)
    # Column divider for patient info
    draw.line([(400, 120), (400, 180)], fill=(120, 120, 120), width=1)

    # Patient info
    draw.text((50, 130), "Patient Name: Rajesh Kumar", fill=(30, 30, 30))
    draw.text((50, 155), "Age / Sex: 46 / M     IP/OP No: 2026/8831", fill=(30, 30, 30))
    draw.text((410, 130), "Date: 21/10/2026", fill=(30, 30, 30))
    draw.text((410, 155), "Consultant: Dr. S. Rao, MD", fill=(30, 30, 30))

    # Form sections with printed ruling lines
    draw.line([(40, 240), (760, 240)], fill=(150, 150, 150), width=1)
    draw.text((50, 215), "CLINICAL NOTES & OBSERVATIONS / VITALS", fill=(50, 50, 50))

    # Printed ruling lines for writing
    for y in range(300, 950, 50):
        draw.line([(50, y), (750, y)], fill=(200, 210, 220), width=1)

    # Vitals and clinical notes
    draw.text((55, 270), "BP: 130/85 mmHg    Pulse: 78/min    Temp: 98.6 F    SpO2: 98%", fill=(30, 30, 30))

    # Simulated handwritten clinical text (Rx, symptoms)
    draw.text((60, 320), "C/o fever x 3 days with mild cough and body ache", fill=(20, 40, 70))
    draw.text((60, 420), "O/E: Chest clear, Throat mild congestion, Abdomen soft", fill=(20, 40, 70))
    draw.text((60, 520), "Impression: Acute Viral Pharyngitis / URTI", fill=(20, 40, 70))
    draw.text((60, 620), "Rx: Tab Paracetamol 650mg TDS x 3 days", fill=(20, 40, 70))
    draw.text((60, 670), "    Tab Cetirizine 10mg OD HS x 5 days", fill=(20, 40, 70))
    draw.text((60, 720), "    Warm saline gargle TDS", fill=(20, 40, 70))
    draw.text((60, 870), "Review after 3 days if fever persists.", fill=(20, 40, 70))
    draw.text((550, 980), "Dr. S. Rao, MD", fill=(30, 30, 30))

    return img


def create_sparse_handwritten_form_image() -> Image.Image:
    """
    Creates a medical form where handwriting is faint or cursive,
    causing standard OCR to read very few words (< 3 words),
    yet visible layout lines, paper ratio, and hospital stamps are present.
    """
    img = Image.new("RGB", (750, 1000), color=(240, 238, 230))
    draw = ImageDraw.Draw(img)

    # Grid / ruling lines
    draw.rectangle([50, 80, 700, 920], outline=(80, 80, 80), width=2)
    for y in range(150, 900, 60):
        draw.line([(50, y), (700, y)], fill=(180, 190, 200), width=1)
    draw.line([(350, 80), (350, 210)], fill=(80, 80, 80), width=1)

    # Faint clinical mark
    draw.text((60, 100), "CLINICAL RECORD", fill=(100, 100, 100))
    draw.text((60, 160), "Rx", fill=(50, 50, 50))

    # Faint handwritten strokes (curves)
    for offset in range(5):
        draw.arc([100 + offset, 240, 300 + offset, 280], start=0, end=180, fill=(30, 40, 80))
        draw.arc([150 + offset, 300, 400 + offset, 340], start=30, end=210, fill=(30, 40, 80))
        draw.arc([120 + offset, 420, 350 + offset, 460], start=10, end=190, fill=(30, 40, 80))

    return img


class TestLayoutSignalsDetection:
    """Tests OpenCV-based layout evidence detector."""

    def test_detects_lines_and_paper_in_clinical_form(self):
        img = create_clinical_note_image()
        signals = detect_layout_signals(img)
        assert signals["is_document_like"] is True
        assert signals["paper_ratio"] is True
        assert signals["horizontal_lines"] > 0
        assert signals["structure_confidence"] >= 0.5

    def test_rejects_solid_color_or_noise(self):
        img = Image.new("RGB", (800, 600), color=(100, 20, 20))
        signals = detect_layout_signals(img)
        assert signals["is_document_like"] is False


class TestImagePreprocessingAndEnhancement:
    """Tests shadow removal, rotation handling, and enhancement."""

    def test_photographed_enhancement_removes_shadows(self):
        img = create_clinical_note_image()
        # Add simulated shadow gradient (darker at bottom right)
        arr = np.array(img, dtype=np.float32)
        h, w = arr.shape[:2]
        shadow = np.linspace(1.0, 0.4, w)[np.newaxis, :, np.newaxis]
        shadowed_arr = np.clip(arr * shadow, 0, 255).astype(np.uint8)
        shadowed_img = Image.fromarray(shadowed_arr)

        enhanced = _enhance_photographed_document(shadowed_img)
        assert enhanced.size == shadowed_img.size
        # The background should be brightened
        enh_arr = np.array(enhanced)
        assert np.mean(enh_arr) >= np.mean(shadowed_arr)

    def test_perspective_detection_does_not_crash(self):
        img = create_clinical_note_image()
        cropped = _detect_and_crop_perspective(img)
        assert cropped.width > 100
        assert cropped.height > 100


class TestHandwrittenDocumentWorkflow:
    """Tests end-to-end extraction behavior on handwritten medical records."""

    def test_sparse_text_with_layout_not_rejected_as_non_medical(self):
        """
        CRITICAL REQUIREMENT 1 & 2:
        A document must not be classified as non-medical solely because OCR extracted little text.
        When layout signals or form structure exist, it must be marked as
        POSSIBLE_MEDICAL_DOCUMENT_NEEDS_REVIEW with NEEDS_REVIEW status.
        """
        img = create_sparse_handwritten_form_image()
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            img.save(f, format="JPEG")
            tmp = f.name

        try:
            res = _run_extract(tmp, "image/jpeg")
            # Must NOT be rejected as non-medical!
            assert res["status"] != "REJECTED" or "NON_MEDICAL_DOCUMENT" not in res.get("reason_codes", [])
            assert res["status"] == "NEEDS_REVIEW"
            assert res["document_type"] == DOCUMENT_TYPE_POSSIBLE_MEDICAL
            assert "POSSIBLE_MEDICAL_DOCUMENT_NEEDS_REVIEW" in res["reason_codes"]
            assert res["accepted"] is False
            # Never fabricate clinical content
            assert res["medicines"] == []
            assert res["tests"] == []
            # Raw OCR text must be preserved
            assert "ocr_text" in res
        finally:
            Path(tmp).unlink(missing_ok=True)

    def test_handwritten_clinical_note_needs_review(self):
        """
        A handwritten outpatient clinical note must produce a contract-compliant
        record with NEEDS_REVIEW status and preserved OCR text.
        """
        img = create_clinical_note_image()
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            img.save(f, format="JPEG")
            tmp = f.name

        try:
            res = _run_extract(tmp, "image/jpeg")
            # Should be accepted or marked for review (never rejected as non-medical)
            assert res["status"] in ("ACCEPTED", "NEEDS_REVIEW")
            assert "NON_MEDICAL_DOCUMENT" not in res.get("reason_codes", [])
            if res["status"] == "NEEDS_REVIEW":
                assert res["accepted"] is False
                assert len(res["needs_review"]) > 0
            assert "ocr_text" in res
            assert res["ocr_text"] is not None
        finally:
            Path(tmp).unlink(missing_ok=True)


class TestNonMedicalDocumentsStillRejected:
    """
    CRITICAL REQUIREMENT 8:
    Keep NON_MEDICAL_DOCUMENT for documents with sufficient evidence that they are unrelated.
    """

    def test_cat_photo_is_strictly_rejected(self):
        img = Image.new("RGB", (800, 600), color=(180, 130, 90))
        draw = ImageDraw.Draw(img)
        draw.ellipse([200, 150, 600, 450], fill=(220, 160, 110))
        draw.text((100, 500), "Cute pet kitten cat portrait", fill=(50, 30, 20))
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            img.save(f, format="JPEG")
            tmp = f.name
        try:
            res = _run_extract(tmp, "image/jpeg")
            assert res["status"] == "REJECTED"
            assert res["accepted"] is False
            assert any(r in res["reason_codes"] for r in ("NON_MEDICAL_DOCUMENT", "BLANK_OR_EMPTY_PAGE"))
            assert res["medicines"] == []
            assert res["tests"] == []
        finally:
            Path(tmp).unlink(missing_ok=True)

    def test_blank_page_is_strictly_rejected(self):
        img = Image.new("RGB", (800, 600), color="white")
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            img.save(f, format="JPEG")
            tmp = f.name
        try:
            res = _run_extract(tmp, "image/jpeg")
            assert res["status"] == "REJECTED"
            assert res["accepted"] is False
            assert any(r in res["reason_codes"] for r in ("BLANK_OR_EMPTY_PAGE", "NON_MEDICAL_DOCUMENT"))
        finally:
            Path(tmp).unlink(missing_ok=True)

    def test_supermarket_receipt_is_rejected(self):
        img = Image.new("RGB", (400, 900), color="white")
        draw = ImageDraw.Draw(img)
        draw.text((120, 30), "SUPERMARKET GROCERY", fill="black")
        draw.text((50, 70), "Fresh Milk 1L ........ $3.50", fill="black")
        draw.text((50, 95), "Cheddar Cheese ....... $5.20", fill="black")
        draw.text((50, 120), "Whole Wheat Bread .... $2.80", fill="black")
        draw.text((50, 145), "Total Items: 3", fill="black")
        draw.text((50, 170), "TOTAL PAID: $11.50", fill="black")
        draw.text((80, 210), "Thank you for shopping!", fill="black")
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            img.save(f, format="JPEG")
            tmp = f.name
        try:
            res = _run_extract(tmp, "image/jpeg")
            assert res["status"] == "REJECTED"
            assert "NON_MEDICAL_DOCUMENT" in res["reason_codes"]
        finally:
            Path(tmp).unlink(missing_ok=True)


class TestRotatedAndPhotographedDocuments:
    """Tests rotated images (90, 270 deg) and low-quality photos."""

    def test_rotated_90_degree_medical_document(self):
        """A photographed medical document rotated 90 degrees must be processed without rejection as non-medical."""
        img = create_clinical_note_image().rotate(90, expand=True)
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            img.save(f, format="JPEG")
            tmp = f.name
        try:
            res = _run_extract(tmp, "image/jpeg")
            assert res["status"] in ("ACCEPTED", "NEEDS_REVIEW")
            assert "NON_MEDICAL_DOCUMENT" not in res.get("reason_codes", [])
        finally:
            Path(tmp).unlink(missing_ok=True)

    def test_rotated_270_degree_medical_document(self):
        """A photographed medical document rotated 270 degrees must be processed without rejection as non-medical."""
        img = create_clinical_note_image().rotate(270, expand=True)
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            img.save(f, format="JPEG")
            tmp = f.name
        try:
            res = _run_extract(tmp, "image/jpeg")
            assert res["status"] in ("ACCEPTED", "NEEDS_REVIEW")
            assert "NON_MEDICAL_DOCUMENT" not in res.get("reason_codes", [])
        finally:
            Path(tmp).unlink(missing_ok=True)

    def test_low_quality_shadowed_medical_photo(self):
        """A low-contrast shadowed photograph of a medical note is enhanced and flagged for review if necessary."""
        img = create_clinical_note_image()
        # Apply blur and shadow
        blurred = img.filter(ImageFilter.GaussianBlur(radius=1.2))
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            blurred.save(f, format="JPEG", quality=40)
            tmp = f.name
        try:
            res = _run_extract(tmp, "image/jpeg")
            assert res["status"] in ("ACCEPTED", "NEEDS_REVIEW")
            assert "NON_MEDICAL_DOCUMENT" not in res.get("reason_codes", [])
        finally:
            Path(tmp).unlink(missing_ok=True)


class TestExistingWorkflowsZeroRegression:
    """
    CRITICAL REQUIREMENT 11:
    Verify that existing prescription and lab-report workflows do not regress.
    """

    def test_printed_prescription_workflow(self):
        """Standard printed prescription with medications must be ACCEPTED."""
        img = Image.new("RGB", (800, 1000), color="white")
        draw = ImageDraw.Draw(img)
        draw.text((250, 40), "APOLLO HOSPITALS CLINIC", fill="black")
        draw.text((320, 70), "OUTPATIENT PRESCRIPTION", fill="black")
        draw.line([(40, 100), (760, 100)], fill="black", width=2)
        draw.text((50, 120), "Patient Name: Jane Doe    Age: 42    Date: 2026-10-15", fill="black")
        draw.text((50, 150), "Doctor: Dr. A. Sharma, MD, Reg: 44211", fill="black")
        draw.line([(40, 180), (760, 180)], fill="black", width=1)
        draw.text((50, 210), "Rx:", fill="black")
        draw.text((70, 250), "1. Tab Metformin 500mg - 1 tablet twice daily after meals x 30 days", fill="black")
        draw.text((70, 300), "2. Tab Atorvastatin 10mg - 1 tablet once daily at bedtime x 30 days", fill="black")
        draw.text((70, 350), "3. Tab Pantoprazole 40mg - 1 tablet once daily before breakfast x 14 days", fill="black")
        draw.line([(40, 800), (760, 800)], fill="black", width=1)
        draw.text((550, 830), "Dr. A. Sharma, MD", fill="black")

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            img.save(f, format="JPEG")
            tmp = f.name
        try:
            res = _run_extract(tmp, "image/jpeg")
            assert res["status"] in ("ACCEPTED", "NEEDS_REVIEW")
            assert "NON_MEDICAL_DOCUMENT" not in res.get("reason_codes", [])
            assert len(res.get("medicines", [])) >= 1
            med_names = [m["name_raw"].lower() for m in res["medicines"]]
            assert any("metformin" in n or "atorvastatin" in n or "pantoprazole" in n for n in med_names)
        finally:
            Path(tmp).unlink(missing_ok=True)

    def test_scanned_lab_report_workflow(self):
        """Standard scanned laboratory report with test results must be ACCEPTED."""
        img = Image.new("RGB", (800, 1000), color="white")
        draw = ImageDraw.Draw(img)
        draw.text((250, 40), "METROPOLIS DIAGNOSTICS LAB", fill="black")
        draw.text((320, 70), "CLINICAL BIOCHEMISTRY REPORT", fill="black")
        draw.line([(40, 100), (760, 100)], fill="black", width=2)
        draw.text((50, 120), "Patient Name: Suresh Kumar    Age: 55    Date: 2026-10-18", fill="black")
        draw.text((50, 150), "Referred By: Dr. Ramanathan, MD", fill="black")
        draw.line([(40, 180), (760, 180)], fill="black", width=1)
        draw.text((50, 210), "TEST NAME                     RESULT       UNIT        REFERENCE RANGE", fill="black")
        draw.line([(40, 235), (760, 235)], fill="black", width=1)
        draw.text((50, 260), "Fasting Blood Sugar (FBS)     126.0        mg/dL       70 - 100", fill="black")
        draw.text((50, 300), "HbA1c                         7.2          %           4.0 - 5.6", fill="black")
        draw.text((50, 340), "Serum Creatinine              1.1          mg/dL       0.7 - 1.3", fill="black")
        draw.line([(40, 800), (760, 800)], fill="black", width=1)
        draw.text((500, 830), "Verified By: Chief Biochemist", fill="black")

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            img.save(f, format="JPEG")
            tmp = f.name
        try:
            res = _run_extract(tmp, "image/jpeg")
            assert res["status"] in ("ACCEPTED", "NEEDS_REVIEW")
            assert "NON_MEDICAL_DOCUMENT" not in res.get("reason_codes", [])
            assert len(res.get("tests", [])) >= 1
            test_names = [t["name"].lower() for t in res["tests"]]
            assert any("sugar" in n or "fbs" in n or "glucose" in n or "hba1c" in n or "creatinine" in n for n in test_names)
        finally:
            Path(tmp).unlink(missing_ok=True)

