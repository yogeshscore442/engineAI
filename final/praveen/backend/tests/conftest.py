"""
tests/conftest.py — Shared fixtures for pytest.
Uses an in-memory SQLite DB per test session.
"""
import io
import os
import pytest
import tempfile

# Point to in-memory DB and temp upload dir BEFORE importing app
os.environ["DATABASE_URL"] = "sqlite://"   # in-memory
os.environ["USE_MOCK_AI"] = "true"

import tempfile
_tmpdir = tempfile.mkdtemp()
os.environ["UPLOAD_DIR"] = _tmpdir

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base, get_db, engine, SessionLocal
from app.main import app
from app.catalog.brands_loader import load_brands

TestingSessionLocal = SessionLocal


@pytest.fixture(autouse=True, scope="session")
def setup_db():
    from app import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    load_brands(None)
    yield
    Base.metadata.drop_all(bind=engine)



def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def db():
    sess = TestingSessionLocal()
    yield sess
    sess.close()


@pytest.fixture(scope="session")
def default_profile_id(client):
    """Create a test profile and return its ID."""
    r = client.post("/api/profiles", json={"name": "Test User", "relation": "self"})
    assert r.status_code == 201
    return r.json()["profile_id"]


def make_fake_pdf() -> bytes:
    """Return minimal valid PDF bytes."""
    return b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\nxref\n0 1\n0000000000 65535 f \ntrailer\n<< /Size 1 /Root 1 0 R >>\nstartxref\n9\n%%EOF"


def make_fake_png() -> bytes:
    """Return minimal valid PNG bytes."""
    import struct, zlib
    def chunk(name, data):
        c = name + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    idat = zlib.compress(b"\x00\xff\xff\xff")
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


def make_fake_jpg() -> bytes:
    """Return minimal valid JPEG bytes."""
    return b"\xff\xd8\xff\xe0" + b"\x00" * 100 + b"\xff\xd9"
