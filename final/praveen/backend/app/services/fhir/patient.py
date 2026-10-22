"""FHIR Patient resource mapper."""
from __future__ import annotations

import uuid
from app.models import Profile


def build_patient(profile: Profile) -> dict:
    identifiers = [
        {
            "use": "usual",
            "system": "urn:health-copilot:profile",
            "value": profile.profile_id,
        }
    ]
    if profile.abha_id:
        identifiers.append({
            "use": "official",
            "system": "https://healthid.abdm.gov.in",
            "value": profile.abha_id,
            "_mock": True,
            "extension": [{"url": "https://healthid.abdm.gov.in/mock", "valueBoolean": True}],
        })

    return {
        "resourceType": "Patient",
        "id": f"patient-{profile.profile_id}",
        "meta": {
            "profile": ["https://nrces.in/ndhm/fhir/r4/StructureDefinition/Patient"]
        },
        "identifier": identifiers,
        "name": [{"text": "[redacted for privacy]"}],  # privacy: name not included in FHIR export
        "extension": [
            {
                "url": "https://health-copilot/relation",
                "valueString": profile.relation,
            }
        ],
    }
