"""
Pydantic contract models for AI Health Copilot.
Maintains strict backward compatibility with existing consumers while
providing enriched Responsible AI metadata, provenance, and rejection outcomes.
"""
from __future__ import annotations

import re
import uuid
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator, model_validator

# ── Fixed disclaimer (identical at every layer) ────────────────────────────────
DISCLAIMER = (
    "This is AI-generated information to help you understand your records. "
    "It is not a diagnosis or medical advice. Please consult your doctor."
)

# ── Type aliases ───────────────────────────────────────────────────────────────
FlagValue = Literal["LOW", "NORMAL", "HIGH", "UNKNOWN"]
DocType = Literal[
    "prescription", "lab_report", "medical_record", "discharge_summary",
    "medical_note", "tablet_or_medicine_image", "unrelated_photograph",
    "unknown_document", "corrupted_file", "unreadable_document",
    "diagnostic_report", "clinical_note", "possible_medical_document_needs_review",
    "unknown_requires_review", "non_medical", "unknown",
    "hospital_form", "medical_certificate", "medical_reference_chart",
    "medicine_or_product_image", "other_medical_document", "unrelated_image",
]
StatusOutcome = Literal[
    "VALIDATING", "PROCESSING", "ACCEPTED", "NEEDS_REVIEW",
    "REJECTED", "UNREADABLE", "PROCESSING_FAILED", "draft", "confirmed"
]
Language = Literal["en", "ta", "hi", "mixed"]
FoodInstruction = Literal["before_food", "after_food"]
ScheduleSlot = Literal["morning", "afternoon", "night"]
VerificationState = Literal[
    "present_verified", "extracted_unverified", "missing",
    "illegible", "conflicting", "not_applicable", "requires_human_review",
    "EXTRACTED", "VERIFIED", "UNVERIFIED", "MISSING",
    "UNREADABLE", "CONFLICTING", "NEEDS_REVIEW", "NOT_APPLICABLE",
]

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# ── Sub-models ─────────────────────────────────────────────────────────────────

