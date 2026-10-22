"""
services/trends.py — Compute time-series trend points for a test name.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.repositories.tests_repo import get_tests_by_name
from app.schemas import TrendPoint


def get_trend_points(db: Session, profile_id: str, test_name: str) -> list[TrendPoint]:
    """Return sorted trend points for a test name (case-insensitive)."""
    tests = get_tests_by_name(db, profile_id, test_name)
    points = []
    for t in tests:
        if t.value is not None and t.date:
            points.append(TrendPoint(
                date=t.date,
                value=t.value,
                unit=t.unit,
                record_id=t.record_id,
                flag=t.flag,
            ))
    # Sort chronologically
    points.sort(key=lambda p: p.date)
    return points
