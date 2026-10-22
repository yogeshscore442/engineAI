"""
repositories/records_repo.py — All DB queries for Record model.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models import Record


def get_record(db: Session, record_id: str) -> Optional[Record]:
    return db.query(Record).filter(Record.record_id == record_id).first()


def get_records_by_profile(db: Session, profile_id: str) -> list[Record]:
    return (
        db.query(Record)
        .filter(Record.profile_id == profile_id)
        .order_by(Record.doc_date.desc(), Record.created_at.desc())
        .all()
    )


def find_by_sha256(db: Session, profile_id: str, sha256: str) -> Optional[Record]:
    return (
        db.query(Record)
        .filter(Record.profile_id == profile_id, Record.file_sha256 == sha256)
        .first()
    )


def create_record(db: Session, **kwargs) -> Record:
    if "record_json" in kwargs and not isinstance(kwargs["record_json"], str):
        kwargs["record_json"] = json.dumps(kwargs["record_json"])
    record = Record(**kwargs)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def update_record(db: Session, record_id: str, **kwargs) -> Optional[Record]:
    record = get_record(db, record_id)
    if not record:
        return None
    if "record_json" in kwargs and not isinstance(kwargs["record_json"], str):
        kwargs["record_json"] = json.dumps(kwargs["record_json"])
    for k, v in kwargs.items():
        setattr(record, k, v)
    db.commit()
    db.refresh(record)
    return record


def confirm_record(db: Session, record_id: str, record_json: dict,
                   headline: Optional[str] = None) -> Optional[Record]:
    from app.services.validators import compute_needs_review
    return update_record(
        db,
        record_id,
        status="confirmed",
        record_json=record_json,
        confirmed_at=datetime.now(timezone.utc),
        headline=headline,
        doc_date=record_json.get("doc_date"),
        doc_type=record_json.get("doc_type", "lab_report"),
        language=record_json.get("language", "en"),
        needs_review=compute_needs_review(record_json),
    )


def delete_record(db: Session, record_id: str) -> bool:
    record = get_record(db, record_id)
    if not record:
        return False
    db.delete(record)
    db.commit()
    return True
