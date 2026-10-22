"""
repositories/medicines_repo.py — All DB queries for Medicine model.
"""
from __future__ import annotations

import json
from typing import Optional

from sqlalchemy.orm import Session

from app.models import Medicine


def get_medicines_by_record(db: Session, record_id: str) -> list[Medicine]:
    return db.query(Medicine).filter(Medicine.record_id == record_id).all()


def get_medicines_by_profile(db: Session, profile_id: str) -> list[Medicine]:
    return db.query(Medicine).filter(Medicine.profile_id == profile_id).all()


def delete_medicines_by_record(db: Session, record_id: str) -> int:
    count = db.query(Medicine).filter(Medicine.record_id == record_id).delete()
    db.flush()
    return count


def bulk_insert_medicines(db: Session, record_id: str, profile_id: str,
                          medicines_data: list[dict]) -> list[Medicine]:
    rows = []
    for m in medicines_data:
        schedule_parsed = m.get("schedule_parsed")
        if schedule_parsed is not None and not isinstance(schedule_parsed, str):
            schedule_parsed = json.dumps(schedule_parsed)
        med = Medicine(
            record_id=record_id,
            profile_id=profile_id,
            name_raw=m.get("name_raw") or m.get("name", ""),
            generic=m.get("generic"),
            strength=m.get("strength"),
            schedule_raw=m.get("schedule_raw") or m.get("schedule"),
            schedule_parsed=schedule_parsed,
            duration_days=m.get("duration_days"),
            confidence=m.get("confidence"),
        )
        db.add(med)
        rows.append(med)
    db.flush()
    return rows
