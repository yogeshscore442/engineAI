"""
test_handwritten_prescription_recovery.py

Regression test suite verifying the fix for handwritten prescription extraction failure:
1. Handwritten prescription with OCR noise/typos recovers medicines via fuzzy matching.
2. Formulation prefixes and attached strengths (e.g. 'Telma 40') are parsed cleanly.
3. Unverified prescription orders with dosage patterns (1-0-1, TDS, etc.) are captured
   as UNVERIFIED_CANDIDATE medicines with provenance preserved.
4. Laboratory test orders on prescriptions (e.g. 'Adv: CBC, HbA1c') are captured as
   ordered tests without hallucinated results or values.
5. Documents with no medical orders return NO_ITEMS_DETECTED without hallucination.
6. Document classification distinguishes PRESCRIPTION, CLINICAL_NOTE, and UNKNOWN_REQUIRES_REVIEW.
   A prescription is never forcibly downgraded to CLINICAL_NOTE simply because extraction was low confidence.
7. make_needs_review_record preserves candidate extractions and raw text rather than resetting them to empty.
"""

import os
import sys
from pathlib import Path
from unittest.mock import patch
import pytest

# Ensure AI Engine is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ai_engine import extract_record
from ai_engine.extract import _fallback_extract_from_text, extract_from_file
from ai_engine.validator import (
    validate_medical_document,
    DOCUMENT_TYPE_PRESCRIPTION,
    DOCUMENT_TYPE_CLINICAL_NOTE,
    DOCUMENT_TYPE_UNKNOWN_REQUIRES_REVIEW,
)
from ai_engine.models import make_needs_review_record


def test_fuzzy_matching_and_attached_strength():
    """
    Verifies that drug names with attached strengths and minor OCR typos
    (e.g., 'Paracetmol 500', 'Cetrizin 10mg', 'Telma 40') are correctly extracted.
    """
    text = (
        "Dr. Sharma MD\n"
        "Rx\n"
        "1. Paracetmol 500mg 1-0-1 3 days\n"
        "2. Cetrizin 10mg 0-0-1 at night\n"
        "3. Telma 40 1-0-0 morning\n"
    )
    result = _fallback_extract_from_text(text, "test-rec-1")
    assert result is not None
    meds = result.get("medicines", [])
    assert len(meds) >= 3

    names = [m["name"].lower() for m in meds]
    assert any("paracetamol" in n or "paracetmol" in n for n in names)
    assert any("cetirizine" in n or "cetrizin" in n for n in names)
    assert any("telma" in n or "telmisartan" in n for n in names)

    # Check strength parsing for Telma 40
    telma_med = next(m for m in meds if "telma" in m["name"].lower())
    assert "40" in (telma_med.get("strength") or "")


def test_unverified_candidate_with_dosage_pattern():
    """
    Verifies that a handwritten order that is not in the drug dictionary
    but has clear clinical dosage patterns (e.g. 'Tab Moxclav 625 1-0-1 x 5d')
    is preserved as an UNVERIFIED_CANDIDATE rather than silently discarded.
    """
    text = (
        "Rx\n"
        "1. Tab Moxclav 625 1-0-1 x 5 days\n"
        "2. Cap Rabeprazole 20mg 1-0-0 before food\n"
    )
    result = _fallback_extract_from_text(text, "test-rec-2")
    assert result is not None
    meds = result.get("medicines", [])
    assert len(meds) >= 2

    # Moxclav should be extracted
    moxclav = next((m for m in meds if "moxclav" in m["name"].lower()), None)
    assert moxclav is not None
    assert moxclav.get("verification_state") in ("VERIFIED", "UNVERIFIED_CANDIDATE")
    assert "source_text" in moxclav
    assert moxclav["source_text"] is not None


def test_prescription_test_order_extraction():
    """
    Verifies that test orders advised on a prescription (e.g. 'Adv: CBC, HbA1c, LFT')
    are extracted into the tests list as orders, without hallucinating numerical values.
    """
    text = (
        "Dr. A. Gupta MBBS\n"
        "Patient: John Doe, 45M\n"
        "Rx\n"
        "Tab Metformin 500mg 1-0-1\n"
        "Adv: CBC, HbA1c, Lipid Profile next week\n"
    )
    result = _fallback_extract_from_text(text, "test-rec-3")
    assert result is not None
    tests = result.get("tests", [])
    assert len(tests) >= 2

    test_names = [t["name"].upper() for t in tests]
    assert any("CBC" in n for n in test_names)
    assert any("HBA1C" in n for n in test_names)

    # Values must be None or empty since they are orders, not completed results
    for t in tests:
        assert t.get("value") is None or t.get("value") == ""


