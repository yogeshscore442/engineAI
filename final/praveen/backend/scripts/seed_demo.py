"""
scripts/seed_demo.py — Seed the database with 3–4 synthetic records for demo.
Includes: HbA1c trend (improving), duplicate-brand demo, discharge summary.
Usage: python scripts/seed_demo.py
"""
from __future__ import annotations

import json
import sys
import os
from pathlib import Path

# Add backend root to path
sys.path.insert(0, str(Path(__file__).parent.parent))
os.chdir(Path(__file__).parent.parent)

from app.db import init_db, db_session
from app.repositories.profiles_repo import get_all_profiles, create_profile, get_profile
from app.repositories.records_repo import create_record
from app.services.normalizer import normalize_record_json
from app.services.validators import generate_headline, compute_needs_review
from app.repositories import medicines_repo, tests_repo, records_repo

DEMO_PROFILE_ID = "demo-patient-001"

DEMO_RECORDS = [
    # Record 1: Discharge summary with high HbA1c (2024-01)
    {
        "doc_type": "discharge_summary",
        "doc_date": "2024-01-10",
        "source": "mock",
        "language": "en",
        "summary": "Admitted for uncontrolled diabetes (HbA1c 9.2%). Discharged stable.",
        "tests": [
            {"name": "HbA1c", "value": 9.2, "unit": "%", "ref_low": 4.0, "ref_high": 5.7, "flag": "H", "date": "2024-01-10", "confidence": 0.94},
            {"name": "Fasting Blood Glucose", "value": 218.0, "unit": "mg/dL", "ref_low": 70.0, "ref_high": 100.0, "flag": "H", "date": "2024-01-10", "confidence": 0.92},
        ],
        "medicines": [
            {"name_raw": "Insulin Glargine", "generic": "insulin glargine", "strength": "10 units", "schedule_raw": "Bedtime SC", "duration_days": 30, "confidence": 0.96},
            {"name_raw": "Metformin", "generic": "metformin", "strength": "500mg", "schedule_raw": "BD", "duration_days": 90, "confidence": 0.95},
        ],
        "diagnoses": [{"name": "Uncontrolled Type 2 Diabetes Mellitus", "icd10": "E11.9"}],
    },
    # Record 2: Lab report with improving HbA1c (2024-03)
    {
        "doc_type": "lab_report",
        "doc_date": "2024-03-15",
        "source": "mock",
        "language": "en",
        "summary": "Repeat labs. HbA1c improving with treatment. Cholesterol borderline.",
        "tests": [
            {"name": "HbA1c", "value": 7.8, "unit": "%", "ref_low": 4.0, "ref_high": 5.7, "flag": "H", "date": "2024-03-15", "confidence": 0.96},
            {"name": "Total Cholesterol", "value": 198.0, "unit": "mg/dL", "ref_low": 0.0, "ref_high": 200.0, "flag": "N", "date": "2024-03-15", "confidence": 0.90},
            {"name": "Haemoglobin", "value": 11.5, "unit": "g/dL", "ref_low": 12.0, "ref_high": 17.5, "flag": "L", "date": "2024-03-15", "confidence": 0.92},
        ],
        "medicines": [],
        "diagnoses": [],
    },
    # Record 3: Prescription with duplicate generic (metformin under 2 brand names)
    {
        "doc_type": "prescription",
        "doc_date": "2024-05-01",
        "source": "mock",
        "language": "en",
        "summary": "Prescription with dual metformin brands (demonstrates duplicate-brand alert).",
        "tests": [],
        "medicines": [
            {"name_raw": "Glucophage", "generic": "metformin", "strength": "500mg", "schedule_raw": "Twice daily", "duration_days": 30, "confidence": 0.90},
            {"name_raw": "Obimet SR", "generic": "metformin", "strength": "1000mg", "schedule_raw": "Once nightly", "duration_days": 30, "confidence": 0.88},
            {"name_raw": "Atorvastatin", "generic": "atorvastatin", "strength": "10mg", "schedule_raw": "Once at bedtime", "duration_days": 90, "confidence": 0.95},
        ],
        "diagnoses": [{"name": "Type 2 Diabetes Mellitus", "icd10": "E11"}, {"name": "Dyslipidaemia", "icd10": "E78.5"}],
    },
    # Record 4: Latest lab — HbA1c further improved (2024-06)
    {
        "doc_type": "lab_report",
        "doc_date": "2024-06-15",
        "source": "mock",
        "language": "en",
        "summary": "Latest labs — HbA1c significantly improved. All other values normal.",
        "tests": [
            {"name": "HbA1c", "value": 6.8, "unit": "%", "ref_low": 4.0, "ref_high": 5.7, "flag": "H", "date": "2024-06-15", "confidence": 0.97},
            {"name": "Fasting Blood Glucose", "value": 95.0, "unit": "mg/dL", "ref_low": 70.0, "ref_high": 100.0, "flag": "N", "date": "2024-06-15", "confidence": 0.95},
            {"name": "Serum Creatinine", "value": 0.9, "unit": "mg/dL", "ref_low": 0.6, "ref_high": 1.2, "flag": "N", "date": "2024-06-15", "confidence": 0.93},
        ],
        "medicines": [],
        "diagnoses": [],
    },
]


