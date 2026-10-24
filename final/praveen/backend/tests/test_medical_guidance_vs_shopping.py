"""
test_medical_guidance_vs_shopping.py — Comprehensive Test Suite for Medical Guidance vs Product Shopping.

Verifies all 10 required test scenarios:
1. Prescription upload → medical extraction and explanation; no automatic shopping links.
2. Lab report upload → test results and relevant explanation; no unrelated products.
3. "Explain this medicine" → medical information; no purchase links by default.
4. "Find a digital thermometer to buy" → relevant product recommendations.
5. "Show alternatives to this blood pressure monitor" → comparable products with genuine links.
6. "Find a cheaper alternative to my prescribed medicine" → safe guidance; no automatic drug substitution.
7. Unclear handwritten medication → NEEDS_REVIEW; no guessed product recommendation.
8. Unrelated image → correct classification; no fabricated medical or shopping output.
9. No verified product results → honest unavailable state; no fabricated URLs.
10. New user query → intent determined from the actual query, not a hardcoded sample response.
Bonus: Verify medical reference links and product purchase links are correctly separated.
"""
import json
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import sys
from pathlib import Path

# Ensure ai_engine is discoverable
AI_ENGINE_ROOT = Path(__file__).resolve().parents[3] / "yogesh" / "healthcare_copilot_AI-Engine-main"
if str(AI_ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_ENGINE_ROOT))

from app.db import Base
from app.models import Profile, Record
from app.schemas import AskResponse
from app.services.ask import answer_question, classify_intent
from app.catalog.product_catalog import catalog_service, validate_safe_url


@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    # Seed profile
    prof = Profile(profile_id="test-patient-001", name="Aarav Sharma", relation="self")
    db.add(prof)

    # Seed prescription record
    rx_json = {
        "doc_type": "prescription",
        "doc_date": "2026-02-15",
        "medicines": [
            {
                "name_raw": "Metformin 500mg",
                "generic": "Metformin",
                "strength": "500 mg",
                "schedule_raw": "1-0-1",
                "food_instruction": "after_food",
                "duration_days": 30,
                "verification_state": "VERIFIED",
                "confidence": 0.95,
            },
            {
                "name_raw": "UnclearMed 10mg",
                "generic": None,
                "strength": "10 mg",
                "schedule_raw": "0-0-1",
                "food_instruction": "after_food",
                "verification_state": "REQUIRES_HUMAN_REVIEW",
                "confidence": 0.42,
            }
        ],
        "summary_en": "Patient prescribed Metformin 500mg twice daily after food for glycemic control.",
        "status": "ACCEPTED"
    }
    rec_rx = Record(
        record_id="rec-prescription-001",
        profile_id="test-patient-001",
        doc_type="prescription",
        doc_date="2026-02-15",
        status="confirmed",
        record_json=json.dumps(rx_json),
    )
    db.add(rec_rx)

    # Seed lab report record
    lab_json = {
        "doc_type": "lab_report",
        "doc_date": "2026-02-20",
        "tests": [
            {
                "name": "HbA1c",
                "value": 6.8,
                "unit": "%",
                "flag": "NORMAL",
                "ref_low": 4.0,
                "ref_high": 7.0,
                "loinc": "4548-4"
            },
            {
                "name": "Fasting Blood Glucose",
                "value": 110.0,
                "unit": "mg/dL",
                "flag": "NORMAL",
                "ref_low": 70.0,
                "ref_high": 100.0,
                "loinc": "1558-6"
            }
        ],
        "summary_en": "HbA1c is 6.8% indicating controlled diabetic state. Fasting glucose slightly borderline at 110 mg/dL.",
        "status": "ACCEPTED"
    }
    rec_lab = Record(
        record_id="rec-lab-001",
        profile_id="test-patient-001",
        doc_type="lab_report",
        doc_date="2026-02-20",
        status="confirmed",
        record_json=json.dumps(lab_json),
    )
    db.add(rec_lab)
    db.commit()

    yield db
    db.close()


# ── Test 1: Prescription Upload → Medical Extraction, No Automatic Shopping Links ─────────────
def test_1_prescription_upload_no_automatic_shopping_links(test_db):
    """Prescription review must explain clinical findings with zero unsolicited shopping links."""
    resp = answer_question(test_db, "test-patient-001", "Explain this prescription")

    assert resp.intent_category == "MEDICAL_INFORMATION"
    assert resp.product_recommendations == [], "Prescription queries must never include shopping links"
    assert resp.product_alternatives == [], "Prescription queries must never include product alternatives"
    assert "Metformin" in resp.answer or "prescribed" in resp.answer.lower()
    assert len(resp.medical_references) > 0, "Should include official medical reference links"
    for ref in resp.medical_references:
        assert ref.url.startswith("https://")