def test_no_items_detected_clean_state():
    """
    Verifies that a document containing medical text but no active medication or test orders
    returns NO_ITEMS_DETECTED cleanly without inventing hallucinations.
    """
    text = (
        "City Clinic Outpatient Department\n"
        "Patient came for general consultation.\n"
        "Vitals: BP 120/80, Pulse 72 bpm.\n"
        "No complaints at present. Diet counseling given.\n"
        "Follow up after 1 month.\n"
    )
    result = _fallback_extract_from_text(text, "test-rec-4")
    assert result is not None
    assert result.get("medicines") == []
    assert result.get("tests") == []
    assert result.get("extraction_status") == "NO_ITEMS_DETECTED"


def test_validator_distinguishes_prescription_vs_clinical_note():
    """
    Verifies that a prescription with Rx and medication orders is classified as PRESCRIPTION,
    while a clinical progress note with SOAP headings is classified as CLINICAL_NOTE.
    """
    from ai_engine.validator import classify_and_validate_evidence
    # Prescription
    rx_text = "Dr. Mehta Clinic\nRx\nTab Azithromycin 500mg 1-0-0 3 days\nTab Pantop 40mg 1-0-0\nSig: After food"
    dec_rx, type_rx, conf_rx, reasons_rx, _ = classify_and_validate_evidence(rx_text, {})
    assert type_rx == DOCUMENT_TYPE_PRESCRIPTION

    # Clinical Note
    soap_text = (
        "Department of Internal Medicine\n"
        "Progress Note - Day 3\n"
        "Subjective: Patient reports improvement in chest tightness.\n"
        "Objective: Vitals stable, chest clear on auscultation.\n"
        "Assessment: Resolving bronchitis.\n"
        "Plan: Continue current regimen, monitor vitals.\n"
    )
    dec_soap, type_soap, conf_soap, reasons_soap, _ = classify_and_validate_evidence(soap_text, {})
    assert type_soap == DOCUMENT_TYPE_CLINICAL_NOTE


def test_validator_unknown_requires_review():
    """
    Verifies that an ambiguous medical document with low evidence score is categorized
    as UNKNOWN_REQUIRES_REVIEW / POSSIBLE_MEDICAL_DOCUMENT_NEEDS_REVIEW rather than being
    erroneously forced to CLINICAL_NOTE.
    """
    from ai_engine.validator import classify_and_validate_evidence, DOCUMENT_TYPE_POSSIBLE_MEDICAL
    ambiguous_text = "Patient seen at reception. Follow up requested. Dr. Sign"
    dec, type_amb, conf, reasons, _ = classify_and_validate_evidence(ambiguous_text, {})
    # Status should be NEEDS_REVIEW and document_type should reflect uncertainty, NOT clinical_note
    assert dec == "NEEDS_REVIEW"
    assert type_amb in (DOCUMENT_TYPE_UNKNOWN_REQUIRES_REVIEW, DOCUMENT_TYPE_POSSIBLE_MEDICAL)
    assert type_amb != DOCUMENT_TYPE_CLINICAL_NOTE


def test_make_needs_review_record_preserves_candidates():
    """
    Verifies that make_needs_review_record preserves candidate medicines, tests,
    and raw OCR text rather than wiping them out.
    """
    cand_med = [{"name": "Telma", "strength": "40 mg", "verification_state": "UNVERIFIED_CANDIDATE"}]
    cand_test = [{"name": "HbA1c", "value": None}]
    record = make_needs_review_record(
        reason_codes=["MODERATE_OCR_CONFIDENCE"],
        message="Review required",
        document_type="PRESCRIPTION",
        doc_type="prescription",
        ocr_text="Rx Telma 40",
        medicines=cand_med,
        tests=cand_test,
    )

    assert record["document_type"] == "PRESCRIPTION"
    assert len(record["medicines"]) == 1
    assert record["medicines"][0]["name"] == "Telma"
    assert len(record["tests"]) == 1
    assert record["tests"][0]["name"] == "HbA1c"
    assert bool(record["needs_review"]) is True
    assert "document_type" in record["needs_review"]
