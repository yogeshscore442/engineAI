"""
services/normalizer.py — Unit, date, test-name, medicine-name normalization.
Keeps AI-provided raw fields intact; adds normalized fields separately.
"""
from __future__ import annotations

import re
import math
from datetime import datetime
from typing import Any, Optional

from app.catalog import test_catalog
from app.catalog.brands_loader import get_generic


# ---------------------------------------------------------------------------
# Date normalization → ISO-8601 YYYY-MM-DD
# ---------------------------------------------------------------------------
_DATE_FORMATS = [
    "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y",
    "%Y/%m/%d", "%Y-%m-%d",
    "%d %b %Y", "%d %B %Y",
    "%b %d, %Y", "%B %d, %Y",
    "%d-%b-%Y", "%d-%B-%Y",
]


def normalize_date(raw: Optional[str]) -> Optional[str]:
    """Try to parse raw date string to ISO-8601. Returns None if unparsable."""
    if not isinstance(raw, str) or not raw:
        return None
    raw = raw.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None  # unparsable; keep None rather than crash


# ---------------------------------------------------------------------------
# Unit normalization — canonical forms
# ---------------------------------------------------------------------------
_UNIT_MAP: dict[str, str] = {
    "mg/dl": "mg/dL",
    "mmol/l": "mmol/L",
    "umol/l": "μmol/L",
    "g/dl": "g/dL",
    "iu/l": "IU/L",
    "u/l": "U/L",
    "ng/ml": "ng/mL",
    "pg/ml": "pg/mL",
    "meq/l": "mEq/L",
    "10^3/ul": "10³/μL",
    "10e3/ul": "10³/μL",
    "thousands/ul": "10³/μL",
    "miu/l": "mIU/L",
    "miu/ml": "mIU/mL",
    "%": "%",
    "ml/min/1.73m2": "mL/min/1.73m²",
}


def normalize_unit(unit: Optional[str]) -> Optional[str]:
    if not unit:
        return unit
    return _UNIT_MAP.get(unit.strip().lower(), unit.strip())


# ---------------------------------------------------------------------------
# Test name normalization — uses catalog lookup
# ---------------------------------------------------------------------------
def normalize_test(test_dict: dict[str, Any]) -> dict[str, Any]:
    """
    Enrich a test dict with name_canonical, loinc, and fill missing ref ranges.
    Does NOT modify AI-provided raw values; adds new keys only.
    Tolerant: unknown keys are preserved.
    """
    result = dict(test_dict)  # shallow copy, preserves extra keys

    name = result.get("name", "")
    entry = test_catalog.lookup(name)

    if entry:
        result.setdefault("name_canonical", entry.canonical)
        if not result.get("loinc"):
            result["loinc"] = entry.loinc
        # A missing unit is unknown, not permission to assume a catalog unit.
        # Preserve one-sided document ranges instead of mixing two sources.
        same_unit = bool(result.get("unit")) and normalize_unit(result["unit"]) == normalize_unit(entry.default_unit)
        if same_unit and result.get("ref_low") is None and result.get("ref_high") is None:
            result["ref_low"] = entry.ref_low
            result["ref_high"] = entry.ref_high
            result["reference_source"] = "catalog"
    else:
        result.setdefault("name_canonical", name)

    # Normalize unit
    result["unit"] = normalize_unit(result.get("unit"))
    # Never trust the incoming flag, including after a user edits a value.
    result["flag"] = "UNKNOWN"
    try:
        value = float(result["value"])
        low = float(result["ref_low"]) if result.get("ref_low") is not None else None
        high = float(result["ref_high"]) if result.get("ref_high") is not None else None
        bounds = [v for v in (low, high) if v is not None]
        if math.isfinite(value) and bounds and all(math.isfinite(v) for v in bounds) and not (low is not None and high is not None and low > high):
            result["flag"] = "LOW" if low is not None and value < low else "HIGH" if high is not None and value > high else "NORMAL"
    except (KeyError, TypeError, ValueError):
        pass

    # Normalize date
    if result.get("date"):
        result["date"] = normalize_date(result["date"])

    return result


# ---------------------------------------------------------------------------
# Medicine normalization
# ---------------------------------------------------------------------------
def normalize_medicine(med_dict: dict[str, Any]) -> dict[str, Any]:
    """
    Fill 'generic' from brands catalog if not provided by AI.
    Tolerant: extra keys preserved.
    """
    result = dict(med_dict)
    name_raw = result.get("name_raw") or result.get("name", "")
    if not result.get("generic") and name_raw:
        generic = get_generic(name_raw)
        if generic:
            result["generic"] = generic
    return result


# ---------------------------------------------------------------------------
# Top-level record normalizer
# ---------------------------------------------------------------------------
def normalize_record_json(data: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize a full record_json dict. Tolerant reader: unknown keys are preserved.
    """
    result = dict(data)

    # Normalize doc_date
    if result.get("doc_date"):
        result["doc_date"] = normalize_date(result["doc_date"])

    # Normalize tests list
    if isinstance(result.get("tests"), list):
        result["tests"] = [normalize_test(t) for t in result["tests"]]
        for test in result["tests"]:
            if not test.get("date"):
                test["date"] = result.get("doc_date")
    else:
        result["tests"] = []

    # Normalize medicines list
    if isinstance(result.get("medicines"), list):
        result["medicines"] = [normalize_medicine(m) for m in result["medicines"]]
    else:
        result["medicines"] = []

    # Normalize diagnoses list
    if isinstance(result.get("diagnoses"), list):
        norm_diag = []
        for d in result["diagnoses"]:
            if isinstance(d, dict):
                norm_d = dict(d)
                if not norm_d.get("text"):
                    norm_d["text"] = norm_d.get("name") or norm_d.get("condition") or ""
                norm_diag.append(norm_d)
            elif isinstance(d, str):
                norm_diag.append({"text": d, "confidence": 0.9})
        result["diagnoses"] = norm_diag
    else:
        result["diagnoses"] = []

    # Ensure needs_review is a list in record_json
    if not isinstance(result.get("needs_review"), list):
        result["needs_review"] = []

    return result
