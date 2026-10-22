"""FHIR Condition resource mapper — one per diagnosis."""
from __future__ import annotations

import uuid
from typing import Any

from app.models import Record


def build_conditions(record: Record, record_data: dict[str, Any], patient_id: str) -> list[dict]:
    diagnoses = record_data.get("diagnoses", [])
    if not isinstance(diagnoses, list):
        return []
    return [_build_single_condition(d, record, patient_id) for d in diagnoses]


def _build_single_condition(diag: dict, record: Record, patient_id: str) -> dict:
    cond_id = str(uuid.uuid4())

    if isinstance(diag, str):
        display = diag
        icd_code = None
    else:
        display = diag.get("name") or diag.get("description") or str(diag)
        icd_code = diag.get("icd10") or diag.get("icd_code")

    coding = []
    if icd_code:
        coding.append({
            "system": "http://hl7.org/fhir/sid/icd-10",
            "code": icd_code,
            "display": display,
        })
    else:
        coding.append({
            "system": "https://health-copilot/diagnosis",
            "display": display,
        })

    return {
        "resourceType": "Condition",
        "id": cond_id,
        "clinicalStatus": {
            "coding": [
                {
                    "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                    "code": "active",
                }
            ]
        },
        "verificationStatus": {
            "coding": [
                {
                    "system": "http://terminology.hl7.org/CodeSystem/condition-ver-status",
                    "code": "unconfirmed",
                }
            ]
        },
        "code": {"coding": coding, "text": display},
        "subject": {"reference": f"Patient/{patient_id}"},
        "recordedDate": record.doc_date or (record.created_at.strftime("%Y-%m-%d") if record.created_at else None),
        "extension": [
            {"url": "https://health-copilot/source-record", "valueString": record.record_id},
            {"url": "https://health-copilot/disclaimer", "valueString": "Informational only, not medical advice."},
        ],
    }
