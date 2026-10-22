"""
services/alerts/__init__.py — Alert rule registry.
New rule: create a file, implement AlertRule, add to RULES list. No other changes needed.
"""
from __future__ import annotations

from typing import Protocol

from sqlalchemy.orm import Session

from app.schemas import AlertItem


class AlertRule(Protocol):
    def check(self, db: Session, profile_id: str) -> list[AlertItem]:
        ...


from app.services.alerts.duplicate_generic import DuplicateGenericRule  # noqa: E402

RULES: list[AlertRule] = [
    DuplicateGenericRule(),
]


def run_all_alerts(db: Session, profile_id: str) -> list[AlertItem]:
    """Run all registered alert rules and collect results."""
    results = []
    for rule in RULES:
        try:
            results.extend(rule.check(db, profile_id))
        except Exception:
            pass  # Rule failure must not break the endpoint
    return results
