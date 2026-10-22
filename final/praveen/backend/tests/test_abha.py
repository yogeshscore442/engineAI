"""
tests/test_abha.py — Mock ABHA endpoint tests.
"""
import pytest


def test_abha_link_valid(client, default_profile_id):
    r = client.post(
        f"/api/profiles/{default_profile_id}/abha/link",
        json={"abha_number": "12345678901234"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["mock"] is True
    assert "DEMO ONLY" in data["banner"]
    assert data["linked"] is True


def test_abha_link_dashes_format(client, default_profile_id):
    r = client.post(
        f"/api/profiles/{default_profile_id}/abha/link",
        json={"abha_number": "12-3456-7890-1234"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["mock"] is True


def test_abha_link_invalid_format(client, default_profile_id):
    r = client.post(
        f"/api/profiles/{default_profile_id}/abha/link",
        json={"abha_number": "123"},
    )
    assert r.status_code == 422


def test_abha_import_mock(client, default_profile_id):
    r = client.post(f"/api/profiles/{default_profile_id}/abha/import")
    assert r.status_code == 200
    data = r.json()
    assert data["mock"] is True
    assert "DEMO ONLY" in data["banner"]
    assert isinstance(data["records_imported"], int)


def test_abha_profile_not_found(client):
    r = client.post(
        "/api/profiles/nonexistent/abha/link",
        json={"abha_number": "12345678901234"},
    )
    assert r.status_code == 404
