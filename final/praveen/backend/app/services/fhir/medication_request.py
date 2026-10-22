"""FHIR MedicationRequest resource mapper — one per medicine."""
from __future__ import annotations

import uuid
from typing import Any

from app.models import Record


def build_medication_requests(record: Record, record_data: dict[str, Any], patient_id: str) -> list[dict]:
    medicines = record_data.get("medicines", [])
    if not isinstance(medicines, list):
        return []
    return [_build_single_medication_request(m, record, patient_id) for m in medicines]


def _build_single_medication_request(med: dict, record: Record, patient_id: str) -> dict:
    med_id = str(uuid.uuid4())
    name_raw = med.get("name_raw") or med.get("name", "Unknown")
    generic = med.get("generic")

    coding = [{"system": "https://health-copilot/medication", "display": name_raw}]
    if generic:
        coding.append({
            "system": "https://health-copilot/generic",
            "display": generic,
        })

    dosage_text = med.get("schedule_raw") or med.get("schedule") or "As prescribed"
    strength = med.get("strength")
    if strength:
        dosage_text = f"{strength} — {dosage_text}"

    duration_days = med.get("duration_days")
    bounds_duration = None
    if duration_days:
        bounds_duration = {
            "boundsDuration": {
                "value": int(duration_days),
                "unit": "d",
                "system": "http://unitsofmeasure.org",
                "code": "d",
            }
        }

    return {
        "resourceType": "MedicationRequest",
        "id": med_id,
        "status": "active",
        "intent": "order",
        "medicationCodeableConcept": {
            "coding": coding,
            "text": name_raw,
        },
        "subject": {"reference": f"Patient/{patient_id}"},
        "authoredOn": record.doc_date or (record.created_at.strftime("%Y-%m-%d") if record.created_at else None),
        "dosageInstruction": [
            {
                "text": dosage_text,
                **(bounds_duration or {}),
            }
        ],
        "extension": [
            {"url": "https://health-copilot/source-record", "valueString": record.record_id}
        ],
    }
