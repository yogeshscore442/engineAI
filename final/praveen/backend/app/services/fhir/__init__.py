"""
services/fhir/__init__.py — FHIR R4 Bundle builder registry.
New mapper: add a file and register in MAPPERS. No other changes needed.
Disclaimer: "FHIR R4-style, ABDM-ready structure. Not ABDM certified."
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from app.models import Profile, Record


def build_fhir_bundle(profile: Profile, record: Record) -> dict[str, Any]:
    """
    Build a FHIR R4 Bundle (type=collection) for a single record.
    Includes: Patient, DiagnosticReport, Observation (per test), MedicationRequest (per med), Condition (per diagnosis).
    """
    from app.services.fhir.patient import build_patient
    from app.services.fhir.diagnostic_report import build_diagnostic_report
    from app.services.fhir.observation import build_observations
    from app.services.fhir.medication_request import build_medication_requests
    from app.services.fhir.condition import build_conditions

    try:
        record_data = json.loads(record.record_json) if isinstance(record.record_json, str) else record.record_json
    except (json.JSONDecodeError, TypeError):
        record_data = {}

    patient = build_patient(profile)
    diagnostic_report = build_diagnostic_report(record, patient["id"])
    observations = build_observations(record, record_data, patient["id"])
    medication_requests = build_medication_requests(record, record_data, patient["id"])
    conditions = build_conditions(record, record_data, patient["id"])

    entries = [{"resource": patient}, {"resource": diagnostic_report}]
    for obs in observations:
        entries.append({"resource": obs})
    for med in medication_requests:
        entries.append({"resource": med})
    for cond in conditions:
        entries.append({"resource": cond})

    bundle = {
        "resourceType": "Bundle",
        "id": str(uuid.uuid4()),
        "type": "collection",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "meta": {
            "profile": ["http://hl7.org/fhir/StructureDefinition/Bundle"],
            "tag": [{"system": "https://healthid.abdm.gov.in", "code": "abdm-ready", "display": "ABDM-ready structure"}],
        },
        "entry": entries,
        "disclaimer": "FHIR R4-style, ABDM-ready structure. Not ABDM certified.",
    }
    return bundle
