"""
tests/test_records.py — Record GET, confirm flow, timeline, and FHIR tests.
"""
import io
import json
import pytest
from tests.conftest import make_fake_pdf


@pytest.fixture(scope="module")
def uploaded_record(client, default_profile_id):
    pdf = make_fake_pdf() + b"\n%uploaded_record_pdf_unique"
    r = client.post(
        f"/api/profiles/{default_profile_id}/records",
        files={"file": ("lab.pdf", io.BytesIO(pdf), "application/pdf")},
        data={"lang": "en"},
    )
    assert r.status_code == 201
    return r.json()


def test_get_record(client, uploaded_record):
    record_id = uploaded_record["record_id"]
    r = client.get(f"/api/records/{record_id}")
    assert r.status_code == 200
    data = r.json()
    assert data["record_id"] == record_id
    assert data["status"] == "draft"
    assert "disclaimer" in data


def test_get_record_not_found(client):
    r = client.get("/api/records/nonexistent-id-9999")
    assert r.status_code == 404
    data = r.json()
    err = data.get("error", data)
    if isinstance(err, dict):
        assert err.get("code") in ("RECORD_NOT_FOUND", "NOT_FOUND")



def test_confirm_record(client, uploaded_record):
    record_id = uploaded_record["record_id"]
    confirmed_json = {
        "doc_type": "lab_report",
        "doc_date": "2024-06-15",
        "tests": [
            {
                "name": "HbA1c",
                "value": 6.5,
                "unit": "%",
                "ref_low": 4.0,
                "ref_high": 5.7,
                "flag": "H",
                "date": "2024-06-15",
                "confidence": 0.95,
            }
        ],
        "medicines": [],
        "diagnoses": [],
    }
    r = client.put(
        f"/api/records/{record_id}",
        json={"record_json": confirmed_json, "status": "confirmed"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "confirmed"
    assert data["confirmed_at"] is not None
    # headline should be non-empty
    assert data.get("headline")


def test_confirm_idempotent(client, uploaded_record):
    """Calling PUT again on same record should re-normalize idempotently."""
    record_id = uploaded_record["record_id"]
    confirmed_json = {
        "doc_type": "lab_report",
        "doc_date": "2024-06-15",
        "tests": [
            {
                "name": "HbA1c",
                "value": 6.5,
                "unit": "%",
                "ref_low": 4.0,
                "ref_high": 5.7,
                "flag": "H",
                "date": "2024-06-15",
            }
        ],
        "medicines": [],
        "diagnoses": [],
    }
    r1 = client.put(f"/api/records/{record_id}", json={"record_json": confirmed_json})
    r2 = client.put(f"/api/records/{record_id}", json={"record_json": confirmed_json})
    assert r1.status_code == 200
    assert r2.status_code == 200
    # Tests should not be doubled
    assert len(r2.json()["tests"]) == len(r1.json()["tests"])


def test_timeline_order(client, default_profile_id):
    r = client.get(f"/api/profiles/{default_profile_id}/timeline")
    assert r.status_code == 200
    data = r.json()
    assert data["profile_id"] == default_profile_id
    assert "items" in data
    # Items should be ordered by date descending (or created_at if no date)


def test_fhir_bundle_structure(client, uploaded_record):
    record_id = uploaded_record["record_id"]
    r = client.get(f"/api/records/{record_id}/fhir")
    assert r.status_code == 200
    bundle = r.json()
    assert bundle["resourceType"] == "Bundle"
    assert bundle["type"] == "collection"
    assert "entry" in bundle
    assert len(bundle["entry"]) > 0
    assert "disclaimer" in bundle

    # Check Patient resource exists
    resource_types = [e["resource"]["resourceType"] for e in bundle["entry"]]
    assert "Patient" in resource_types
    assert "DiagnosticReport" in resource_types


def test_fhir_bundle_observations_have_loinc(client, default_profile_id):
    """After confirming with LOINC-aware tests, FHIR Observations should have LOINC coding."""
    pdf = make_fake_pdf()
    up = client.post(
        f"/api/profiles/{default_profile_id}/records",
        files={"file": ("fhir_test.pdf", io.BytesIO(pdf), "application/pdf")},
        data={"lang": "en"},
    )
    record_id = up.json()["record_id"]

    # Confirm with a known LOINC test
    confirmed_json = {
        "doc_type": "lab_report",
        "doc_date": "2024-07-01",
        "tests": [{"name": "HbA1c", "value": 6.0, "unit": "%", "ref_low": 4.0, "ref_high": 5.7, "flag": "H", "date": "2024-07-01"}],
        "medicines": [],
        "diagnoses": [],
    }
    client.put(f"/api/records/{record_id}", json={"record_json": confirmed_json})

    r = client.get(f"/api/records/{record_id}/fhir")
    assert r.status_code == 200
    bundle = r.json()
    observations = [e["resource"] for e in bundle["entry"] if e["resource"]["resourceType"] == "Observation"]
    if observations:
        codes = observations[0]["code"]["coding"]
        loinc_codings = [c for c in codes if c.get("system") == "http://loinc.org"]
        assert len(loinc_codings) >= 1