class MedicineRecord(BaseModel):
    """One medicine entry extracted from a prescription or discharge summary."""
    name_raw: str
    generic: Optional[str] = None
    brand_name: Optional[str] = None
    strength: Optional[str] = None
    formulation: Optional[str] = None           # tablet | capsule | syrup | injection | ointment | drops
    route: Optional[str] = "oral"              # oral | parenteral | topical | inhalation
    dose: Optional[str] = None                 # e.g. "1 tab", "5 ml"
    frequency: Optional[str] = None            # e.g. "OD", "BD", "TDS", "1-0-1"
    schedule_raw: Optional[str] = None
    schedule_parsed: List[ScheduleSlot] = Field(default_factory=list)
    food_instruction: Optional[FoodInstruction] = None
    timing_instructions: Optional[str] = None
    duration_days: Optional[int] = None
    quantity: Optional[int] = None
    refill_instructions: Optional[str] = None
    confidence: float = Field(default=0.85, ge=0.0, le=1.0)
    bbox: Optional[List[float]] = None
    source_text: Optional[str] = None
    source_page: Optional[int] = 1
    verification_state: VerificationState = "extracted_unverified"
    review_candidates: List[str] = Field(default_factory=list)
    provenance: Optional[Dict[str, Any]] = None

    @field_validator("schedule_parsed", mode="before")
    @classmethod
    def _coerce_schedule_parsed(cls, v: Any) -> list:
        if not v or not isinstance(v, list):
            return []
        slot_map = {0: "morning", 1: "afternoon", 2: "night"}
        if all(isinstance(x, (int, str)) and str(x) in ("0", "1") for x in v) and len(v) == 3:
            return [slot_map[i] for i, val in enumerate(v) if str(val) == "1"]
        valid = {"morning", "afternoon", "night"}
        return [str(x).lower() for x in v if str(x).lower() in valid]

    @field_validator("bbox")
    @classmethod
    def _bbox_len(cls, v: Optional[List[float]]) -> Optional[List[float]]:
        if v is not None and len(v) != 4:
            raise ValueError("bbox must have exactly 4 elements [x, y, w, h]")
        return v

    @field_validator("duration_days")
    @classmethod
    def _positive_days(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v <= 0:
            raise ValueError("duration_days must be positive")
        return v


class TestRecord(BaseModel):
    """One lab / diagnostic test result."""
    __test__ = False  # Prevent pytest from treating this model as a test suite
    name: str
    loinc: Optional[str] = None
    value: Optional[float] = None
    value_text: Optional[str] = None          # for qualitative or impression findings
    unit: Optional[str] = None
    lab_reference_interval: Optional[str] = None  # Verbatim printed reference range from lab report
    ref_low: Optional[float] = None
    ref_high: Optional[float] = None
    lab_flag: Optional[str] = None            # Flag printed directly on lab report (e.g. H, L, *)
    flag: FlagValue = "UNKNOWN"               # Deterministically validated flag
    explanation_en: Optional[str] = None
    explanation_ta: Optional[str] = None
    explanation_hi: Optional[str] = None
    confidence: float = Field(default=0.85, ge=0.0, le=1.0)
    bbox: Optional[List[float]] = None
    source_text: Optional[str] = None
    source_page: Optional[int] = 1
    verification_state: VerificationState = "extracted_unverified"
    provenance: Optional[Dict[str, Any]] = None

    @field_validator("bbox")
    @classmethod
    def _bbox_len(cls, v: Optional[List[float]]) -> Optional[List[float]]:
        if v is not None and len(v) != 4:
            raise ValueError("bbox must have exactly 4 elements [x, y, w, h]")
        return v


class DiagnosisRecord(BaseModel):
    """A diagnosis text mention extracted from the document."""
    text: str
    icd10: Optional[str] = None
    confidence: float = Field(default=0.80, ge=0.0, le=1.0)
    source_text: Optional[str] = None
    provenance: Optional[Dict[str, Any]] = None


class ErrorRecord(BaseModel):
    """Structured error — always present on failure, null on success."""
    code: str
    message: str


class HealthRecord(BaseModel):
    """Root contract model. All fields match the shared contract and provide Responsible AI metadata."""
    record_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    doc_type: DocType = "lab_report"
    document_type: str = "lab_report"
    status: StatusOutcome = "ACCEPTED"
    document_state: str = "ACCEPTED"
    accepted: bool = True
    reason_codes: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    quality_assessment: Optional[Dict[str, Any]] = None
    field_provenance: Optional[Dict[str, Any]] = None
    extracted_data: Optional[Dict[str, Any]] = None
    ruleset_version: str = "2.1.0"
    model_metadata: Optional[Dict[str, Any]] = None

    doc_date: Optional[str] = None
    collection_date: Optional[str] = None
    follow_up_date: Optional[str] = None
    language: Language = "en"
    patient_name: Optional[str] = None
    patient_name_present: bool = False
    prescriber_info: Optional[Union[str, Dict[str, Any]]] = None
    ocr_text: Optional[str] = None
    allergies: List[str] = Field(default_factory=list)
    medicines: List[MedicineRecord] = Field(default_factory=list)
    tests: List[TestRecord] = Field(default_factory=list)
    diagnoses: List[DiagnosisRecord] = Field(default_factory=list)
    summary_en: Optional[str] = None
    summary_ta: Optional[str] = None
    summary_hi: Optional[str] = None
    safety_alerts: List[Dict[str, Any]] = Field(default_factory=list)
    cost_savings: Optional[Dict[str, Any]] = None
    needs_review: List[str] = Field(default_factory=list)
    confidence_breakdown: Optional[Dict[str, Any]] = None
    vitals: Optional[Dict[str, Any]] = None
    printed_sections: Optional[Dict[str, Any]] = None
    handwritten_sections: Optional[Dict[str, Any]] = None
    clinical_notes: Optional[List[str]] = None
    disclaimer: str = DISCLAIMER
    error: Optional[ErrorRecord] = None

    @field_validator("doc_date", "collection_date", "follow_up_date", mode="before")
    @classmethod
    def _validate_date(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        if not _DATE_RE.match(str(v)):
            raise ValueError(f"Date must be YYYY-MM-DD, got: {v!r}")
        return v

    @field_validator("disclaimer")
    @classmethod
    def _fixed_disclaimer(cls, v: str) -> str:
        return DISCLAIMER

    @model_validator(mode="after")
    def _sync_doc_types(self) -> "HealthRecord":
        # Keep doc_type and document_type synchronized
        if self.document_type and not self.doc_type:
            self.doc_type = self.document_type.lower()
        elif self.doc_type and not self.document_type:
            self.document_type = self.doc_type.upper()
        if self.status == "REJECTED":
            self.accepted = False
        self.document_state = self.status
        return self

    def mark_review(self, path: str) -> None:
        """Add a JSON-path string to needs_review (deduplicating)."""
        if path not in self.needs_review:
            self.needs_review.append(path)


# ── Error & Rejection Factories ───────────────────────────────────────────────

def make_error_record(
    code: str,
    message: str,
    doc_type: str = "lab_report",
    reason_codes: Optional[list[str]] = None,
) -> dict:
    """
    Return a contract-compliant dict representing an execution failure.
    Never raises — safe to call from any except block.
    """
    reasons = list(reason_codes or [code])
    is_rejected = code in (
        "LOAD_FAILED", "FILE_NOT_FOUND", "EMPTY_FILE",
        "BLANK_OR_EMPTY_PAGE", "UNSUPPORTED_OR_CORRUPT_FILE",
        "NON_MEDICAL_DOCUMENT", "UNSUPPORTED_TYPE", "CORRUPTED_FILE",
        "UNSUPPORTED_FILE_TYPE", "UNSUPPORTED_FORMAT"
    ) or any(r in (
        "FILE_NOT_FOUND", "EMPTY_FILE", "LOAD_FAILED", "NON_MEDICAL_DOCUMENT",
        "CORRUPTED_FILE", "UNSUPPORTED_FILE_TYPE", "UNSUPPORTED_OR_CORRUPT_FILE",
        "BLANK_OR_EMPTY_PAGE"
    ) for r in reasons)
    status = "REJECTED" if is_rejected else "PROCESSING_FAILED"
    return {
        "record_id": str(uuid.uuid4()),
        "status": status,
        "document_state": status,
        "doc_type": doc_type.lower(),
        "document_type": doc_type.upper(),
        "accepted": False,
        "reason_codes": reasons,
        "warnings": [],
        "quality_assessment": None,
        "field_provenance": None,
        "extracted_data": None,
        "ruleset_version": "2.1.0",
        "model_metadata": None,
        "doc_date": None,
        "collection_date": None,
        "follow_up_date": None,
        "language": "en",
        "patient_name": None,
        "patient_name_present": False,
        "prescriber_info": None,
        "ocr_text": None,
        "allergies": [],
        "medicines": [],
        "tests": [],
        "diagnoses": [],
        "summary_en": None,
        "summary_ta": None,
        "summary_hi": None,
        "safety_alerts": [],
        "cost_savings": None,
        "needs_review": ["all"],
        "disclaimer": DISCLAIMER,
        "error": {"code": code, "message": message},
    }


def make_rejected_record(
    reason_codes: list[str],
    message: str,
    quality: Optional[dict[str, Any]] = None,
    document_type: str = "NON_MEDICAL",
) -> dict:
    """
    Explicit rejection record for non-medical, blank, corrupt, or unsupported documents.
    Never fabricates clinical data or summaries.
    """
    codes = reason_codes or ["NON_MEDICAL_DOCUMENT"]
    return {
        "record_id": str(uuid.uuid4()),
        "status": "REJECTED",
        "document_state": "REJECTED",
        "doc_type": document_type.lower(),
        "document_type": document_type.upper(),
        "accepted": False,
        "reason_codes": codes,
        "warnings": [],
        "quality_assessment": quality,
        "field_provenance": None,
        "extracted_data": None,
        "ruleset_version": "2.1.0",
        "model_metadata": None,
        "doc_date": None,
        "collection_date": None,
        "follow_up_date": None,
        "language": "en",
        "patient_name": None,
        "patient_name_present": False,
        "prescriber_info": None,
        "ocr_text": None,
        "allergies": [],
        "medicines": [],
        "tests": [],
        "diagnoses": [],
        "summary_en": None,
        "summary_ta": None,
        "summary_hi": None,
        "safety_alerts": [],
        "cost_savings": None,
        "needs_review": [],
        "disclaimer": DISCLAIMER,
        "error": {
            "code": codes[0],
            "message": message,
        },
    }


def make_needs_review_record(
    reason_codes: list[str],
    message: str,
    document_type: str = "UNKNOWN_REQUIRES_REVIEW",
    doc_type: str = "unknown_requires_review",
    quality: Optional[dict[str, Any]] = None,
    ocr_text: Optional[str] = None,
    field_provenance: Optional[dict[str, Any]] = None,
    medicines: Optional[list[dict[str, Any]]] = None,
    tests: Optional[list[dict[str, Any]]] = None,
    diagnoses: Optional[list[dict[str, Any]]] = None,
    needs_review: Optional[list[str]] = None,
    extracted_data: Optional[dict[str, Any]] = None,
) -> dict:
    """
    Contract-compliant review record for ambiguous, handwritten,
    or low-confidence medical documents. Preserves candidate extractions
    for human review without silently discarding them.
    """
    codes = list(reason_codes) if reason_codes else ["UNKNOWN_REQUIRES_REVIEW"]
    meds_list = list(medicines) if medicines else []
    tests_list = list(tests) if tests else []
    diag_list = list(diagnoses) if diagnoses else []

    if needs_review is not None:
        computed_needs_review = list(needs_review)
    else:
        computed_needs_review = ["document_type"]
        if meds_list:
            computed_needs_review.extend([f"medicines[{i}]" for i in range(len(meds_list))])
        else:
            computed_needs_review.append("medicines")
        if tests_list:
            computed_needs_review.extend([f"tests[{i}]" for i in range(len(tests_list))])
        else:
            computed_needs_review.append("tests")

    return {
        "record_id": str(uuid.uuid4()),
        "status": "NEEDS_REVIEW",
        "document_state": "NEEDS_REVIEW",
        "doc_type": doc_type.lower(),
        "document_type": document_type.upper(),
        "accepted": False,
        "reason_codes": codes,
        "warnings": [
            "POSSIBLE_MEDICAL_DOCUMENT_DETECTED",
            "HANDWRITTEN_OR_LOW_CONTRAST_REQUIRES_MANUAL_VERIFICATION",
        ],
        "quality_assessment": quality,
        "field_provenance": field_provenance or {
            "extraction_engine": "layout_aware_deterministic",
            "is_handwritten": True,
        },
        "extracted_data": extracted_data,
        "ruleset_version": "2.1.0",
        "model_metadata": {
            "provider": "local_deterministic_pipeline",
            "model": "layout_ocr_engine_v2",
        },
        "doc_date": None,
        "collection_date": None,
        "follow_up_date": None,
        "language": "en",
        "patient_name": None,
        "patient_name_present": False,
        "prescriber_info": None,
        "ocr_text": ocr_text,
        "allergies": [],
        "medicines": meds_list,
        "tests": tests_list,
        "diagnoses": diag_list,
        "summary_en": message or "Medical document or handwritten prescription detected. Text could not be fully read automatically. Please verify or enter details manually.",
        "summary_ta": "சாத்தியமான மருத்துவ ஆவணம் அல்லது கையால் எழுதப்பட்ட மருந்துச் சீட்டு கண்டறியப்பட்டது. தயவுசெய்து கைமுறையாக சரிபார்க்கவும்.",
        "summary_hi": "चिकित्सा दस्तावेज़ या हस्तलिखित नुस्खा मिला। कृपया विवरण की मैन्युअल रूप से समीक्षा करें।",
        "safety_alerts": [],
        "cost_savings": None,
        "needs_review": computed_needs_review,
        "disclaimer": DISCLAIMER,
        "error": None,
    }