def seed():
    init_db()
    with db_session() as db:
        profile = get_profile(db, DEMO_PROFILE_ID)
        if not profile:
            profile = create_profile(db, profile_id=DEMO_PROFILE_ID, name="Demo Patient", relation="self")
            print(f"Created demo profile: {DEMO_PROFILE_ID}")
        else:
            print(f"Demo profile already exists: {DEMO_PROFILE_ID}")

        for i, rec_data in enumerate(DEMO_RECORDS):
            normalized = normalize_record_json(rec_data)
            doc_type = normalized["doc_type"]
            headline = generate_headline(normalized, doc_type)
            needs_review = compute_needs_review(normalized)

            record = create_record(
                db,
                profile_id=DEMO_PROFILE_ID,
                doc_type=doc_type,
                doc_date=normalized.get("doc_date"),
                status="confirmed",
                file_path=None,
                file_sha256=f"demo_sha256_{i:04d}",
                record_json=json.dumps(normalized),
                schema_version=1,
                source="mock",
                language="en",
                needs_review=needs_review,
                headline=headline,
            )

            # Insert projections
            meds_data = normalized.get("medicines", [])
            tests_data = normalized.get("tests", [])
            medicines_repo.bulk_insert_medicines(db, record.record_id, DEMO_PROFILE_ID, meds_data)
            tests_repo.bulk_insert_tests(db, record.record_id, DEMO_PROFILE_ID, tests_data)
            db.flush()

            print(f"  Seeded record {i+1}: {doc_type} ({normalized.get('doc_date')}) — {headline}")

    print(f"\nDemo seed complete! Profile ID: {DEMO_PROFILE_ID}")
    print(f"Test with: GET /api/profiles/{DEMO_PROFILE_ID}/timeline")

    # Seed patient-002 if empty
    with db_session() as db:
        p2 = get_profile(db, "patient-002")
        if not p2:
            create_profile(db, profile_id="patient-002", name="Priya Sharma", relation="family")
        p2_records = records_repo.get_records_by_profile(db, "patient-002")
        if len(p2_records) == 0:
            for i, rec_data in enumerate(DEMO_RECORDS[:2]):
                normalized = normalize_record_json(rec_data)
                doc_type = normalized["doc_type"]
                headline = generate_headline(normalized, doc_type)
                needs_review = compute_needs_review(normalized)
                record = create_record(
                    db,
                    profile_id="patient-002",
                    doc_type=doc_type,
                    doc_date=normalized.get("doc_date"),
                    status="confirmed",
                    file_path=None,
                    file_sha256=f"p2_sha256_{i:04d}",
                    record_json=json.dumps(normalized),
                    schema_version=1,
                    source="mock",
                    language="en",
                    needs_review=needs_review,
                    headline=headline,
                )
                meds_data = normalized.get("medicines", [])
                tests_data = normalized.get("tests", [])
                medicines_repo.bulk_insert_medicines(db, record.record_id, "patient-002", meds_data)
                tests_repo.bulk_insert_tests(db, record.record_id, "patient-002", tests_data)
            db.flush()
            print("  Seeded 2 records for patient-002 (Priya Sharma)")


if __name__ == "__main__":
    seed()
