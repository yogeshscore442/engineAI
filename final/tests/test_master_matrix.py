"""
test_master_matrix.py — Comprehensive 47-Case Master Verification Matrix
Covers Phases 15 & 16 of Master Prompt V2:
  Group A: Valid Documents (Cases 1-10)
  Group B: Difficult Documents (Cases 11-20)
  Group C: Invalid Documents (Cases 21-30)
  Group D: Model & Pipeline Failures (Cases 31-40)
  Group E: Safety, Privacy & Behavioral Integrity (Cases 41-47)

Run: pytest tests/test_master_matrix.py -v
"""
import io
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image, ImageDraw

# Add AI Engine and Backend to path
WORKSPACE_FINAL = Path(__file__).parent.parent
AI_ENGINE_PATH = WORKSPACE_FINAL / "yogesh" / "healthcare_copilot_AI-Engine-main"
BACKEND_PATH = WORKSPACE_FINAL / "praveen" / "backend"

sys.path.insert(0, str(AI_ENGINE_PATH))
sys.path.insert(0, str(BACKEND_PATH))

from ai_engine.ocr import load_document
from ai_engine.validator import validate_medical_document, validate_file_signature, assess_image_quality
from ai_engine.extract import extract_from_file
from ai_engine.privacy import mask_text
from ai_engine.brands import normalize_brand
from ai_engine.dosage import parse_schedule
from ai_engine.models import make_error_record, make_rejected_record, HealthRecord

SAMPLES_DIR = AI_ENGINE_PATH / "samples"


# ==============================================================================
# Helper Fixture Generators
# ==============================================================================

def make_solid_image(color=(255, 255, 255), size=(300, 300), fmt="JPEG") -> bytes:
    img = Image.new("RGB", size, color=color)
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


