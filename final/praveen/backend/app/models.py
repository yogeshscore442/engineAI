"""
models.py — SQLAlchemy ORM models.
All types are Postgres-portable (no SQLite-only hacks).
Primary keys are UUID strings for FHIR/ABDM compatibility.
ON DELETE CASCADE enforced via FK + DB pragma.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------
class Profile(Base):
    __tablename__ = "profiles"

    profile_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    relation: Mapped[str] = mapped_column(String(100), nullable=False, default="self")
    abha_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    abha_linked_mock: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    records: Mapped[list[Record]] = relationship(
        "Record", back_populates="profile", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# Record
# ---------------------------------------------------------------------------
class Record(Base):
    __tablename__ = "records"

    record_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    profile_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("profiles.profile_id", ondelete="CASCADE"), nullable=False
    )
    doc_type: Mapped[str] = mapped_column(String(100), nullable=False)
    doc_date: Mapped[str | None] = mapped_column(String(10), nullable=True)  # ISO-8601 date
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft | confirmed
    file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    record_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    schema_version: Mapped[int] = mapped_column(Integer, default=1)
    source: Mapped[str] = mapped_column(String(20), default="mock")  # ai | mock | abha_mock
    language: Mapped[str] = mapped_column(String(10), default="en")
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False)
    headline: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    profile: Mapped[Profile] = relationship("Profile", back_populates="records")
    medicines: Mapped[list[Medicine]] = relationship(
        "Medicine", back_populates="record", cascade="all, delete-orphan"
    )
    tests: Mapped[list[Test]] = relationship(
        "Test", back_populates="record", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_records_profile_doc_date", "profile_id", "doc_date"),
        Index("ix_records_profile_sha256", "profile_id", "file_sha256"),
    )


# ---------------------------------------------------------------------------
# Medicine (projection from record_json)
# ---------------------------------------------------------------------------
class Medicine(Base):
    __tablename__ = "medicines"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    record_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("records.record_id", ondelete="CASCADE"), nullable=False
    )
    profile_id: Mapped[str] = mapped_column(String(36), nullable=False)
    name_raw: Mapped[str] = mapped_column(String(255), nullable=False)
    generic: Mapped[str | None] = mapped_column(String(255), nullable=True)
    strength: Mapped[str | None] = mapped_column(String(100), nullable=True)
    schedule_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    schedule_parsed: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON string
    duration_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    record: Mapped[Record] = relationship("Record", back_populates="medicines")


# ---------------------------------------------------------------------------
# Test result (projection from record_json)
# ---------------------------------------------------------------------------
class Test(Base):
    __tablename__ = "tests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    record_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("records.record_id", ondelete="CASCADE"), nullable=False
    )
    profile_id: Mapped[str] = mapped_column(String(36), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    name_canonical: Mapped[str | None] = mapped_column(String(255), nullable=True)
    loinc: Mapped[str | None] = mapped_column(String(20), nullable=True)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ref_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    ref_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    flag: Mapped[str | None] = mapped_column(String(5), nullable=True)   # H | L | N
    flag_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    date: Mapped[str | None] = mapped_column(String(10), nullable=True)  # ISO-8601
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    record: Mapped[Record] = relationship("Record", back_populates="tests")

    __table_args__ = (
        Index("ix_tests_profile_name_date", "profile_id", "name_canonical", "date"),
    )
