"""
test_healthcare_modules.py — Automated tests for the Five Healthcare Modules:
1. CareBridge AI
2. MedExplain Verify
3. AdhereSense
4. AccessLens Health
5. MedList Safety
"""
import pytest
from datetime import date
from fastapi.testclient import TestClient

from app.main import app
from app.db import get_db, Base
from app.models import Profile, Record
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

TEST_DATABASE_URL = "sqlite:///:memory:"

@pytest.fixture
def test_db():
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        # Seed test patient and medical documents
        prof = Profile(id="test-patient-001", name="Ramesh Kumar")
        db.add(prof)

        # 1. Discharge Summary (CareBridge AI source)
        rec_discharge = Record(
            id="rec-dis-001",
            profile_id="test-patient-001",
            doc_type="discharge_summary",
            doc_date=date(2026, 3, 15),
            file_path="uploads/discharge1.pdf",
            file_hash="hash-dis-001",
            status="confirmed",
            record_json={
                "treating_doctor": "Dr. K. Swaminathan, MD",
                "hospital_name": "Apollo Speciality Hospital",
                "discharge_advice": "Follow diabetic diet. Review after 10 days. Report immediately if chest pain or shortness of breath occurs.",
                "follow_up_date": "2026-03-25",
                "medicines": [
                    {"name_raw": "Metformin 500mg", "generic": "Metformin", "strength": "500mg", "schedule_raw": "1-0-1 after food"}
                ]
            }
        )
        db.add(rec_discharge)

        # 2. Outpatient Prescription (MedList Safety & CareBridge source)
        rec_rx = Record(
            id="rec-rx-001",
            profile_id="test-patient-001",
            doc_type="prescription",
            doc_date=date(2026, 3, 20),
            file_path="uploads/prescription1.jpg",
            file_hash="hash-rx-001",
            status="confirmed",
            record_json={
                "summary_en": "Patient prescribed Glycomet and Calpol. Review in 5 days if fever persists.",
                "medicines": [
                    {"name_raw": "Glycomet 500mg", "generic": "Metformin", "strength": "500mg", "schedule_raw": "1-0-1 after food"},
                    {"name_raw": "Calpol 500mg", "generic": "Paracetamol", "strength": "500mg", "schedule_raw": "1-0-0 SOS"}
                ]
            }
        )
        db.add(rec_rx)

        # 3. Lab Report (MedExplain Verify source)
        rec_lab = Record(
            id="rec-lab-001",
            profile_id="test-patient-001",
            doc_type="lab_report",
            doc_date=date(2026, 3, 22),
            file_path="uploads/lab1.jpg",
            file_hash="hash-lab-001",
            status="confirmed",
            record_json={
                "tests": [
                    {
                        "name": "HbA1c",
                        "value": 8.4,
                        "unit": "%",
                        "ref_range": "4.0 - 5.6",
                        "flag": "HIGH"
                    },
                    {
                        "name": "Fasting Blood Sugar",
                        "value": 142.0,
                        "unit": "mg/dL",
                        "ref_range": "70 - 100",
                        "flag": "HIGH"
                    }
                ]
            }
        )
        db.add(rec_lab)
        db.commit()

        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(test_db):
    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ── 1. CareBridge AI Tests ───────────────────────────────────────────────────
def test_carebridge_ai_discharge_and_followup_analysis(client):
    res = client.get("/api/profiles/test-patient-001/carebridge")
    assert res.status_code == 200
    data = res.json()

    assert data["total_discharge_summaries"] == 1
    assert len(data["follow_up_instructions"]) >= 1
    assert "2026-03-25" in data["follow_up_instructions"][0]["appointment_date"]
    assert any("Chest Pain" in rf or "Shortness Of Breath" in rf for rf in data["documented_red_flags"])
    assert data["care_plan_completeness_percent"] >= 70
    assert "CareBridge AI" in data["disclaimer"]


# ── 2. MedExplain Verify Tests ────────────────────────────────────────────────
def test_medexplain_verify_lab_biomarker_grounding(client):
    res = client.post("/api/profiles/test-patient-001/medexplain", json={"test_name": "HbA1c"})
    assert res.status_code == 200
    data = res.json()

    assert data["test_or_topic"] == "HbA1c"
    assert data["observed_value"] == "8.4"
    assert data["unit"] == "%"
    assert data["clinical_flag"] == "HIGH"
    assert "elevated" in data["grounded_explanation"].lower() or "high" in data["grounded_explanation"].lower()
    assert len(data["official_medical_references"]) >= 1
    assert any("medlineplus.gov" in ref["url"] or "loinc.org" in ref["url"] for ref in data["official_medical_references"])


# ── 3. AdhereSense Tests ──────────────────────────────────────────────────────
def test_adheresense_cost_barrier_support(client):
    res = client.post("/api/profiles/test-patient-001/adheresense", json={
        "medicine_name": "Glycomet 500mg",
        "barrier_category": "COST",
        "patient_description": "The medication is very expensive at the private chemist."
    })
    assert res.status_code == 200
    data = res.json()

    assert data["barrier_category"] == "COST"
    assert data["prohibits_auto_substitution"] is True
    assert "janaushadhi.gov.in" in data["jan_aushadhi_generic_inquiry_url"]
    assert len(data["questions_for_doctor_or_pharmacist"]) >= 1
    assert "generic" in data["educational_guidance"].lower()


def test_adheresense_side_effects_caution(client):
    res = client.post("/api/profiles/test-patient-001/adheresense", json={
        "medicine_name": "Metformin",
        "barrier_category": "SIDE_EFFECTS",
        "patient_description": "Experiencing mild stomach upset and nausea."
    })
    assert res.status_code == 200
    data = res.json()

    assert data["barrier_category"] == "SIDE_EFFECTS"
    assert "do not stop" in data["educational_guidance"].lower()
    assert data["prohibits_auto_substitution"] is True


# ── 4. AccessLens Health Tests ────────────────────────────────────────────────
def test_access_lens_verified_services_directory(client):
    res = client.get("/api/access_lens/services")
    assert res.status_code == 200
    data = res.json()

    assert len(data["emergency_helplines"]) >= 2
    helpline_numbers = [h["contact"] for h in data["emergency_helplines"]]
    assert any("112" in n for n in helpline_numbers)
    assert any("108" in n for n in helpline_numbers)

    schemes = [s["name"] for s in data["government_health_schemes"]]
    assert any("Ayushman Bharat" in s or "PM-JAY" in s for s in schemes)
    assert any("Janaushadhi" in s or "PMBJP" in s for s in schemes)


# ── 5. MedList Safety Tests ───────────────────────────────────────────────────
def test_medlist_safety_reconciliation_and_duplicate_generics(client):
    res = client.get("/api/profiles/test-patient-001/medlist_safety")
    assert res.status_code == 200
    data = res.json()

    assert data["total_active_medications"] >= 2
    # Detects duplicate Metformin between discharge summary ("Metformin 500mg") and prescription ("Glycomet 500mg")
    assert any("Metformin" in alert for alert in data["duplicate_generic_alerts"])
    assert data["requires_pharmacist_review"] is True
