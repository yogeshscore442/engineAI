"""
tests/test_upload.py — Upload endpoint tests.
Covers: happy path, bad extension, oversize, corrupt file, duplicate.
"""
import io
import pytest
from tests.conftest import make_fake_pdf, make_fake_png, make_fake_jpg


def test_upload_happy_path_pdf(client, default_profile_id):
    pdf = make_fake_pdf() + b"\n%unique_pdf_1"
    r = client.post(
        f"/api/profiles/{default_profile_id}/records",
        files={"file": ("test_lab.pdf", io.BytesIO(pdf), "application/pdf")},
        data={"lang": "en"},
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert "record_id" in data
    assert data["status"] == "draft"
    assert "record" in data


def test_upload_happy_path_png(client, default_profile_id):
    png = make_fake_png() + b"\n%unique_png_1"
    r = client.post(
        f"/api/profiles/{default_profile_id}/records",
        files={"file": ("scan.png", io.BytesIO(png), "image/png")},
        data={"lang": "en"},
    )
    assert r.status_code == 201, r.text


def test_upload_bad_extension(client, default_profile_id):
    r = client.post(
        f"/api/profiles/{default_profile_id}/records",
        files={"file": ("malware.exe", io.BytesIO(b"MZ\x90\x00"), "application/octet-stream")},
        data={"lang": "en"},
    )
    assert r.status_code == 415
    data = r.json()
    assert "error" in data or "detail" in data


def test_upload_fake_extension_content_mismatch(client, default_profile_id):
    """File claims to be PDF but has wrong magic bytes."""
    r = client.post(
        f"/api/profiles/{default_profile_id}/records",
        files={"file": ("fake.pdf", io.BytesIO(b"NOTPDF" + b"\x00" * 100), "application/pdf")},
        data={"lang": "en"},
    )
    assert r.status_code == 415
    body = r.json()
    err = body.get("error", body)
    if isinstance(err, dict):
        assert err.get("code") in ("INVALID_FILE_CONTENT", "INVALID_FILE_TYPE", "UNSUPPORTED_MEDIA_TYPE")


def test_upload_oversize_file(client, default_profile_id):
    big_content = b"%PDF-1.4\n" + b"A" * (11 * 1024 * 1024)  # 11 MB
    r = client.post(
        f"/api/profiles/{default_profile_id}/records",
        files={"file": ("big.pdf", io.BytesIO(big_content), "application/pdf")},
        data={"lang": "en"},
    )
    assert r.status_code == 413


def test_upload_profile_not_found(client):
    pdf = make_fake_pdf()
    r = client.post(
        "/api/profiles/nonexistent-profile/records",
        files={"file": ("test.pdf", io.BytesIO(pdf), "application/pdf")},
        data={"lang": "en"},
    )
    assert r.status_code == 404
    body = r.json()
    err = body.get("error", body)
    if isinstance(err, dict):
        assert err.get("code") in ("PROFILE_NOT_FOUND", "NOT_FOUND")



def test_duplicate_upload_returns_existing(client, default_profile_id):
    """Uploading the same file twice should return the same record."""
    pdf = make_fake_pdf()
    r1 = client.post(
        f"/api/profiles/{default_profile_id}/records",
        files={"file": ("dup_test.pdf", io.BytesIO(pdf), "application/pdf")},
        data={"lang": "en"},
    )
    r2 = client.post(
        f"/api/profiles/{default_profile_id}/records",
        files={"file": ("dup_test.pdf", io.BytesIO(pdf), "application/pdf")},
        data={"lang": "en"},
    )
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["record_id"] == r2.json()["record_id"]
