"""
schemas.py — Pydantic schemas that mirror the API contract exactly.
Never silently change field names or shapes vs the contract.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, AliasChoices
from app.integration import DISCLAIMER


# ---------------------------------------------------------------------------
# Shared / primitive
# ---------------------------------------------------------------------------
class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------
class ProfileCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=200)
    relation: str = Field(default="self", min_length=1, max_length=50)
    abha_id: Optional[str] = None


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    profile_id: str
    name: str
    relation: str
    abha_id: Optional[str] = None
    abha_linked_mock: bool = False
    created_at: datetime


# ---------------------------------------------------------------------------
# Medicine (within record)
# ---------------------------------------------------------------------------
class MedicineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name_raw: str
    generic: Optional[str] = None
    strength: Optional[str] = None
    schedule_raw: Optional[str] = None
    schedule_parsed: Optional[Any] = None
    duration_days: Optional[int] = None
    confidence: Optional[float] = None


# ---------------------------------------------------------------------------
# Test result (within record)
# ---------------------------------------------------------------------------
class TestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    name_canonical: Optional[str] = None
    loinc: Optional[str] = None
    value: Optional[float] = None
    unit: Optional[str] = None
    ref_low: Optional[float] = None
    ref_high: Optional[float] = None
    flag: Optional[str] = None        # H | L | N
    flag_verified: bool = False
    date: Optional[str] = None
    confidence: Optional[float] = None


# ---------------------------------------------------------------------------
# Record
# ---------------------------------------------------------------------------
class RecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    record_id: str
    profile_id: str
    doc_type: str
    doc_date: Optional[str] = None
    status: str                        # draft | confirmed
    source: str                        # ai | mock | abha_mock
    language: str = "en"
    needs_review: Any = False
    headline: Optional[str] = None
    schema_version: int = 1
    record_json: Any = None            # parsed JSON object (not raw string)
    record: Any = None                 # contract-compliant record object
    medicines: list[MedicineOut] = []
    tests: list[TestOut] = []
    created_at: datetime
    confirmed_at: Optional[datetime] = None
    disclaimer: str = DISCLAIMER


class RecordUpdate(BaseModel):
    """Payload for PUT /api/records/{id} (user-confirmed data)."""
    record_json: Any = Field(default=None, validation_alias=AliasChoices("record_json", "record"))
    status: str = "confirmed"


# ---------------------------------------------------------------------------
# Upload response
# ---------------------------------------------------------------------------
class UploadResponse(BaseModel):
    record_id: str
    record: RecordOut
    status: str = "draft"


# ---------------------------------------------------------------------------
# Timeline
# ---------------------------------------------------------------------------
class TimelineItem(BaseModel):
    record_id: str
    doc_type: str
    doc_date: Optional[str] = None
    headline: Optional[str] = None
    status: str
    source: str
    needs_review: bool = False
    created_at: datetime
    medicines: list[Any] = []
    tests: list[Any] = []


class TimelineResponse(BaseModel):
    profile_id: str
    items: list[TimelineItem]


# ---------------------------------------------------------------------------
# Trends
# ---------------------------------------------------------------------------
class TrendPoint(BaseModel):
    date: str
    value: float
    unit: Optional[str] = None
    record_id: str
    flag: Optional[str] = None


class TrendsResponse(BaseModel):
    profile_id: str
    test: Optional[str] = None
    test_name: Optional[str] = None
    unit: Optional[str] = None
    points: list[TrendPoint] = []


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------
class AlertItem(BaseModel):
    alert_type: str         # e.g. "duplicate_generic"
    type: Optional[str] = None
    generic: Optional[str] = None
    medicines: list[Any] = []
    severity: str = "info"  # info | warning
    message: str
    record_ids: list[str] = []
    disclaimer: str = "Informational only. Please confirm with your doctor."


class AlertsResponse(BaseModel):
    profile_id: str
    alerts: list[AlertItem]


# ---------------------------------------------------------------------------
# ABHA (mock)
# ---------------------------------------------------------------------------
class AbhaLinkRequest(BaseModel):
    abha_number: Optional[str] = None
    abha_id: Optional[str] = None


class AbhaLinkResponse(BaseModel):
    mock: bool = True
    profile_id: str
    abha_id: str
    status: str = "linked"
    linked: bool = True
    banner: str = "DEMO ONLY — no real ABHA connection is made."
    disclaimer: str = "This is a mock integration for demonstration purposes."


class AbhaImportResponse(BaseModel):
    mock: bool = True
    profile_id: str
    records_imported: int
    imported_record_ids: list[str] = []
    banner: str = "DEMO ONLY — no real ABHA connection is made."
    records: list[dict] = []


# ---------------------------------------------------------------------------
# Ask (P3)
# ---------------------------------------------------------------------------
class AskRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    question: str = Field(min_length=1, max_length=4000)
    lang: str = "en"


class AskSource(BaseModel):
    record_id: str
    doc_type: str
    doc_date: Optional[str] = None


class MedicalReference(BaseModel):
    title: str
    source: str                          # e.g., "MedlinePlus / NIH", "CDSCO", "WHO", "AIIMS"
    url: str                             # Authoritative HTTPS medical URL
    description: Optional[str] = None
    reference_type: str = "official_monograph"  # official_monograph | clinical_guideline | health_authority


class ProductCard(BaseModel):
    product_id: str
    product_name: str
    category: str                        # medical_device | healthcare_equipment | otc_product
    price_inr: Optional[float] = None
    price_display: Optional[str] = None
    retailer: str                        # e.g., "Apollo Pharmacy", "Tata 1mg", "Omron Official", "Accu-Chek"
    purchase_url: Optional[str] = None
    image_url: Optional[str] = None
    is_prescription_only: bool = False
    specifications: Optional[dict[str, Any]] = None
    comparison_notes: Optional[str] = None
    availability_status: str = "VERIFIED_AVAILABLE"  # VERIFIED_AVAILABLE | CHECK_RETAILER | OUT_OF_STOCK
    rating: Optional[float] = None


class AskResponse(BaseModel):
    answer: str
    intent_category: str = "MEDICAL_INFORMATION"  # MEDICAL_INFORMATION | MEDICINE_QUERY | PRODUCT_SHOPPING | PRODUCT_ALTERNATIVES | MEDICINE_SUBSTITUTION_REQUEST | GENERAL_CONVERSATIONAL
    medical_explanation: Optional[str] = None
    medical_references: list[MedicalReference] = Field(default_factory=list)
    product_recommendations: list[ProductCard] = Field(default_factory=list)
    product_alternatives: list[ProductCard] = Field(default_factory=list)
    safety_notes: list[str] = Field(default_factory=list)
    needs_clinician_review: bool = False
    sources: list[AskSource] = Field(default_factory=list)
    disclaimer: str = "Informational only, not medical advice. Consult your doctor."
    lang: str = "en"


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
class HealthResponse(BaseModel):
    status: str = "ok"
    api_version: str
    schema_version: int
    ai_mode: str                         # mock | real
    features: dict[str, bool]
    disclaimer: str = "FHIR R4-style, ABDM-ready structure. Not ABDM certified."
