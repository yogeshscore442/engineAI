"""
routers/records.py — Record upload, get, file download, and PUT confirm endpoints.
Thin: parse request → call service → return response.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Record
from app.repositories import records_repo
from app.repositories import medicines_repo, tests_repo
from app.schemas import RecordOut, RecordUpdate, UploadResponse, MedicineOut, TestOut, ErrorResponse
from app.services import ai_client as ai_module
from app.services.files import validate_and_read_upload, get_file_path, get_content_type
from app.services.pipeline import run_upload_pipeline, run_confirm_pipeline, MedicalDocumentRejectionError
from app.services.privacy import get_request_id, log_upload, log_record_event

router = APIRouter()


def _record_to_out(record: Record, db: Session) -> RecordOut:
    """Convert ORM Record to RecordOut schema, parsing record_json."""
    try:
        rj = json.loads(record.record_json) if isinstance(record.record_json, str) else record.record_json
    except Exception:
        rj = {}

    meds = medicines_repo.get_medicines_by_record(db, record.record_id)
    tests = tests_repo.get_tests_by_record(db, record.record_id)

    return RecordOut(
        record_id=record.record_id,
        profile_id=record.profile_id,
        doc_type=record.doc_type,
        doc_date=record.doc_date,
        status=record.status,
        source=record.source,
        language=record.language,
        needs_review=rj.get("needs_review") if (isinstance(rj, dict) and rj.get("needs_review")) else record.needs_review,
        headline=record.headline,
        schema_version=record.schema_version,
        record_json=rj,
        record=rj,
        medicines=[MedicineOut.model_validate(m) for m in meds],
        tests=[TestOut.model_validate(t) for t in tests],
        created_at=record.created_at,
        confirmed_at=record.confirmed_at,
    )


# ---------------------------------------------------------------------------
# POST /api/profiles/{profile_id}/records  — Upload
# ---------------------------------------------------------------------------
@router.post(
    "/profiles/{profile_id}/records",
    response_model=UploadResponse,
    status_code=201,
    summary="Upload a medical document for a profile",
)
async def upload_record(
    profile_id: str,
    file: UploadFile = File(...),
    lang: str = Form("en"),
    db: Session = Depends(get_db),
):
    from app.repositories.profiles_repo import profile_exists
    request_id = get_request_id()

    if not profile_exists(db, profile_id):
        raise HTTPException(status_code=404, detail={"error": {"code": "PROFILE_NOT_FOUND", "message": "Profile not found."}})

    # Validate and read file
    file_bytes, ext, sha256 = await validate_and_read_upload(file)
    log_upload(request_id, profile_id, ext, len(file_bytes))

    ai = ai_module.get_cached_ai_client()
    filename_hint = file.filename or ""

    try:
        record = await run_upload_pipeline(
            db=db,
            profile_id=profile_id,
            file_bytes=file_bytes,
            ext=ext,
            sha256=sha256,
            filename_hint=filename_hint,
            lang=lang,
            ai_client=ai,
            request_id=request_id,
        )
    except MedicalDocumentRejectionError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "reason_codes": exc.reason_codes,
                    "status": "REJECTED",
                }
            },
        )

    log_record_event(request_id, record.record_id, "uploaded")
    record_out = _record_to_out(record, db)
    return UploadResponse(record_id=record.record_id, record=record_out, status=record.status)


# ---------------------------------------------------------------------------
# GET /api/records/{record_id}
# ---------------------------------------------------------------------------
@router.get(
    "/records/{record_id}",
    response_model=RecordOut,
    summary="Get a record by ID",
)
def get_record(record_id: str, db: Session = Depends(get_db)):
    record = records_repo.get_record(db, record_id)
    if not record:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "RECORD_NOT_FOUND", "message": f"Record '{record_id}' not found."}}
        )
    return _record_to_out(record, db)


# ---------------------------------------------------------------------------
# GET /api/records/{record_id}/file
# ---------------------------------------------------------------------------
@router.get(
    "/records/{record_id}/file",
    summary="Download the original uploaded file",
)
def get_record_file(record_id: str, db: Session = Depends(get_db)):
    record = records_repo.get_record(db, record_id)
    if not record:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "RECORD_NOT_FOUND", "message": f"Record '{record_id}' not found."}}
        )
    if not record.file_path:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "FILE_NOT_FOUND", "message": "No file associated with this record."}}
        )

    file_path = get_file_path(record.file_path)
    if not file_path:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "FILE_NOT_FOUND", "message": "File not found on server."}}
        )

    ext = Path(record.file_path).suffix.lower()
    content_type = get_content_type(ext)
    return FileResponse(path=str(file_path), media_type=content_type)


# ---------------------------------------------------------------------------
# PUT /api/records/{record_id}  — User confirm / correction
# ---------------------------------------------------------------------------
@router.put(
    "/records/{record_id}",
    response_model=RecordOut,
    summary="Confirm or correct a record (user edits)",
)
def confirm_record(
    record_id: str,
    payload: RecordUpdate,
    db: Session = Depends(get_db),
):
    request_id = get_request_id()
    record = records_repo.get_record(db, record_id)
    if not record:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "RECORD_NOT_FOUND", "message": f"Record '{record_id}' not found."}}
        )

    try:
        updated = run_confirm_pipeline(db, record, payload.record_json, request_id=request_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={"error": {"code": "VALIDATION_ERROR", "message": str(exc)}}
        )

    log_record_event(request_id, record_id, "confirmed")
    return _record_to_out(updated, db)
