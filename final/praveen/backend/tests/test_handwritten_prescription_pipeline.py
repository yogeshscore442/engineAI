import json
import os
import sys
from pathlib import Path
import pytest

from app.services.pipeline import is_possible_medical, run_confirm_pipeline
from app.repositories import records_repo

# Ensure AI Engine is on sys.path for direct component tests
ai_engine_root = os.environ.get("AI_ENGINE_ROOT") or str(Path(__file__).resolve().parent.parent.parent / "yogesh" / "healthcare_copilot_AI-Engine-main")
if ai_engine_root not in sys.path:
    sys.path.insert(0, ai_engine_root)


def test_is_possible_medical_handles_all_review_types():
    """
    Verifies that is_possible_medical correctly recognizes all intermediate
    review types including UNKNOWN_REQUIRES_REVIEW, POSSIBLE_MEDICAL_DOCUMENT_NEEDS_REVIEW,
    and CLINICAL_NOTE.
    """
    assert is_possible_medical({"document_type": "POSSIBLE_MEDICAL_DOCUMENT_NEEDS_REVIEW"}) is True
    assert is_possible_medical({"document_type": "UNKNOWN_REQUIRES_REVIEW"}) is True
    assert is_possible_medical({"document_type": "CLINICAL_NOTE"}) is True
    assert is_possible_medical({"document_type": "PRESCRIPTION"}) is True
    assert is_possible_medical({"document_type": "LAB_REPORT"}) is True
    assert is_possible_medical({"document_type": "NON_MEDICAL"}) is False
    assert is_possible_medical({"doc_type": "non_medical"}) is False


def test_confirm_pipeline_marks_candidate_medicines_as_verified(db, default_profile_id):
    """
    Verifies that run_confirm_pipeline marks user-reviewed candidate medicines
    with verification_state = 'VERIFIED_BY_USER' and user_confirmed = True.
    """
    doc_id = "test-doc-handwritten-confirm-1"
    draft_json = {
        "record_id": doc_id,
        "doc_type": "prescription",
        "status": "draft",
        "ocr_text": "Rx Telma 40 1-0-0",
        "medicines": [
            {
                "name": "Telma",
                "strength": "40 mg",
                "dosage": "1-0-0",
                "verification_state": "UNVERIFIED_CANDIDATE",
                "source_text": "Telma 40 1-0-0",
                "user_confirmed": False,
            }
        ],
        "tests": [],
        "diagnoses": [],
    }

    # Create draft in DB
    record = records_repo.create_record(
        db,
        record_id=doc_id,
        profile_id=default_profile_id,
        doc_type="prescription",
        doc_date="2026-10-21",
        status="draft",
        file_path="dummy.jpg",
        file_sha256="dummy_sha256_handwritten",
        record_json=json.dumps(draft_json),
        schema_version=1,
        source="local_ocr",
        language="en",
        needs_review=True,
        headline="Prescription - Telma 40 mg",
    )

    confirmed_payload = {
        "doc_type": "prescription",
        "doc_date": "2026-10-21",
        "medicines": [
            {
                "name": "Telma",
                "strength": "40 mg",
                "dosage": "1-0-0",
                "frequency": "Once daily",
            }
        ],
        "tests": [],
        "diagnoses": [],
    }

    updated_record = run_confirm_pipeline(db, record, confirmed_payload)
    assert updated_record is not None
    confirmed_data = json.loads(updated_record.record_json)
    confirmed_meds = confirmed_data.get("medicines", [])
    assert len(confirmed_meds) == 1
    assert confirmed_meds[0]["verification_state"] == "VERIFIED_BY_USER"
    assert confirmed_meds[0]["user_confirmed"] is True


def test_candidate_medicines_preserve_provenance():
    """
    Verifies that when AI extraction produces unverified candidates,
    they retain verification_state and source_text fields for clinical auditing.
    """
    from ai_engine.extract import _fallback_extract_from_text

    raw_text = "Dr. Rao\nRx\nTab Moxclav 625 1-0-1 5 days\n"
    extracted = _fallback_extract_from_text(raw_text, "test-prov-1")

    assert extracted is not None
    meds = extracted.get("medicines", [])
    assert len(meds) >= 1
    mox = meds[0]
    assert "source_text" in mox
    assert mox["source_text"] is not None
    assert mox.get("verification_state") in ("VERIFIED", "UNVERIFIED_CANDIDATE")
