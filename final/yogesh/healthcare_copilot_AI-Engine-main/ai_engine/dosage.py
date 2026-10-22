"""
dosage.py — Parse Indian medical dosage strings into structured fields.

Handles:
  1-0-1, 1-1-1, 0-0-1, 1-0-0 etc.      → schedule_parsed
  OD, BD, TDS, QID, HS, SOS             → schedule_parsed
  before food / after food / AC / PC    → food_instruction
  x 5 days / for 5 days / 5 days        → duration_days

Returns:
  (schedule_parsed: list[str], food_instruction: str|None, duration_days: int|None)
"""
from __future__ import annotations

import re
from typing import Optional, Tuple

# Slot positions in N-N-N patterns
_SLOTS = ["morning", "afternoon", "night"]

# Abbreviation → slots
_ABBREV: dict[str, list[str]] = {
    "once daily": ["morning"],
    "once a day": ["morning"],
    "twice daily": ["morning", "night"],
    "two times daily": ["morning", "night"],
    "two times a day": ["morning", "night"],
    "thrice daily": ["morning", "afternoon", "night"],
    "three times daily": ["morning", "afternoon", "night"],
    "three times a day": ["morning", "afternoon", "night"],
    "four times daily": ["morning", "afternoon", "night"],
    "four times a day": ["morning", "afternoon", "night"],
    "at bedtime": ["night"],
    "bedtime": ["night"],
    "od":  ["morning"],
    "bd":  ["morning", "night"],
    "bid": ["morning", "night"],
    "tds": ["morning", "afternoon", "night"],
    "tid": ["morning", "afternoon", "night"],
    "qid": ["morning", "afternoon", "night"],   # 4× treated as M+A+N for display
    "qds": ["morning", "afternoon", "night"],
    "hs":  ["night"],
    "hora somni": ["night"],
    "sos": [],
    "prn": [],
    "stat": ["morning"],
    "nocte": ["night"],
    "mane": ["morning"],
    "om": ["morning"],
    "on": ["night"],
    "bbf": ["morning"],
    "abf": ["morning"],
}

_FOOD_BEFORE = re.compile(
    r"\b(?:before\s+food|before\s+meals?|before\s+breakfast|before\s+lunch|before\s+dinner|a\.?c\.?|ac\b|bbf\b|b\.b\.f\.?|empty\s+stomach)\b",
    re.IGNORECASE,
)
_FOOD_AFTER = re.compile(
    r"\b(?:after\s+food|after\s+meals?|after\s+breakfast|after\s+lunch|after\s+dinner|p\.?c\.?|pc\b|abf\b|a\.b\.f\.?|with\s+food|with\s+meals?)\b",
    re.IGNORECASE,
)
_DURATION = re.compile(
    r"(?:x\s*|for\s+|;\s*)?(\d+)\s*(?:days?|weeks?|months?|d\b)",
    re.IGNORECASE,
)
# Matches 1-0-1, 1+0+1, 1/0/1, 1:0:1, 1.0.1, 1 + 0 + 1, 1/2+0+1/2, etc.
_SLOT_NUM = r"(?:\d+(?:\.\d+)?|\d+/\d+)"
_DELIM = r"[\-\+\/\:\.]"
_MULTI_SLOT_PATTERN = re.compile(
    rf"\b({_SLOT_NUM})\s*{_DELIM}\s*({_SLOT_NUM})\s*{_DELIM}\s*({_SLOT_NUM})(?:\s*{_DELIM}\s*({_SLOT_NUM}))?\b"
)
_ABBREV_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in sorted(_ABBREV.keys(), key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)


def parse_schedule(schedule_raw: Optional[str]) -> Tuple[list, Optional[str], Optional[int]]:
    """
    Parse *schedule_raw* string into:
        schedule_parsed  : list of "morning" | "afternoon" | "night"
        food_instruction : "before_food" | "after_food" | None
        duration_days    : int | None

    Examples:
        "1-0-1 after food x 5 days" → (["morning","night"], "after_food", 5)
        "1+0+1 BBF x 5d" → (["morning","night"], "before_food", 5)
        "BD" → (["morning","night"], None, None)
        "TDS AC" → (["morning","afternoon","night"], "before_food", None)
        "" / None → ([], None, None)
    """
    if not schedule_raw or not schedule_raw.strip():
        return [], None, None

    text = schedule_raw.strip()
    # Normalize spaces around dashes/pluses/slashes: e.g. "1 + 0 + 1" -> "1+0+1"
    text = re.sub(r"(\d)\s*([\-\+\/\:])\s*(\d)", r"\1\2\3", text)

    # ── Food instruction ──────────────────────────────────────────────────────
    food: Optional[str] = None
    if _FOOD_BEFORE.search(text):
        food = "before_food"
    elif _FOOD_AFTER.search(text):
        food = "after_food"

    # ── Duration ──────────────────────────────────────────────────────────────
    duration: Optional[int] = None
    dur_match = _DURATION.search(text)
    if dur_match:
        try:
            val = int(dur_match.group(1))
            matched_str = dur_match.group(0).lower()
            if "week" in matched_str:
                duration = val * 7
            elif "month" in matched_str:
                duration = val * 30
            else:
                duration = val
        except ValueError:
            pass

    # ── Schedule slots ────────────────────────────────────────────────────────
    slots: list[str] = []

    # Search for multi-slot pattern (1-0-1, 1+0+1, 0-0-1, etc.)
    slot_match = _MULTI_SLOT_PATTERN.search(text)
    if slot_match:
        for i, grp in enumerate(_SLOTS):
            val = slot_match.group(i + 1)
            if val and val != "0" and val != "0.0":
                slots.append(grp)
        # Check 4th slot if present (e.g. 1-1-1-1 or 1+1+1+1)
        val4 = slot_match.group(4)
        if val4 and val4 != "0" and val4 != "0.0" and "night" not in slots:
            slots.append("night")
    else:
        # Try abbreviation
        abbrev_match = _ABBREV_PATTERN.search(text)
        if abbrev_match:
            key = abbrev_match.group(1).lower()
            slots = list(_ABBREV.get(key, []))

    return slots, food, duration


def parse_all(name_raw: str, schedule_raw: Optional[str]) -> dict:
    """
    Convenience wrapper returning a dict ready to merge into a MedicineRecord.
    """
    slots, food, dur = parse_schedule(schedule_raw)
    return {
        "schedule_parsed": slots,
        "food_instruction": food,
        "duration_days": dur,
    }
