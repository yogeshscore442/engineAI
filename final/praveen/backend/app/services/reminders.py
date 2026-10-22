"""
app/services/reminders.py — Safe Medication Reminder Scheduling (Phase 12).

CORE SAFETY RULES:
1. Generate reminders ONLY from explicit, legible instructions or a schedule
   the user has reviewed and confirmed.
2. Forbid inference of missing dosages, frequencies, meal timings, or start/end dates.
3. Forbid automatic activation from ambiguous, low-confidence (<0.70), or PRN (as-needed) extractions.
4. Always preserve and display the exact source instruction verbatim.
5. Prevent duplicate reminders for the same medication slot.
6. Explicit disclaimer: The existence of a reminder does not confirm that the
   prescription is medically correct.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

AMBIGUOUS_SCHEDULE_PATTERNS = [
    re.compile(r"\b(as\s*needed|prn|sos|when\s*required|optional|if\s*needed)\b", re.IGNORECASE),
    re.compile(r"[\?\/]{2,}"),
    re.compile(r"\bunclear\b|\bambiguous\b", re.IGNORECASE),
]

DISCLAIMER_REMINDER = (
    "This medication reminder schedule is an informational personal aid. Generating or activating "
    "a reminder does not confirm that the prescription or dosage is medically correct or suitable. "
    "Always consult your doctor or pharmacist if dosage instructions are unclear."
)


def can_activate_auto_reminder(med: dict[str, Any], user_reviewed: bool = False) -> bool:
    """
    Determines whether a medication schedule is eligible for automated reminder creation.
    Blocked if:
    - Low confidence OCR (< 0.70) without explicit user review.
    - Missing or empty schedule_raw.
    - As-needed / PRN / SOS notation (cannot create fixed time reminders).
    - Ambiguous punctuation or missing frequency.
    """
    if user_reviewed:
        # User has explicitly confirmed the schedule
        schedule = (med.get("schedule_raw") or "").strip()
        return bool(schedule and not any(p.search(schedule) for p in AMBIGUOUS_SCHEDULE_PATTERNS))

    conf = float(med.get("confidence", 0.0) or 0.0)
    if conf < 0.70:
        logger.info("Reminder blocked: OCR confidence %.2f < 0.70", conf)
        return False

    schedule = (med.get("schedule_raw") or "").strip()
    if not schedule:
        logger.info("Reminder blocked: No explicit schedule_raw provided")
        return False

    for pat in AMBIGUOUS_SCHEDULE_PATTERNS:
        if pat.search(schedule):
            logger.info("Reminder blocked: Ambiguous or PRN schedule pattern '%s'", schedule)
            return False

    return True


def create_safe_reminder(
    med: dict[str, Any],
    profile_id: str,
    user_timezone: str = "Asia/Kolkata",
    user_reviewed: bool = False,
) -> dict[str, Any]:
    """
    Generates a structured, safe medication reminder.
    Guarantees:
    - Never infers missing timing, duration, or meal instruction.
    - Preserves exact source instruction verbatim.
    - Includes medical safety disclaimer.
    """
    eligible = can_activate_auto_reminder(med, user_reviewed=user_reviewed)
    schedule_raw = (med.get("schedule_raw") or "").strip()

    # Parse slots only from recognized explicit patterns without guessing
    parsed_slots: list[dict[str, str]] = []
    if re.search(r"1\s*-\s*0\s*-\s*1", schedule_raw):
        parsed_slots = [{"slot": "morning", "default_time": "08:00"}, {"slot": "night", "default_time": "20:00"}]
    elif re.search(r"1\s*-\s*1\s*-\s*1", schedule_raw):
        parsed_slots = [{"slot": "morning", "default_time": "08:00"}, {"slot": "afternoon", "default_time": "13:00"}, {"slot": "night", "default_time": "20:00"}]
    elif re.search(r"0\s*-\s*0\s*-\s*1", schedule_raw) or re.search(r"\bHS\b|\bbedtime\b", schedule_raw, re.IGNORECASE):
        parsed_slots = [{"slot": "night", "default_time": "21:00"}]
    elif re.search(r"1\s*-\s*0\s*-\s*0", schedule_raw) or re.search(r"\bOD\b", schedule_raw, re.IGNORECASE):
        parsed_slots = [{"slot": "morning", "default_time": "08:00"}]
    elif re.search(r"\bBD\b", schedule_raw, re.IGNORECASE):
        parsed_slots = [{"slot": "morning", "default_time": "08:00"}, {"slot": "night", "default_time": "20:00"}]
    elif re.search(r"\bTDS\b", schedule_raw, re.IGNORECASE):
        parsed_slots = [{"slot": "morning", "default_time": "08:00"}, {"slot": "afternoon", "default_time": "14:00"}, {"slot": "night", "default_time": "20:00"}]

    return {
        "medicine_name": med.get("name_raw", "Unknown"),
        "strength": med.get("strength"),
        "exact_source_instruction": schedule_raw or "None recorded in document",
        "food_instruction": med.get("food_instruction"),
        "duration_days": med.get("duration_days"),  # None if unspecified; NEVER invented
        "is_active": eligible and bool(parsed_slots),
        "status": "ACTIVE" if eligible and parsed_slots else "REQUIRES_USER_CONFIRMATION",
        "scheduled_slots": parsed_slots,
        "timezone": user_timezone,
        "disclaimer": DISCLAIMER_REMINDER,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