# ── Test 2: Lab Report Upload → Test Results, No Unrelated Products ───────────────────────────
def test_2_lab_report_upload_no_unrelated_products(test_db):
    """Lab report queries must explain biomarker results and reference intervals with zero product recommendations."""
    resp = answer_question(test_db, "test-patient-001", "What does my HbA1c test result mean?")

    assert resp.intent_category == "MEDICAL_INFORMATION"
    assert resp.product_recommendations == [], "Lab report queries must not contain product recommendations"
    assert resp.product_alternatives == [], "Lab report queries must not contain product alternatives"
    assert "6.8" in resp.answer
    assert "NORMAL" in resp.answer or "reference" in resp.answer.lower()
    assert any("loinc" in r.url.lower() or "nih" in r.url.lower() for r in resp.medical_references)


# ── Test 3: "Explain this medicine" → Medical Information, No Purchase Links ──────────────────
def test_3_explain_medicine_no_purchase_links_by_default(test_db):
    """'Explain this medicine' queries must return clinical pharmacology and instructions, NOT purchase links."""
    resp = answer_question(test_db, "test-patient-001", "What is this prescribed medicine generally used for?")

    assert resp.intent_category == "MEDICINE_QUERY"
    assert resp.product_recommendations == [], "Medicine queries must NEVER show purchase links by default"
    assert resp.product_alternatives == [], "Medicine queries must not show purchase alternatives"
    assert "Metformin" in resp.answer or "prescribed" in resp.answer.lower()
    assert "precautions" in resp.answer.lower() or "clinical" in resp.answer.lower()
    # Medical references are provided, not retailer links
    for ref in resp.medical_references:
        assert any(auth in ref.url for auth in ["medlineplus.gov", "cdsco.gov.in", "who.int"])


# ── Test 4: "Find a digital thermometer to buy" → Relevant Product Recommendations ───────────
def test_4_find_digital_thermometer_relevant_recommendations(test_db):
    """Explicit shopping intent for a thermometer must return verified products with genuine retailer links."""
    resp = answer_question(test_db, "test-patient-001", "Find a digital thermometer to buy")

    assert resp.intent_category == "PRODUCT_SHOPPING"
    assert len(resp.product_recommendations) > 0, "Must return product recommendations for explicit shopping query"

    primary = resp.product_recommendations[0]
    assert "thermometer" in primary.product_name.lower()
    assert primary.price_inr is not None and primary.price_inr > 0
    assert primary.retailer is not None
    assert primary.purchase_url is not None and primary.purchase_url.startswith("https://")

    # Validate URL against security whitelist
    is_safe, err = validate_safe_url(primary.purchase_url)
    assert is_safe, f"Purchase URL must be verified and safe: {err}"


# ── Test 5: "Show alternatives to this blood pressure monitor" → Comparable Products ──────────
def test_5_alternatives_to_blood_pressure_monitor(test_db):
    """Alternative requests must return comparable verified options with clear technical differences."""
    resp = answer_question(test_db, "test-patient-001", "Show alternatives to this blood pressure monitor")

    assert resp.intent_category == "PRODUCT_ALTERNATIVES"
    assert len(resp.product_alternatives) >= 1, "Must return at least 1 verified alternative"

    for alt in resp.product_alternatives:
        assert "blood pressure" in alt.product_name.lower() or "bp" in alt.product_name.lower()
        assert alt.price_inr is not None
        assert alt.comparison_notes is not None, "Alternatives must explain key differences"
        assert alt.purchase_url is not None and alt.purchase_url.startswith("https://")
        is_safe, _ = validate_safe_url(alt.purchase_url)
        assert is_safe, "Alternative URL must belong to authorized retailer whitelist"


# ── Test 6: "Find a cheaper alternative to my prescribed medicine" → Strict Safeguard ─────────
def test_6_find_cheaper_alternative_prescribed_medicine(test_db):
    """User asking to substitute prescription medicine must receive strict clinical safety advice, NOT automatic substitution."""
    resp = answer_question(test_db, "test-patient-001", "Find a cheaper alternative to my prescribed medicine")

    assert resp.intent_category == "MEDICINE_SUBSTITUTION_REQUEST"
    assert resp.product_recommendations == [], "Prescription drugs must NEVER be substituted automatically with shopping links"
    assert resp.product_alternatives == [], "Must not return substitute drug shopping links"
    assert resp.needs_clinician_review is True, "Must flag clinician review requirement"
    assert "pharmacist" in resp.answer.lower() or "physician" in resp.answer.lower()
    # References official PMBJP Jan Aushadhi portal for legitimate generic education
    assert any("janaushadhi.gov.in" in ref.url for ref in resp.medical_references)


