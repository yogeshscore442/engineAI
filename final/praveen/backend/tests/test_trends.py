"""
tests/test_trends.py — Trends endpoint tests.
"""
import io
import pytest
from tests.conftest import make_fake_pdf


@pytest.fixture(scope="module")
def profile_with_trend_data(client):
    """Create a profile with multiple HbA1c readings for trending."""
    r = client.post("/api/profiles", json={"name": "Trend Test User", "relation": "self"})
    pid = r.json()["profile_id"]
    for date, value in [("2024-01-10", 9.2), ("2024-03-15", 7.8), ("2024-06-15", 6.8)]:
        pdf = make_fake_pdf() + f"\n%trend_{date}".encode()
        up = client.post(
            f"/api/profiles/{pid}/records",
            files={"file": (f"lab_{date}.pdf", io.BytesIO(pdf), "application/pdf")},
            data={"lang": "en"},
        )

        rid = up.json()["record_id"]
        client.put(
            f"/api/records/{rid}",
            json={
                "record_json": {
                    "doc_type": "lab_report",
                    "doc_date": date,
                    "tests": [
                        {"name": "HbA1c", "value": value, "unit": "%",
                         "ref_low": 4.0, "ref_high": 5.7, "flag": "H" if value > 5.7 else "N",
                         "date": date, "confidence": 0.95}
                    ],
                    "medicines": [],
                    "diagnoses": [],
                }
            },
        )
    return pid


def test_trends_sorted_ascending(client, profile_with_trend_data):
    pid = profile_with_trend_data
    r = client.get(f"/api/profiles/{pid}/trends?test=HbA1c")
    assert r.status_code == 200
    data = r.json()
    assert data["profile_id"] == pid
    assert data["test_name"] == "HbA1c"
    points = data["points"]
    assert len(points) >= 3
    dates = [p["date"] for p in points]
    assert dates == sorted(dates), "Trend points must be sorted ascending by date"
    values = [p["value"] for p in points]
    assert 9.2 in values
    assert 6.8 in values


def test_trends_unknown_test_returns_empty(client, profile_with_trend_data):
    pid = profile_with_trend_data
    r = client.get(f"/api/profiles/{pid}/trends?test=NonExistentTest999")
    assert r.status_code == 200
    data = r.json()
    assert data["points"] == []


def test_trends_profile_not_found(client):
    r = client.get("/api/profiles/nonexistent-xyz/trends?test=HbA1c")
    assert r.status_code == 404
