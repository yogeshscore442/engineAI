"""
routers/fhir.py — FHIR R4 Bundle export endpoint.
GET /api/records/{record_id}/fhir
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.repositories import profiles_repo, records_repo
from app.services.fhir import build_fhir_bundle

router = APIRouter()


@router.get(
    "/records/{record_id}/fhir",
    summary="Export a record as a FHIR R4 Bundle",
    response_description="FHIR R4 Bundle (type=collection). FHIR R4-style, ABDM-ready. Not ABDM certified.",
)
def get_fhir_bundle(record_id: str, db: Session = Depends(get_db)):
    record = records_repo.get_record(db, record_id)
    if not record:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "RECORD_NOT_FOUND", "message": f"Record '{record_id}' not found."}}
        )

    profile = profiles_repo.get_profile(db, record.profile_id)
    if not profile:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "PROFILE_NOT_FOUND", "message": "Profile not found."}}
        )

    bundle = build_fhir_bundle(profile, record)
    return bundle
