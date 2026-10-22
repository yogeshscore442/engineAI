"""
repositories/tests_repo.py — All DB queries for Test model.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models import Test


def get_tests_by_record(db: Session, record_id: str) -> list[Test]:
    return db.query(Test).filter(Test.record_id == record_id).all()


def get_tests_by_profile(db: Session, profile_id: str) -> list[Test]:
    return db.query(Test).filter(Test.profile_id == profile_id).all()


def get_tests_by_name(db: Session, profile_id: str, name: str) -> list[Test]:
    """Case-insensitive match on name_canonical or name."""
    from app.catalog.test_catalog import lookup
    entry = lookup(name.strip())
    name_lower = (entry.canonical if entry else name).strip().lower()
    return (
        db.query(Test)
        .filter(
            Test.profile_id == profile_id,
            or_(func.lower(Test.name_canonical) == name_lower, func.lower(Test.name) == name.strip().lower()),
        )
        .order_by(Test.date.asc())
        .all()
    )


def delete_tests_by_record(db: Session, record_id: str) -> int:
    count = db.query(Test).filter(Test.record_id == record_id).delete()
    db.flush()
    return count


def bulk_insert_tests(db: Session, record_id: str, profile_id: str,
                      tests_data: list[dict]) -> list[Test]:
    rows = []
    for t in tests_data:
        # Safely parse value
        raw_val = t.get("value")
        value: Optional[float] = None
        if raw_val is not None:
            try:
                value = float(raw_val)
            except (TypeError, ValueError):
                value = None

        # Parse ref_low / ref_high
        ref_low: Optional[float] = None
        ref_high: Optional[float] = None
        try:
            ref_low = float(t["ref_low"]) if t.get("ref_low") is not None else None
        except (TypeError, ValueError):
            pass
        try:
            ref_high = float(t["ref_high"]) if t.get("ref_high") is not None else None
        except (TypeError, ValueError):
            pass

        # Verify flag from values
        flag = t.get("flag")
        flag_verified = False
        if value is not None and ref_low is not None and ref_high is not None:
            computed_flag = "N"
            if value > ref_high:
                computed_flag = "H"
            elif value < ref_low:
                computed_flag = "L"
            flag = computed_flag
            flag_verified = True

        test = Test(
            record_id=record_id,
            profile_id=profile_id,
            name=t.get("name", ""),
            name_canonical=t.get("name_canonical") or t.get("name", ""),
            loinc=t.get("loinc"),
            value=value,
            unit=t.get("unit"),
            ref_low=ref_low,
            ref_high=ref_high,
            flag=flag,
            flag_verified=flag_verified,
            date=t.get("date"),
            confidence=t.get("confidence"),
        )
        db.add(test)
        rows.append(test)
    db.flush()
    return rows
