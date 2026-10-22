"""
routers/abha.py — Mock ABHA link and import endpoints.
Every response includes mock:true and a DEMO ONLY banner.
Never claims real ABHA connection.
"""
from __future__ import annotations

import re
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.repositories import profiles_repo
from app.schemas import AbhaImportResponse, AbhaLinkRequest, AbhaLinkResponse

router = APIRouter()

MOCK_BANNER = "DEMO ONLY — no real ABHA connection is made."
MOCK_DISCLAIMER = "This is a mock integration for demonstration purposes only."


def _validate_abha_format(abha_number: str) -> bool:
    """Loosely validate 14-digit ABHA number (digits only or XX-XXXX-XXXX-XXXX)."""
    cleaned = re.sub(r"[-\s]", "", abha_number)
    return bool(re.match(r"^\d{14}$", cleaned))


@router.post(
    "/profiles/{profile_id}/abha/link",
    response_model=AbhaLinkResponse,
    summary="[MOCK] Link an ABHA ID to a profile",
)
def link_abha(
    profile_id: str,
    payload: AbhaLinkRequest,
    db: Session = Depends(get_db),
):
    profile = profiles_repo.get_profile(db, profile_id)
    if not profile:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "PROFILE_NOT_FOUND", "message": f"Profile '{profile_id}' not found."}}
        )

    val = (payload.abha_id or payload.abha_number or "").strip()
    if not _validate_abha_format(val):
        raise HTTPException(
            status_code=422,
            detail={"error": {
                "code": "INVALID_ABHA_FORMAT",
                "message": "ABHA number must be 14 digits (e.g. 12345678901234 or 12-3456-7890-1234)."
            }}
        )

    updated = profiles_repo.update_profile_abha(db, profile_id, val)
    return AbhaLinkResponse(
        mock=True,
        profile_id=profile_id,
        abha_id=val,
        status="linked",
        linked=True,
        banner=MOCK_BANNER,
        disclaimer=MOCK_DISCLAIMER,
    )


@router.post(
    "/profiles/{profile_id}/abha/import",
    response_model=AbhaImportResponse,
    summary="[MOCK] Import records from ABHA for a profile",
)
def import_abha(
    profile_id: str,
    db: Session = Depends(get_db),
):
    profile = profiles_repo.get_profile(db, profile_id)
    if not profile:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "PROFILE_NOT_FOUND", "message": f"Profile '{profile_id}' not found."}}
        )

    # Mock response: no real import
    mock_records = [
        {
            "record_id": str(uuid.uuid4()),
            "doc_type": "lab_report",
            "doc_date": "2024-03-15",
            "source": "abha_mock",
            "note": "Mock record imported from ABHA (demo only)",
        }
    ]

    return AbhaImportResponse(
        mock=True,
        profile_id=profile_id,
        records_imported=len(mock_records),
        imported_record_ids=[r["record_id"] for r in mock_records],
        banner=MOCK_BANNER,
        records=mock_records,
    )
