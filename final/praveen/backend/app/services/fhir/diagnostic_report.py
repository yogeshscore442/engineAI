"""FHIR DiagnosticReport resource mapper."""
from __future__ import annotations

from app.models import Record

DOC_TYPE_CODE_MAP = {
    "lab_report": ("11502-2", "Laboratory report", "http://loinc.org"),
    "prescription": ("57833-6", "Prescription for medication", "http://loinc.org"),
    "discharge_summary": ("18842-5", "Discharge summary", "http://loinc.org"),
    "diagnostic_report": ("47045-0", "Diagnostic imaging report", "http://loinc.org"),
    "radiology": ("68604-8", "Radiology diagnostic report", "http://loinc.org"),
}


def build_diagnostic_report(record: Record, patient_id: str) -> dict:
    code_entry = DOC_TYPE_CODE_MAP.get(record.doc_type, ("74213-0", "Health record", "http://loinc.org"))
    fhir_status = "final" if record.status == "confirmed" else "preliminary"

    report = {
        "resourceType": "DiagnosticReport",
        "id": f"report-{record.record_id}",
        "status": fhir_status,
        "category": [
            {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/v2-0074",
                        "code": "LAB",
                        "display": "Laboratory",
                    }
                ]
            }
        ],
        "code": {
            "coding": [
                {
                    "system": code_entry[2],
                    "code": code_entry[0],
                    "display": code_entry[1],
                }
            ],
            "text": record.doc_type,
        },
        "subject": {"reference": f"Patient/{patient_id}"},
        "effectiveDateTime": record.doc_date or (record.created_at.strftime("%Y-%m-%d") if record.created_at else None),
        "issued": record.created_at.isoformat() if record.created_at else None,
        "extension": [
            {
                "url": "https://health-copilot/source",
                "valueString": record.source,
            }
        ],
    }
    return report
