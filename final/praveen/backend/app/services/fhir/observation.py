"""FHIR Observation resource mapper — one per test result."""
from __future__ import annotations

import uuid
from typing import Any

from app.models import Record

FLAG_INTERPRETATION_MAP = {
    "H": ("H", "High", "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation"),
    "L": ("L", "Low", "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation"),
    "N": ("N", "Normal", "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation"),
}


def build_observations(record: Record, record_data: dict[str, Any], patient_id: str) -> list[dict]:
    tests = record_data.get("tests", [])
    if not isinstance(tests, list):
        return []

    observations = []
    for t in tests:
        obs = _build_single_observation(t, record, patient_id)
        observations.append(obs)
    return observations


def _build_single_observation(test: dict, record: Record, patient_id: str) -> dict:
    obs_id = str(uuid.uuid4())
    coding = []

    # LOINC coding if present
    loinc = test.get("loinc")
    if loinc:
        coding.append({
            "system": "http://loinc.org",
            "code": loinc,
            "display": test.get("name_canonical") or test.get("name", ""),
        })
    coding.append({
        "system": "https://health-copilot/test-name",
        "code": (test.get("name") or "").lower().replace(" ", "-"),
        "display": test.get("name", ""),
    })

    obs: dict[str, Any] = {
        "resourceType": "Observation",
        "id": obs_id,
        "status": "final" if record.status == "confirmed" else "preliminary",
        "category": [
            {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                        "code": "laboratory",
                        "display": "Laboratory",
                    }
                ]
            }
        ],
        "code": {"coding": coding, "text": test.get("name", "")},
        "subject": {"reference": f"Patient/{patient_id}"},
        "effectiveDateTime": test.get("date") or record.doc_date,
        "derivedFrom": [{"reference": f"DiagnosticReport/report-{record.record_id}"}],
    }

    # valueQuantity
    value = test.get("value")
    if value is not None:
        obs["valueQuantity"] = {
            "value": float(value),
            "unit": test.get("unit", ""),
            "system": "http://unitsofmeasure.org",
            "code": test.get("unit", ""),
        }

    # referenceRange
    ref_low = test.get("ref_low")
    ref_high = test.get("ref_high")
    if ref_low is not None or ref_high is not None:
        ref_range: dict[str, Any] = {}
        if ref_low is not None:
            ref_range["low"] = {"value": float(ref_low), "unit": test.get("unit", "")}
        if ref_high is not None:
            ref_range["high"] = {"value": float(ref_high), "unit": test.get("unit", "")}
        obs["referenceRange"] = [ref_range]

    # interpretation
    flag = test.get("flag")
    flag = {"HIGH": "H", "LOW": "L", "NORMAL": "N"}.get(flag, flag)
    if flag and flag in FLAG_INTERPRETATION_MAP:
        interp = FLAG_INTERPRETATION_MAP[flag]
        obs["interpretation"] = [
            {
                "coding": [
                    {"system": interp[2], "code": interp[0], "display": interp[1]}
                ]
            }
        ]

    return obs
