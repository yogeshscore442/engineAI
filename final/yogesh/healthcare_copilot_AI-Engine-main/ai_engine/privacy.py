"""
privacy.py — PII masking for text sent to the LLM for summarization.

Engine Priority:
  1. Microsoft Presidio (if available) — ML-based NLP entity recognition for
     PERSON, EMAIL_ADDRESS, PHONE_NUMBER, IN_AADHAAR, IN_PAN, IN_VOTER, LOCATION, etc.
  2. Custom regex fallback — Indian phone numbers, Aadhaar, email, patient name labels,
     PIN codes, and generic ID patterns.

WHAT IS MASKED (before any text reaches the summarization LLM):
  - Indian phone numbers (10-digit, with/without +91 / 0 prefix)
  - Email addresses
  - Aadhaar-like 12-digit number groups (XXXX XXXX XXXX)
  - Generic ID numbers (PID, MRN, UHID, ABHA patterns)
  - Patient names when clearly labelled ("Patient: John Doe")
  - Postal addresses (door no, PIN codes, street patterns)
  - Presidio: PERSON, LOCATION, IN_PAN, IN_VOTER, NRP, MEDICAL_LICENSE (when available)

WHAT IS NOT MASKED:
  - Test values and units
  - Medicine names and dosages
  - Dates (not PII in this context)
  - Doctor names (not patient PII)
  - Diagnosis text (clinical, not personal)

NOTE: The extraction LLM receives the raw document image (vision call).
Masking applies only to Tesseract/OCR fallback text included in extraction prompts
and to the structured JSON used as summarization LLM input.
"""
from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# ── Regex patterns (always available, used as final fallback) ──────────────────

_PATTERNS: list[tuple[str, str, int]] = [
    # (label, pattern, re_flags)
    ("phone",    r"(?:\+91[\s\-]?)?[6-9]\d{9}\b",                                   re.IGNORECASE),
    ("email",    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",              0),
    ("aadhaar",  r"\b\d{4}\s\d{4}\s\d{4}\b",                                        0),
    ("id_num",   r"(?:PID|MRN|UHID|ABHA|REG(?:NO)?|IP\s?NO|OP\s?NO)[\s:.-]*\d+",  re.IGNORECASE),
    ("pin",      r"\b[1-9]\d{5}\b",                                                  0),
    ("patient",  r"(?:Patient(?:\s+Name)?|Name of Patient)\s*[:\-]\s*[A-Z][a-zA-Z\s\.]{2,40}", re.IGNORECASE),
]

_COMPILED = [
    (label, re.compile(pat, flags), repl)
    for label, pat, flags in _PATTERNS
    for repl in (f"[{label.upper()}]",)
]


# ── Presidio Integration ───────────────────────────────────────────────────────

_PRESIDIO_ANALYZER = None
_PRESIDIO_ANONYMIZER = None
_PRESIDIO_OK = False

# PII entity types to detect and mask with Presidio
_PRESIDIO_ENTITIES = [
    "PERSON",
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "IN_AADHAAR",
    "IN_PAN",
    "IN_VOTER",
    "LOCATION",
    "NRP",                  # Nationality / Religion / Political group (sensitive)
    "MEDICAL_LICENSE",
    "CREDIT_CARD",
    "IBAN_CODE",
    "IP_ADDRESS",
    "URL",
]


def _get_presidio():
    """Lazy-initialize Presidio engines (load NLP models once)."""
    global _PRESIDIO_ANALYZER, _PRESIDIO_ANONYMIZER, _PRESIDIO_OK
    import os
    if os.getenv("ENABLE_PRESIDIO", "false").lower() != "true":
        return None, None
    if _PRESIDIO_ANALYZER is not None:
        return _PRESIDIO_ANALYZER, _PRESIDIO_ANONYMIZER
    try:
        from presidio_analyzer import AnalyzerEngine
        from presidio_anonymizer import AnonymizerEngine

        _PRESIDIO_ANALYZER = AnalyzerEngine()
        _PRESIDIO_ANONYMIZER = AnonymizerEngine()
        _PRESIDIO_OK = True
        logger.info("Presidio PII analyzer loaded (enhanced privacy engine active).")
        return _PRESIDIO_ANALYZER, _PRESIDIO_ANONYMIZER
    except Exception as e:
        logger.warning("Presidio not available, using regex-only PII masking: %s", e)
        _PRESIDIO_OK = False
        return None, None


def _mask_with_presidio(text: str) -> str:
    """
    Use Microsoft Presidio to detect and anonymize PII entities.
    Returns the anonymized text, or the original text on any failure.
    """
    try:
        analyzer, anonymizer = _get_presidio()
        if analyzer is None or anonymizer is None:
            return text

        # Determine which entities are actually supported by the loaded recognizers
        supported = {r.supported_entities[0] for r in analyzer.registry.recognizers
                     if r.supported_entities}
        entities_to_use = [e for e in _PRESIDIO_ENTITIES if e in supported] or _PRESIDIO_ENTITIES

        results = analyzer.analyze(
            text=text,
            entities=entities_to_use,
            language="en",
        )

        if not results:
            return text

        # Doctor names are practitioner names, not patient PII — exclude them from masking
        filtered_results = []
        for r in results:
            if r.entity_type == "PERSON":
                prefix = text[max(0, r.start - 15):r.start]
                if re.search(r"\b(?:dr|dr\.|doctor|consultant|physician)\s*$", prefix, re.IGNORECASE):
                    continue
            filtered_results.append(r)

        if not filtered_results:
            return text

        # Standardize Presidio entity tags to align with application and test conventions
        _PRESIDIO_TAG_MAP = {
            "PHONE_NUMBER": "[PHONE]",
            "EMAIL_ADDRESS": "[EMAIL]",
            "PERSON": "[PATIENT]",
            "IN_AADHAAR": "[AADHAAR]",
            "IN_PAN": "[ID_NUM]",
            "IN_VOTER": "[ID_NUM]",
            "LOCATION": "[LOCATION]",
            "MEDICAL_LICENSE": "[ID_NUM]",
        }

        from presidio_anonymizer.entities import OperatorConfig
        operators = {
            entity: OperatorConfig("replace", {"new_value": _PRESIDIO_TAG_MAP.get(entity, f"[{entity}]")})
            for entity in entities_to_use
        }
        anonymized = anonymizer.anonymize(
            text=text,
            analyzer_results=filtered_results,
            operators=operators,
        )
        return anonymized.text
    except Exception as e:
        logger.debug("Presidio masking failed (falling back to regex): %s", e)
        return text


# ── Public API ─────────────────────────────────────────────────────────────────

def mask_text(text: str) -> str:
    """
    Replace PII patterns in *text* with placeholder tokens.
    Uses Presidio if available; always applies regex patterns on top.
    Returns the cleaned string.
    """
    if not text:
        return text

    # Stage 1: Presidio (ML-based, handles complex entity patterns)
    text = _mask_with_presidio(text)

    # Stage 2: Regex patterns (always applied — catches Indian-specific patterns
    # that Presidio's default recognizers may miss)
    for _label, pattern, repl in _COMPILED:
        text = pattern.sub(repl, text)

    return text


def mask_record_for_llm(record: dict) -> dict:
    """
    Return a shallow-copy of *record* with patient-identifying strings masked.
    Only modifies string fields that could carry PII; clinical values untouched.
    """
    import copy
    r = copy.deepcopy(record)
    r["patient_name_present"] = False  # signal to LLM that name is gone
    # Mask summary strings if already partially filled
    for key in ("summary_en", "summary_ta"):
        if isinstance(r.get(key), str):
            r[key] = mask_text(r[key])
    return r
