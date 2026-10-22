import pytest
from ai_engine.flags import compute_flag


@pytest.mark.parametrize('value', [float('nan'), float('inf'), float('-inf')])
def test_nonfinite_values_are_not_normal(value):
    assert compute_flag('Glucose', value, 'mg/dL', 70, 100) == 'UNKNOWN'


def test_incompatible_unit_is_not_compared_to_reference():
    assert compute_flag('HbA1c', 6, 'unrecognized-unit', None, None) == 'UNKNOWN'


def test_missing_unit_does_not_assume_table_unit():
    assert compute_flag('HbA1c', 6, None, None, None) == 'UNKNOWN'


def test_reversed_reference_range_is_unknown():
    assert compute_flag('synthetic', 5, 'u', 10, 1) == 'UNKNOWN'


@pytest.mark.parametrize('value,expected', [(1, 'LOW'), (2, 'NORMAL'), (4, 'NORMAL'), (5, 'HIGH')])
def test_document_boundaries(value, expected):
    assert compute_flag('synthetic', value, 'u', 2, 4) == expected


def test_synthetic_test_prescription_fixture():
    import os
    from ai_engine.extract import extract_from_file

    pdf_path = os.path.join(os.path.dirname(__file__), "..", "samples", "synthetic_test_prescription.pdf")
    if not os.path.exists(pdf_path):
        pytest.skip("synthetic_test_prescription.pdf not found")

    rec = extract_from_file(pdf_path, "application/pdf")
    assert rec["status"] == "ACCEPTED"
    assert rec["document_type"] == "PRESCRIPTION"
    assert rec["is_synthetic"] is True
    assert rec["patient_name"] == "Alex Testpatient"
    assert rec["doc_date"] == "2026-10-21"
    assert len(rec["tests"]) == 0, f"Expected 0 lab tests on prescription, got {len(rec['tests'])}"

    meds = rec["medicines"]
    assert len(meds) == 2, f"Expected 2 medicines, got {len(meds)}"
    med_names = [m["generic"].lower() for m in meds]
    assert "paracetamol" in med_names
    assert "cetirizine" in med_names

    pcm = next(m for m in meds if m["generic"].lower() == "paracetamol")
    assert "500" in pcm["strength"]
    assert pcm["duration_days"] == 2
    assert pcm["schedule_parsed"] == ["morning", "night"]

    cet = next(m for m in meds if m["generic"].lower() == "cetirizine")
    assert "10" in cet["strength"]
    assert cet["duration_days"] == 3
    assert cet["schedule_parsed"] == ["morning"]