# ── Test 7: Unclear Handwritten Medication → NEEDS_REVIEW, No Guessed Product ──────────────────
def test_7_unclear_handwritten_medication_needs_review(test_db):
    """If handwriting or dosage is uncertain, mark NEEDS_REVIEW and recommend confirmation with prescribing clinician."""
    resp = answer_question(test_db, "test-patient-001", "Explain the dosage written on this prescription for Unclearmed")

    assert resp.intent_category == "MEDICINE_QUERY"
    assert resp.needs_clinician_review is True, "Ambiguous/uncertain handwriting must flag needs_clinician_review"
    assert resp.product_recommendations == [], "Never guess a commercial purchase link for uncertain handwriting"
    assert any("unclear" in s.lower() or "physician" in s.lower() or "treating" in s.lower() for s in resp.safety_notes)


# ── Test 8: Unrelated Image / Non-Medical Validation ──────────────────────────────────────────
def test_8_unrelated_image_correct_classification():
    """Unrelated images (pets, scenery, invoices) must be classified as NON_MEDICAL without fake clinical records."""
    import os
    import tempfile
    from PIL import Image, ImageDraw
    from ai_engine.validator import validate_medical_document

    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        # Create an image with visual contrast and non-medical features (e.g., photo banner)
        im = Image.new("RGB", (300, 300), color=(100, 150, 200))
        draw = ImageDraw.Draw(im)
        draw.rectangle([20, 20, 280, 140], fill=(240, 200, 100))
        draw.text((30, 40), "OUTDOOR PET PHOTOGRAPHY", fill=(20, 20, 20))
        draw.text((30, 70), "ORANGE CAT IN GARDEN SCENERY", fill=(20, 20, 20))
        im.save(tmp.name, "JPEG")
        tmp_path = tmp.name

    try:
        res = validate_medical_document(
            file_path=tmp_path,
            images=[im],
            fallback_text="Cute orange cat sitting on green grass in sunlight with flowers pet photography",
            claimed_mime="image/jpeg",
        )
        assert res.decision == "REJECTED"
        assert res.document_type == "NON_MEDICAL"
        assert "NON_MEDICAL_DOCUMENT" in res.reason_codes or "DETECTED_NON_MEDICAL_CONTENT" in res.reason_codes
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


# ── Test 9: No Verified Product Results → Honest Unavailable State, No Fabricated URLs ─────────
def test_9_no_verified_product_results_honest_unavailable_state(test_db):
    """When a requested product is not in the authorized catalog, state unavailable honestly instead of fabricating links."""
    resp = answer_question(test_db, "test-patient-001", "Find a hospital MRI scanner to buy")

    assert resp.intent_category == "PRODUCT_SHOPPING"
    assert resp.product_recommendations == [], "Must not fabricate product recommendations for unverified items"
    assert resp.product_alternatives == [], "Must not fabricate alternative links"
    assert "no verified" in resp.answer.lower() or "not generate unverified" in resp.answer.lower()


# ── Test 10: New User Query → Intent Determined from Actual Query ─────────────────────────────
def test_10_new_user_query_dynamic_intent_determination():
    """Intent must be dynamically determined from actual query semantics, not hardcoded strings."""
    assert classify_intent("Where can I buy a pulse oximeter for my grandmother?") == "PRODUCT_SHOPPING"
    assert classify_intent("What are the precautions associated with Metformin 500mg?") == "MEDICINE_QUERY"
    assert classify_intent("Can I replace my prescribed tablet with a cheaper option?") == "MEDICINE_SUBSTITUTION_REQUEST"
    assert classify_intent("Compare available glucometers in the market") == "PRODUCT_ALTERNATIVES"
    assert classify_intent("Please explain my fasting blood sugar test result") == "MEDICAL_INFORMATION"
    assert classify_intent("Hello, how are you feeling today?") == "GENERAL_CONVERSATIONAL"


# ── Test 11: Medical Reference Links vs Product Purchase Links Separated ───────────────────────
def test_11_separation_of_medical_references_and_purchase_links(test_db):
    """Medical reference links and product purchase links must occupy distinct fields with strict schemas."""
    # Medical query: medical_references populated, product_recommendations empty
    med_resp = answer_question(test_db, "test-patient-001", "What is Metformin used for?")
    assert len(med_resp.medical_references) > 0
    assert len(med_resp.product_recommendations) == 0

    # Device query: product_recommendations populated with retailer links
    shop_resp = answer_question(test_db, "test-patient-001", "Recommend a blood pressure monitor to buy")
    assert len(shop_resp.product_recommendations) > 0
    prod = shop_resp.product_recommendations[0]
    assert prod.purchase_url is not None
    assert any(dom in prod.purchase_url for dom in ["omron-healthcare.in", "apollopharmacy.in", "1mg.com", "beurerindia.com"])
