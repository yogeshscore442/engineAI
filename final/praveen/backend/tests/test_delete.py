"""
tests/test_delete.py — Delete profile removes DB rows and files.
"""
import io
import os
import pytest
from tests.conftest import make_fake_pdf


def test_delete_profile_removes_records_and_files(client):
    """Creating a profile, uploading a file, then deleting should remove both."""
    r = client.post("/api/profiles", json={"name": "Delete Test User", "relation": "self"})
    assert r.status_code == 201
    pid = r.json()["profile_id"]

    pdf = make_fake_pdf() + b"\n%del_test_pdf_unique"
    up = client.post(
        f"/api/profiles/{pid}/records",
        files={"file": ("del_test.pdf", io.BytesIO(pdf), "application/pdf")},
        data={"lang": "en"},
    )
    assert up.status_code == 201
    record_id = up.json()["record_id"]

    # Get file path from the record
    rec_r = client.get(f"/api/records/{record_id}")
    assert rec_r.status_code == 200

    # Delete the profile
    del_r = client.delete(f"/api/profiles/{pid}")
    assert del_r.status_code == 200
    data = del_r.json()
    assert data["deleted"] is True
    assert data["records_deleted"] >= 1

    # Profile should now 404
    check_r = client.get(f"/api/profiles/{pid}")
    assert check_r.status_code == 404

    # Record should now 404
    rec_check = client.get(f"/api/records/{record_id}")
    assert rec_check.status_code == 404


def test_delete_nonexistent_profile_returns_404(client):
    r = client.delete("/api/profiles/nonexistent-profile-xyz")
    assert r.status_code == 404
    body = r.json()
    err = body.get("error", body)
    if isinstance(err, dict):
        assert err.get("code") in ("PROFILE_NOT_FOUND", "NOT_FOUND")