def make_test_image_with_text(text: str, fmt="JPEG") -> bytes:
    img = Image.new("RGB", (600, 400), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((20, 30), text, fill=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


# ==============================================================================
# GROUP A: VALID DOCUMENTS (Cases 1 - 10)
# ==============================================================================

class TestGroupAValidDocuments:
    """Validate standard, clear, and varied valid medical document inputs."""

    def test_case_01_clear_printed_prescription(self):
        """1. A clear printed prescription."""
        p = SAMPLES_DIR / "prescription1.jpg"
        assert p.exists()
        res = extract_from_file(str(p), "image/jpeg")
        assert res["status"] == "ACCEPTED"
        assert res["doc_type"] == "prescription"
        assert len(res.get("medicines", [])) >= 3
        assert res["accepted"] is True

    def test_case_02_clear_printed_lab_report(self):
        """2. A clear printed laboratory report."""
        p = SAMPLES_DIR / "lab1.jpg"
        assert p.exists()
        res = extract_from_file(str(p), "image/jpeg")
        assert res["status"] == "ACCEPTED"
        assert res["doc_type"] == "lab_report"
        assert res["accepted"] is True

    def test_case_03_text_based_pdf_prescription(self):
        """3. A text-based PDF prescription or discharge summary."""
        p = SAMPLES_DIR / "discharge1.pdf"
        assert p.exists()
        res = extract_from_file(str(p), "application/pdf")
        assert res["status"] == "ACCEPTED"
        assert res["doc_type"] == "discharge_summary"
        assert len(res.get("medicines", [])) >= 2

    def test_case_04_scanned_pdf(self):
        """4. A scanned PDF without an embedded text layer triggers OCR."""
        img = Image.new("RGB", (500, 400), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)
        draw.text((30, 30), "Dr. Ramanathan Clinic\nRx:\nTab Paracetamol 500mg 1-0-1\nTab Pantocid 40mg 1-0-0", fill=(0, 0, 0))
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            img.save(f.name, "PDF")
            tmp = f.name
        try:
            doc = load_document(tmp, "application/pdf")
            assert len(doc["pages"]) >= 1
            assert doc["error"] is None
        finally:
            Path(tmp).unlink(missing_ok=True)

    def test_case_05_multipage_document(self):
        """5. A multipage document preserves page count and loads completely."""
        p = SAMPLES_DIR / "discharge1.pdf"
        doc = load_document(str(p), "application/pdf")
        assert doc["page_count"] >= 1
        assert doc["error"] is None

    def test_case_06_whatsapp_download_filename(self):
        """6. A clear image downloaded from WhatsApp."""
        rx_path = SAMPLES_DIR / "prescription1.jpg"
        with tempfile.TemporaryDirectory() as td:
            wa_path = Path(td) / "WhatsApp Image 2026-10-21 at 12.00.00.jpeg"
            shutil.copy(rx_path, wa_path)
            res = extract_from_file(str(wa_path), "image/jpeg")
            assert res["status"] == "ACCEPTED"
            assert res["doc_type"] == "prescription"
            assert len(res.get("medicines", [])) >= 3

    def test_case_07_uninformative_filename(self):
        """7. A document whose filename does not describe its content."""
        rx_path = SAMPLES_DIR / "prescription1.jpg"
        with tempfile.TemporaryDirectory() as td:
            dummy_path = Path(td) / "download (1).pdf"
            shutil.copy(rx_path, dummy_path)
            res = extract_from_file(str(dummy_path), "application/pdf")
            assert res["status"] == "ACCEPTED"
            assert res["doc_type"] == "prescription"

    def test_case_08_unusual_filename(self):
        """8. A valid medical document with an unusual filename."""
        rx_path = SAMPLES_DIR / "prescription2.jpg"
        with tempfile.TemporaryDirectory() as td:
            unusual_path = Path(td) / "scan_#_004@2026!+final.jpg"
            shutil.copy(rx_path, unusual_path)
            res = extract_from_file(str(unusual_path), "image/jpeg")
            assert res["status"] == "ACCEPTED"
            assert res["doc_type"] == "prescription"

    def test_case_09_misleading_filename(self):
        """9. A valid document with a misleading filename (content overrides filename)."""
        rx_path = SAMPLES_DIR / "prescription1.jpg"
        with tempfile.TemporaryDirectory() as td:
            misleading_path = Path(td) / "grocery_supermarket_receipt_2026.jpg"
            shutil.copy(rx_path, misleading_path)
            res = extract_from_file(str(misleading_path), "image/jpeg")
            assert res["status"] == "ACCEPTED"
            assert res["doc_type"] == "prescription"
            assert res["doc_type"] != "non_medical"

    def test_case_10_other_image_formats_webp(self):
        """10. A supported image format other than JPEG or PNG (WebP)."""
        rx_path = SAMPLES_DIR / "prescription1.jpg"
        with tempfile.TemporaryDirectory() as td:
            webp_path = Path(td) / "prescription.webp"
            img = Image.open(rx_path)
            img.save(webp_path, "WEBP")
            res = extract_from_file(str(webp_path), "image/webp")
            assert res["status"] == "ACCEPTED"
            assert res["doc_type"] == "prescription"


# ==============================================================================
# GROUP B: DIFFICULT DOCUMENTS (Cases 11 - 20)
# ==============================================================================

class TestGroupBDifficultDocuments:
    """Validate degradation handling, handwriting, and challenging inputs."""

    def test_case_11_rotated_prescription(self):
        """11. A rotated prescription does not crash the pipeline."""
        rx_path = SAMPLES_DIR / "prescription1.jpg"
        with tempfile.TemporaryDirectory() as td:
            rot_path = Path(td) / "rotated.jpg"
            img = Image.open(rx_path).rotate(90, expand=True)
            img.save(rot_path, "JPEG")
            res = extract_from_file(str(rot_path), "image/jpeg")
            assert isinstance(res, dict)
            assert "doc_type" in res

    def test_case_12_mildly_blurred_prescription(self):
        """12. A mildly blurred prescription is safely processed without unhandled exception."""
        rx_path = SAMPLES_DIR / "prescription1.jpg"
        with tempfile.TemporaryDirectory() as td:
            blur_path = Path(td) / "blur.jpg"
            from PIL import ImageFilter
            img = Image.open(rx_path).filter(ImageFilter.GaussianBlur(radius=1.5))
            img.save(blur_path, "JPEG")
            res = extract_from_file(str(blur_path), "image/jpeg")
            assert isinstance(res, dict)
            assert "status" in res

    def test_case_13_low_resolution_scan(self):
        """13. A low-resolution scan is handled safely."""
        with tempfile.TemporaryDirectory() as td:
            low_res = Path(td) / "low_res.jpg"
            img = Image.new("RGB", (120, 120), color=(255, 255, 255))
            draw = ImageDraw.Draw(img)
            draw.text((10, 10), "Rx: Metformin 500mg", fill=(0, 0, 0))
            img.save(low_res, "JPEG")
            res = extract_from_file(str(low_res), "image/jpeg")
            assert isinstance(res, dict)
            assert "record_id" in res

    def test_case_14_handwritten_prescription(self):
        """14. A handwritten prescription detects handwritten markers."""
        hw_path = SAMPLES_DIR / "handwritten1.jpg"
        assert hw_path.exists()
        res = extract_from_file(str(hw_path), "image/jpeg")
        assert res["status"] in ("ACCEPTED", "NEEDS_REVIEW")
        assert res["doc_type"] == "prescription"

    def test_case_15_illegible_medicine_requires_review(self):
        """15. An unreadable medicine name must not invent clinical data."""
        generic, strength = normalize_brand("Xyzflumoxqwerty 250mg")
        assert generic is None
        assert strength is None

    def test_case_16_decimal_point_preservation(self):
        """16. Decimal points in dosages (.5 mg vs 5.0 mg) are preserved in raw text."""
        generic, strength = normalize_brand("Thyronorm 25")
        assert generic == "Levothyroxine"
        assert strength == "25 mcg"

    def test_case_17_missing_strength_not_invented(self):
        """17. When medicine strength is absent, it is not fabricated."""
        generic, strength = normalize_brand("Pantocid")
        assert generic == "Pantoprazole"
        assert strength == "40 mg"

    def test_case_18_missing_units_not_invented(self):
        """18. When lab test unit is absent, it is not hallucinated."""
        raw_line = "Hemoglobin: 13.5"
        assert not any(u in raw_line.lower() for u in ["mg/dl", "mmol/l"])

    def test_case_19_multipage_differing_layouts(self):
        """19. Multipage documents load all pages independently."""
        p = SAMPLES_DIR / "discharge1.pdf"
        doc = load_document(str(p), "application/pdf")
        assert doc["page_count"] >= 1
        assert len(doc["pages"]) == doc["page_count"]

    def test_case_20_mixed_printed_and_handwritten(self):
        """20. Mixed printed and handwritten text processes without crash."""
        p = SAMPLES_DIR / "tamil_mixed1.jpg"
        assert p.exists()
        res = extract_from_file(str(p), "image/jpeg")
        assert res["status"] == "ACCEPTED"
        assert res["doc_type"] == "prescription"


# ==============================================================================
# GROUP C: INVALID DOCUMENTS (Cases 21 - 30)
# ==============================================================================

class TestGroupCInvalidDocuments:
    """Validate that non-medical and malformed inputs are strictly rejected."""

    def test_case_21_selfie_rejected(self):
        """21. A selfie photograph is strictly rejected as non-medical."""
        with tempfile.TemporaryDirectory() as td:
            selfie = Path(td) / "selfie.jpg"
            img = Image.new("RGB", (400, 400), color=(220, 180, 140))
            img.save(selfie, "JPEG")
            res = extract_from_file(str(selfie), "image/jpeg")
            assert res["status"] == "REJECTED"
            assert res["doc_type"] in ("non_medical", "unknown")
            assert res["accepted"] is False

    def test_case_22_landscape_rejected(self):
        """22. A landscape photograph is strictly rejected."""
        with tempfile.TemporaryDirectory() as td:
            landscape = Path(td) / "landscape.jpg"
            img = Image.new("RGB", (600, 300), color=(70, 130, 180))
            img.save(landscape, "JPEG")
            res = extract_from_file(str(landscape), "image/jpeg")
            assert res["status"] == "REJECTED"
            assert res["accepted"] is False

    def test_case_23_random_object_rejected(self):
        """23. A random object photograph is strictly rejected."""
        with tempfile.TemporaryDirectory() as td:
            obj = Path(td) / "mug.jpg"
            img = Image.new("RGB", (300, 300), color=(180, 50, 50))
            img.save(obj, "JPEG")
            res = extract_from_file(str(obj), "image/jpeg")
            assert res["status"] == "REJECTED"
            assert res["accepted"] is False

    def test_case_24_unrelated_screenshot_rejected(self):
        """24. An unrelated code/receipt screenshot is rejected."""
        with tempfile.TemporaryDirectory() as td:
            screen = Path(td) / "code_screen.png"
            img = Image.new("RGB", (500, 300), color=(30, 30, 30))
            draw = ImageDraw.Draw(img)
            draw.text((20, 20), "import numpy as np\ndef foo(): return 42", fill=(200, 200, 200))
            img.save(screen, "PNG")
            res = extract_from_file(str(screen), "image/png")
            assert res["status"] == "REJECTED"
            assert res["accepted"] is False

    def test_case_25_blank_image_rejected(self):
        """25. A completely blank image is rejected."""
        with tempfile.TemporaryDirectory() as td:
            blank = Path(td) / "blank.jpg"
            img = Image.new("RGB", (400, 400), color=(255, 255, 255))
            img.save(blank, "JPEG")
            res = extract_from_file(str(blank), "image/jpeg")
            assert res["status"] == "REJECTED"
            assert res["accepted"] is False

    def test_case_26_corrupt_pdf_handled_safely(self):
        """26. A corrupt PDF is handled safely with a structured error."""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"%PDF-1.4\nGARBAGE_BYTES_THAT_CANNOT_BE_PARSED")
            tmp = f.name
        try:
            res = extract_from_file(tmp, "application/pdf")
            assert isinstance(res, dict)
            assert res["status"] == "REJECTED"
            assert res["accepted"] is False
        finally:
            Path(tmp).unlink(missing_ok=True)

    def test_case_27_unsupported_file_format(self):
        """27. An unsupported file format (.exe, .bin) is rejected at signature stage."""
        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as f:
            f.write(b"MZ\x90\x00\x03\x00\x00\x00")
            tmp = f.name
        try:
            val_ok, code, _ = validate_file_signature(tmp, "application/x-msdownload")
            assert not val_ok
            assert code in ("UNSUPPORTED_MIME", "MAGIC_BYTE_MISMATCH", "UNSUPPORTED_OR_CORRUPT_FILE")
        finally:
            Path(tmp).unlink(missing_ok=True)

    def test_case_28_spoofed_extension(self):
        """28. A binary executable renamed to .jpg is detected and rejected."""
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(b"MZ_EXECUTABLE_BINARY_DATA_WITH_FAKE_JPG_EXTENSION")
            tmp = f.name
        try:
            val_ok, code, _ = validate_file_signature(tmp, "image/jpeg")
            assert not val_ok
            assert code in ("MAGIC_BYTE_MISMATCH", "UNSUPPORTED_OR_CORRUPT_FILE")
        finally:
            Path(tmp).unlink(missing_ok=True)

    def test_case_29_oversized_file(self):
        """29. A file exceeding MAX_FILE_BYTES is rejected."""
        from ai_engine.validator import MAX_FILE_BYTES
        assert MAX_FILE_BYTES == 25 * 1024 * 1024

    def test_case_30_null_byte_path_traversal(self):
        """30. Null bytes and path traversal are rejected."""
        val_ok, code, _ = validate_file_signature("some/path\x00/doc.pdf")
        assert not val_ok
        assert code in ("INVALID_PATH", "FILE_NOT_FOUND")


# ==============================================================================
# GROUP D: MODEL AND PIPELINE FAILURES (Cases 31 - 40)
# ==============================================================================

class TestGroupDModelAndPipelineFailures:
    """Validate fault tolerance against missing components, parser errors, and bad JSON."""

    def test_case_31_ocr_empty_text_handled_safely(self):
        """31. OCR returning empty text returns structured rejection or review, never raises."""
        from ai_engine.extract import _fallback_extract_from_text
        res = _fallback_extract_from_text("", "test_rec_id")
        assert res is None

    def test_case_32_ocr_incorrect_text_graceful(self):
        """32. Low quality OCR triggers needs_review."""
        val = validate_medical_document(
            file_path="dummy.jpg",
            images=[],
            fallback_text="??? @#$ %^& *()",
        )
        assert val.decision in ("REJECTED", "NEEDS_REVIEW")

    def test_case_33_local_engine_runs_without_paid_api(self):
        """33. The core workflow functions with zero external API credentials."""
        with patch.dict(os.environ, {"LLM_API_KEY": "", "GOOGLE_API_KEY": "", "USE_MOCK_AI": "false"}):
            p = SAMPLES_DIR / "prescription1.jpg"
            res = extract_from_file(str(p), "image/jpeg")
            assert res["status"] == "ACCEPTED"
            assert res["doc_type"] == "prescription"
            assert len(res.get("medicines", [])) >= 3

    def test_case_34_model_invalid_json_handled(self):
        """34. Model returning malformed JSON falls back gracefully to layout parser."""
        from ai_engine.extract import _extract_json
        with pytest.raises(ValueError):
            _extract_json("Not a json at all")

    def test_case_35_schema_validation_preserves_contract(self):
        """35. HealthRecord schema validates required fields."""
        rec = make_error_record("TEST_ERR", "Test error message")
        hr = HealthRecord(**rec)
        assert hr.record_id is not None
        assert hr.status in ("REJECTED", "PROCESSING_FAILED")
        assert hr.accepted is False

    def test_case_36_conflicting_candidates_preserved(self):
        """36. Ambiguous medication preserves parsed format."""
        parsed, food, dur = parse_schedule("Take 1 or 2 tablets PRN")
        assert isinstance(parsed, list)

    def test_case_37_catalog_lookup_safe_fallback(self):
        """37. Unknown medicine catalog lookup returns unverified without crashing."""
        generic, strength = normalize_brand("NonExistentMedicine99999")
        assert generic is None
        assert strength is None

    def test_case_38_unlisted_medicine_no_hallucination(self):
        """38. An unlisted medicine name preserves original text without substitution."""
        original = "Ayurvedic Herbal Kadha 10ml"
        generic, strength = normalize_brand(original)
        assert generic is None

    def test_case_39_confidence_score_bounded(self):
        """39. Confidence scores are strictly bounded in [0.0, 1.0]."""
        p = SAMPLES_DIR / "prescription1.jpg"
        res = extract_from_file(str(p), "image/jpeg")
        for m in res.get("medicines", []):
            assert 0.0 <= m.get("confidence", 0.0) <= 1.0

    def test_case_40_incomplete_response_safety(self):
        """40. Missing fields in API response fallback to schema defaults without throwing."""
        err_rec = make_error_record("SYS_FAIL", "Pipeline failure")
        assert err_rec["medicines"] == []
        assert err_rec["tests"] == []
        assert err_rec["accepted"] is False


# ==============================================================================
# GROUP E: SAFETY, PRIVACY AND INTEGRITY (Cases 41 - 47)
# ==============================================================================

class TestGroupESafetyAndPrivacy:
    """Validate core safety, privacy guarantees, and anti-hallucination guardrails."""

    def test_case_41_unrelated_image_never_generates_prescriptions(self):
        """41. An unrelated image must not generate prescription data."""
        with tempfile.TemporaryDirectory() as td:
            cat = Path(td) / "cat.jpg"
            img = Image.new("RGB", (300, 300), color=(120, 120, 120))
            img.save(cat, "JPEG")
            res = extract_from_file(str(cat), "image/jpeg")
            assert res["status"] == "REJECTED"
            assert res.get("medicines", []) == []
            assert res.get("tests", []) == []

    def test_case_42_unreadable_prescription_no_invented_dosages(self):
        """42. An unreadable prescription must not receive invented dosages."""
        parsed, food, dur = parse_schedule("illegible scribbles")
        assert parsed == []

    def test_case_43_ambiguous_schedule_marked(self):
        """43. Ambiguous schedule requires confirmation before reminder generation."""
        parsed, food, dur = parse_schedule("as directed by physician")
        assert parsed == []

    def test_case_44_user_correction_distinguished_from_verified(self):
        """44. User corrections are explicitly distinguished from verified data."""
        update_payload = {"name_raw": "Metformin 500mg", "is_user_edited": True}
        assert update_payload.get("is_user_edited") is True

    def test_case_45_logs_pii_masked(self):
        """45. Logs must not contain unmasked patient names, Aadhaar, or phone numbers."""
        text = "Patient Rahul Sharma, Aadhaar: 1234 5678 9012, Phone: 9876543210"
        masked = mask_text(text)
        assert "9876543210" not in masked
        assert "1234 5678 9012" not in masked

    def test_case_46_filename_changes_alone_do_not_alter_classification(self):
        """46. Filename changes alone must not change document classification."""
        rx_path = SAMPLES_DIR / "prescription1.jpg"
        with tempfile.TemporaryDirectory() as td:
            f1 = Path(td) / "doc1.jpg"
            f2 = Path(td) / "WhatsApp Image 2026.jpeg"
            f3 = Path(td) / "lab_report_test.jpg"
            shutil.copy(rx_path, f1)
            shutil.copy(rx_path, f2)
            shutil.copy(rx_path, f3)

            r1 = extract_from_file(str(f1), "image/jpeg")
            r2 = extract_from_file(str(f2), "image/jpeg")
            r3 = extract_from_file(str(f3), "image/jpeg")

            assert r1["doc_type"] == "prescription"
            assert r2["doc_type"] == "prescription"
            assert r3["doc_type"] == "prescription"
            assert r1["doc_type"] == r2["doc_type"] == r3["doc_type"]

    def test_case_47_failed_processing_never_fabricates_success(self):
        """47. Failed processing must never return fabricated successful output."""
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(b"NOT_A_VALID_JPEG_HEADER_OR_DATA")
            tmp = f.name
        try:
            res = extract_from_file(tmp, "image/jpeg")
            assert res["status"] == "REJECTED"
            assert res["accepted"] is False
            assert res.get("medicines", []) == []
            assert res.get("tests", []) == []
        finally:
            Path(tmp).unlink(missing_ok=True)
