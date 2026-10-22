"""
services/validators.py — Post-AI validation: flag re-check, confidence thresholds, schema checks.
Records AI-provided data as-is; backend derives flag_verified separately.
"""
from __future__ import annotations

from typing import Any, Optional
import math
from datetime import date


CONFIDENCE_THRESHOLD = 0.7  # matches the AI engine


def _needs_review_from_tests(tests: list[dict]) -> bool:
    for t in tests:
        conf = t.get("confidence")
        if conf is not None and conf < CONFIDENCE_THRESHOLD:
            return True
    return False


def _needs_review_from_medicines(meds: list[dict]) -> bool:
    for m in meds:
        conf = m.get("confidence")
        if conf is not None and conf < CONFIDENCE_THRESHOLD:
            return True
    return False


def validate_record_json(data: Any) -> tuple[bool, Optional[str]]:
    """
    Validate that record_json is a dict with expected keys.
    Returns (is_valid, error_message_or_None).
    Tolerant: extra/unknown keys are OK.
    """
    if not isinstance(data, dict):
        return False, "record_json must be a JSON object"
    if "doc_type" not in data and "type" not in data:
        return False, "record_json missing 'doc_type'"
    if data.get("error"):
        return False, "Resolve the extraction error before confirming the record"
    for field in ("tests", "medicines", "diagnoses"):
        if not isinstance(data.get(field, []), list) or any(not isinstance(item, dict) for item in data.get(field, [])):
            return False, f"{field} must be a list of objects"
    if not isinstance(data.get("doc_type", data.get("type")), str):
        return False, "doc_type must be a string"
    for key in ("doc_date", "collection_date", "follow_up_date"):
        value = data.get(key)
        if value is not None:
            try:
                date.fromisoformat(value)
            except (TypeError, ValueError):
                return False, f"{key} must be a valid ISO date"
    for field in ("tests", "medicines"):
        for item in data.get(field, []):
            for key in ("name", "name_raw", "unit", "generic", "schedule_raw", "strength"):
                if item.get(key) is not None and not isinstance(item[key], str):
                    return False, f"{field}.{key} must be a string"
            for key in ("value", "ref_low", "ref_high", "confidence", "duration_days"):
                if item.get(key) is not None:
                    try:
                        number = float(item[key])
                        if not math.isfinite(number) or isinstance(item[key], bool):
                            raise ValueError()
                        if key == "confidence" and not 0 <= number <= 1:
                            raise ValueError()
                        if key == "duration_days" and (number < 0 or not number.is_integer()):
                            raise ValueError()
                    except (TypeError, ValueError):
                        return False, f"{field}.{key} has an invalid numeric value"
    return True, None


def compute_needs_review(record_json: dict) -> bool:
    """Return True if any extracted item has low confidence."""
    tests = record_json.get("tests", [])
    meds = record_json.get("medicines", [])
    if not isinstance(tests, list):
        tests = []
    if not isinstance(meds, list):
        meds = []
    unknown_results = any(t.get("flag") == "UNKNOWN" for t in tests)
    return bool(record_json.get("needs_review") or record_json.get("error")) or unknown_results or _needs_review_from_tests(tests) or _needs_review_from_medicines(meds)


def generate_headline(record_json: dict, doc_type: str) -> str:
    """
    Generate a safe, neutral headline string for timeline display.
    Never says 'dangerous' or implies diagnosis.
    """
    tests = record_json.get("tests", []) if isinstance(record_json.get("tests"), list) else []
    meds = record_json.get("medicines", []) if isinstance(record_json.get("medicines"), list) else []
    diagnoses = record_json.get("diagnoses", []) if isinstance(record_json.get("diagnoses"), list) else []

    abnormal = [t for t in tests if t.get("flag") in ("H", "L", "HIGH", "LOW")]
    n_tests = len(tests)
    n_meds = len(meds)
    n_diagnoses = len(diagnoses)

    doc_label = {
        "lab_report": "Lab report",
        "prescription": "Prescription",
        "discharge_summary": "Discharge summary",
        "diagnostic_report": "Diagnostic report",
        "radiology": "Radiology report",
        "clinical_note": "Clinical note",
        "possible_medical_document_needs_review": "Possible medical document",
        "other": "Health record",
    }.get((doc_type or "").lower(), "Health record")

    parts = []

    if n_tests:
        if abnormal:
            parts.append(f"{len(abnormal)} value(s) need attention")
        else:
            parts.append(f"{n_tests} test result(s)")

    if n_meds:
        parts.append(f"{n_meds} medication(s)")

    if n_diagnoses:
        parts.append(f"{n_diagnoses} diagnosis entry(s)")

    if parts:
        return f"{doc_label}: {', '.join(parts)}"

    if (doc_type or "").lower() in ("clinical_note", "possible_medical_document_needs_review") or record_json.get("status") == "NEEDS_REVIEW":
        return f"{doc_label} (verification needed)"
    return doc_label
