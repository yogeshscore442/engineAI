"""
catalog/brands_loader.py — Loads brands.csv (brand -> generic mapping) for duplicate-brand alerts.
Person 1 is expected to provide brands.csv; this falls back to built-in stubs if absent.
"""
from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Default stub table (common Indian generic/brand pairs)
_BUILTIN_TABLE: dict[str, str] = {
    # brand (lower) -> generic (canonical lower)
    "crocin": "paracetamol",
    "dolo": "paracetamol",
    "combiflam": "ibuprofen+paracetamol",
    "brufen": "ibuprofen",
    "metformin": "metformin",
    "glucophage": "metformin",
    "obimet": "metformin",
    "glycomet": "metformin",
    "amlodipine": "amlodipine",
    "amlong": "amlodipine",
    "stamlo": "amlodipine",
    "atorvastatin": "atorvastatin",
    "atorva": "atorvastatin",
    "lipitor": "atorvastatin",
    "rosuvastatin": "rosuvastatin",
    "rozucor": "rosuvastatin",
    "crestor": "rosuvastatin",
    "aspirin": "aspirin",
    "ecosprin": "aspirin",
    "pantoprazole": "pantoprazole",
    "pantop": "pantoprazole",
    "pan": "pantoprazole",
    "omeprazole": "omeprazole",
    "omez": "omeprazole",
    "ramipril": "ramipril",
    "cardace": "ramipril",
    "telmisartan": "telmisartan",
    "telmikind": "telmisartan",
    "telma": "telmisartan",
    "metoprolol": "metoprolol",
    "betaloc": "metoprolol",
    "met xl": "metoprolol",
    "glimepiride": "glimepiride",
    "amaryl": "glimepiride",
    "insulin glargine": "insulin glargine",
    "lantus": "insulin glargine",
    "toujeo": "insulin glargine",
}

_brand_map: dict[str, str] = {}


def load_brands(csv_path: Optional[Path] = None) -> None:
    """Load brand->generic mapping from CSV. Falls back to built-in if not found."""
    global _brand_map
    _brand_map = dict(_BUILTIN_TABLE)  # start with built-ins

    if csv_path and csv_path.exists():
        try:
            with open(csv_path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    brand = (row.get("brand_name") or row.get("brand") or row.get("Brand") or "").strip().lower()
                    generic = (row.get("generic_name") or row.get("generic") or row.get("Generic") or "").strip().lower()
                    if brand and generic:
                        _brand_map[brand] = generic
            logger.info("Brands CSV loaded: %d entries", len(_brand_map))
        except Exception as exc:
            logger.warning("Could not load brands.csv (%s), using built-ins.", exc)
    else:
        logger.info("brands.csv not found; using %d built-in entries.", len(_brand_map))


def get_generic(brand_name: str) -> Optional[str]:
    """Return canonical generic name for a brand, or None if unknown."""
    return _brand_map.get(brand_name.strip().lower())
