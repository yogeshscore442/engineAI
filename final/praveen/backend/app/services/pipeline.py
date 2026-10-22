"""
services/pipeline.py — Explicit pipeline stages for the upload→confirm lifecycle.
Each stage is a named, unit-testable function.
Stage logs only metadata (stage name, timing). Never logs content.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models import Record
from app.repositories import medicines_repo, records_repo, tests_repo
from app.services import normalizer, validators
from app.services.files import delete_file, save_file
from app.services.privacy import log_stage
from app.integration import DISCLAIMER
from app.services.summaries import refresh_summaries
import uuid

logger = logging.getLogger(__name__)

FRIENDLY_AI_ERROR = (
    "We couldn't read this document. Please retry or enter the details manually."
)


class MedicalDocumentRejectionError(Exception):
    """Raised when an uploaded document is rejected by medical validation."""
    def __init__(self, code: str, message: str, reason_codes: list[str]):
        self.code = code
        self.message = message
        self.reason_codes = reason_codes
        super().__init__(message)


def is_possible_medical(ai_result: dict) -> bool:
    """
    Check if this document has medical evidence or needs manual review.
    Documents with layout structure, printed headings, or handwriting signals
    must NOT be classified as non-medical solely because OCR text was sparse.
    """
    reason_codes = ai_result.get("reason_codes") or []
    return bool(
        str(ai_result.get("document_type", "")).upper() in (
            "POSSIBLE_MEDICAL_DOCUMENT_NEEDS_REVIEW",
            "UNKNOWN_REQUIRES_REVIEW",
            "PRESCRIPTION",
            "CLINICAL_NOTE",
            "LAB_REPORT",
            "DISCHARGE_SUMMARY",
            "DIAGNOSTIC_REPORT",
            "MEDICAL_REFERENCE_CHART",
            "HOSPITAL_FORM",
            "MEDICAL_CERTIFICATE",
            "MEDICINE_OR_PRODUCT_IMAGE",
            "OTHER_MEDICAL_DOCUMENT",
        )
        or str(ai_result.get("doc_type", "")).lower() in (
            "unknown_requires_review",
            "clinical_note",
            "prescription",
            "lab_report",
            "discharge_summary",
            "diagnostic_report",
            "medical_reference_chart",
            "hospital_form",
            "medical_certificate",
            "medicine_or_product_image",
            "other_medical_document",
        )
        or str(ai_result.get("status", "")).upper() in ("NEEDS_REVIEW", "ACCEPTED")
        or str(ai_result.get("document_state", "")).upper() in ("NEEDS_REVIEW", "ACCEPTED")
        or "POSSIBLE_MEDICAL_DOCUMENT_NEEDS_REVIEW" in reason_codes
        or "UNKNOWN_REQUIRES_REVIEW" in reason_codes
        or "HANDWRITTEN_OR_LOW_CONTRAST_REQUIRES_MANUAL_VERIFICATION" in reason_codes
        or "MEDICAL_REFERENCE_CHART_DETECTED" in reason_codes
        or "HOSPITAL_CLINICAL_FORM_DETECTED" in reason_codes
        or "HOMEOPATHIC_DOCUMENT_DETECTED" in reason_codes
    )


async def run_upload_pipeline(
    db: Session,
    profile_id: str,
    file_bytes: bytes,
    ext: str,
    sha256: str,
    filename_hint: str,
    lang: str,
    ai_client,
    request_id: str = "",
) -> Record:
    """
    Full upload pipeline:
    Stage 1: Duplicate detection (sha256 per profile)
    Stage 2: Store file (atomic)
    Stage 3: AI extraction (threadpool, timeout)
    Stage 4: Validate & normalize
    Stage 5: Persist draft record
    """
    # Stage 1: Duplicate detection
    with log_stage("duplicate_check", request_id):
        disable_cache = os.getenv("DISABLE_CACHE", "").lower() in ("true", "1")
        if not disable_cache:
            existing = records_repo.find_by_sha256(db, profile_id, sha256)
            if existing and existing.status not in ("error", "PROCESSING_FAILED") and existing.doc_type not in ("unknown", None):
                logger.info("[%s] Duplicate upload detected, returning existing record", request_id)
                return existing

    # Stage 2: Store file
    file_path_str: Optional[str] = None
    with log_stage("store_file", request_id):
        _, file_path_str = save_file(file_bytes, ext)

    # Stage 3: AI extraction (release DB session before blocking call)
    ai_result: dict[str, Any] = {}
    ai_error: Optional[str] = None
    with log_stage("ai_extract", request_id):
        try:
            ai_result = await ai_client.extract(file_bytes, filename_hint=filename_hint, lang=lang)
        except Exception as exc:
            ai_error = FRIENDLY_AI_ERROR
            logger.warning("[%s] AI extraction error: %s", request_id, type(exc).__name__)
            # Clean up file on AI failure
            if file_path_str:
                try:
                    delete_file(file_path_str)
                except Exception:
                    logger.warning("[%s] Could not clean up file after AI failure", request_id)
                file_path_str = None

    if not isinstance(ai_result, dict):
        ai_result = {}
        ai_error = FRIENDLY_AI_ERROR

    # ── Strict Medical Validation Gatekeeper ──────────────────────────────
    reason_codes = ai_result.get("reason_codes") or []
    is_poss_med = is_possible_medical(ai_result)

    # Non-medical content (selfies, pets, landscapes, receipts, blank images)
    # must be rejected immediately without persisting to disk.
    # Note: INSUFFICIENT_TEXT_CONTENT is a diagnostic signal, NOT proof of non-medical document.
    is_non_medical = not is_poss_med and (
        str(ai_result.get("document_type", "")).upper() == "NON_MEDICAL"
        or str(ai_result.get("doc_type", "")).lower() == "non_medical"
        or any(
            r in reason_codes
            for r in [
                "NON_MEDICAL_DOCUMENT",
                "DETECTED_NON_MEDICAL_CONTENT",
                "BLANK_OR_EMPTY_PAGE",
                "NO_RECOGNIZABLE_MEDICAL_EVIDENCE",
                "UNSUPPORTED_FILE_TYPE",
            ]
        )
    )

    if is_non_medical:
        # Immediately remove file from disk — never persist rejected non-medical uploads
        if file_path_str:
            try:
                delete_file(file_path_str)
            except Exception:
                logger.warning("[%s] Could not clean up file after rejection", request_id)
            file_path_str = None

        if not reason_codes:
            reason_codes = ["NON_MEDICAL_DOCUMENT"]
        err_obj = ai_result.get("error") if isinstance(ai_result.get("error"), dict) else {}
        code = "NON_MEDICAL_DOCUMENT" if "NON_MEDICAL_DOCUMENT" in reason_codes else (err_obj.get("code") or reason_codes[0])
        msg = err_obj.get("message") or (
            "The uploaded file does not appear to be a supported medical document. "
            "Please upload a valid laboratory report, prescription, or diagnostic report."
        )
        logger.info("[%s] Document rejected: code=%s reasons=%s", request_id, code, reason_codes)
        raise MedicalDocumentRejectionError(code=code, message=msg, reason_codes=reason_codes)

    if not ai_error:
        valid, _ = validators.validate_record_json(ai_result)
        if not valid:
            ai_error = FRIENDLY_AI_ERROR
    if ai_result.get("error"):
        ai_error = FRIENDLY_AI_ERROR

    if ai_error:
        # Return a draft record with error state (no file)
        record = records_repo.create_record(
            db,
            profile_id=profile_id,
            doc_type="unknown",
            doc_date=None,
            status="draft",
            file_path=file_path_str,
            file_sha256=None,  # allow retrying a failed extraction
            record_json=json.dumps({"error": {"code": "EXTRACTION_FAILED", "message": ai_error}, "disclaimer": DISCLAIMER}),
            source=ai_result.get("source", "ai"),
            language=lang,
            needs_review=True,
            headline="Document could not be read — please enter manually.",
        )
        return record

    # Stage 4: Validate & normalize
    with log_stage("validate_normalize", request_id):
        normalized = normalizer.normalize_record_json(ai_result)
        normalized["record_id"] = str(uuid.uuid4())
        normalized["disclaimer"] = DISCLAIMER
        refresh_summaries(normalized)
        doc_type = normalized.get("doc_type") or normalized.get("type") or "lab_report"
        normalized["doc_type"] = doc_type
        doc_date = normalized.get("doc_date")
        needs_review = validators.compute_needs_review(normalized)
        headline = validators.generate_headline(normalized, doc_type)
        source = normalized.get("source", "mock")
        language = normalized.get("language", lang)
        normalized["schema_version"] = 1

    # Stage 5: Persist draft record
    with log_stage("persist_draft", request_id):
        record = records_repo.create_record(
            db,
            record_id=normalized["record_id"],
            profile_id=profile_id,
            doc_type=doc_type,
            doc_date=doc_date,
            status="draft",
            file_path=file_path_str,
            file_sha256=sha256,
            record_json=json.dumps(normalized),
            schema_version=1,
            source=source,
            language=language,
            needs_review=needs_review,
            headline=headline,
        )

    return record


def run_confirm_pipeline(
    db: Session,
    record: Record,
    new_record_json: dict,
    request_id: str = "",
) -> Record:
    """
    Confirmation pipeline (PUT):
    Stage 6: Validate confirmed JSON
    Stage 7: Re-normalize child rows (idempotent: delete + reinsert in one transaction)
    """
    # Stage 6: Validate
    with log_stage("validate_confirmed", request_id):
        ok, err = validators.validate_record_json(new_record_json)
        if not ok:
            raise ValueError(err)
        normalized = normalizer.normalize_record_json(new_record_json)
        normalized["record_id"] = record.record_id
        normalized["disclaimer"] = DISCLAIMER
        refresh_summaries(normalized)
        doc_type = normalized.get("doc_type", record.doc_type)
        headline = validators.generate_headline(normalized, doc_type)

    # Stage 7: Re-normalize child rows (atomic)
    with log_stage("renormalize_children", request_id):
        medicines_repo.delete_medicines_by_record(db, record.record_id)
        tests_repo.delete_tests_by_record(db, record.record_id)

        meds_data = normalized.get("medicines", [])
        tests_data = normalized.get("tests", [])
        if isinstance(meds_data, list):
            for m in meds_data:
                if isinstance(m, dict):
                    m["user_confirmed"] = True
                    if m.get("verification_state") in ("UNVERIFIED_CANDIDATE", "REQUIRES_HUMAN_REVIEW", "UNVERIFIED", None):
                        m["verification_state"] = "VERIFIED_BY_USER"
            medicines_repo.bulk_insert_medicines(db, record.record_id, record.profile_id, meds_data)
        if isinstance(tests_data, list):
            for t in tests_data:
                if isinstance(t, dict):
                    t["user_confirmed"] = True
            tests_repo.bulk_insert_tests(db, record.record_id, record.profile_id, tests_data)

        updated = records_repo.confirm_record(
            db, record.record_id, normalized, headline=headline
        )

    return updated
