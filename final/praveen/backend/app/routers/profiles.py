"""
routers/profiles.py — Profile CRUD, timeline, trends, alerts, and delete endpoints.
"""
from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.repositories import profiles_repo, records_repo
from app.repositories.medicines_repo import get_medicines_by_profile
from app.schemas import (
    AlertsResponse,
    ProfileCreate,
    ProfileOut,
    TimelineItem,
    TimelineResponse,
    TrendsResponse,
)
from app.services.alerts import run_all_alerts
from app.services.files import delete_file
from app.services.privacy import get_request_id, log_record_event
from app.services.trends import get_trend_points

router = APIRouter()


# ---------------------------------------------------------------------------
# GET /api/profiles — List all profiles (P3)
# ---------------------------------------------------------------------------
@router.get("/profiles", response_model=list[ProfileOut], summary="List all profiles")
def list_profiles(db: Session = Depends(get_db)):
    return [ProfileOut.model_validate(p) for p in profiles_repo.get_all_profiles(db)]


# ---------------------------------------------------------------------------
# POST /api/profiles — Create profile (P3)
# ---------------------------------------------------------------------------
@router.post("/profiles", response_model=ProfileOut, status_code=201, summary="Create a profile")
def create_profile(payload: ProfileCreate, db: Session = Depends(get_db)):
    profile = profiles_repo.create_profile(
        db,
        profile_id=str(uuid.uuid4()),
        name=payload.name,
        relation=payload.relation,
        abha_id=payload.abha_id,
    )
    return ProfileOut.model_validate(profile)


# ---------------------------------------------------------------------------
# GET /api/profiles/{profile_id}
# ---------------------------------------------------------------------------
@router.get("/profiles/{profile_id}", response_model=ProfileOut, summary="Get a profile")
def get_profile(profile_id: str, db: Session = Depends(get_db)):
    profile = profiles_repo.get_profile(db, profile_id)
    if not profile:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "PROFILE_NOT_FOUND", "message": f"Profile '{profile_id}' not found."}}
        )
    return ProfileOut.model_validate(profile)


# ---------------------------------------------------------------------------
# GET /api/profiles/{profile_id}/timeline
# ---------------------------------------------------------------------------
@router.get(
    "/profiles/{profile_id}/timeline",
    response_model=TimelineResponse,
    summary="Get health timeline for a profile",
)
def get_timeline(profile_id: str, db: Session = Depends(get_db)):
    if not profiles_repo.profile_exists(db, profile_id):
        raise HTTPException(status_code=404, detail={"error": {"code": "PROFILE_NOT_FOUND", "message": "Profile not found."}})
    records = records_repo.get_records_by_profile(db, profile_id)
    items = []
    for r in records:
        try:
            rj = json.loads(r.record_json) if isinstance(r.record_json, str) else (r.record_json or {})
        except Exception:
            rj = {}
        items.append(
            TimelineItem(
                record_id=r.record_id,
                doc_type=r.doc_type,
                doc_date=r.doc_date,
                headline=r.headline,
                status=r.status,
                source=r.source,
                needs_review=r.needs_review,
                created_at=r.created_at,
                medicines=rj.get("medicines", []),
                tests=rj.get("tests", []),
            )
        )
    return TimelineResponse(profile_id=profile_id, items=items)


# ---------------------------------------------------------------------------
# GET /api/profiles/{profile_id}/trends?test=HbA1c
# ---------------------------------------------------------------------------
@router.get(
    "/profiles/{profile_id}/trends",
    response_model=TrendsResponse,
    summary="Get trend data for a specific test",
)
def get_trends(profile_id: str, test: str, db: Session = Depends(get_db)):
    if not profiles_repo.profile_exists(db, profile_id):
        raise HTTPException(status_code=404, detail={"error": {"code": "PROFILE_NOT_FOUND", "message": "Profile not found."}})
    points = get_trend_points(db, profile_id, test)
    units = {point.unit for point in points}
    unit = next(iter(units)) if len(units) == 1 else None
    return TrendsResponse(profile_id=profile_id, test=test, test_name=test, unit=unit, points=points)


# ---------------------------------------------------------------------------
# GET /api/profiles/{profile_id}/alerts
# ---------------------------------------------------------------------------
@router.get(
    "/profiles/{profile_id}/alerts",
    response_model=AlertsResponse,
    summary="Get health alerts for a profile",
)
def get_alerts(profile_id: str, db: Session = Depends(get_db)):
    if not profiles_repo.profile_exists(db, profile_id):
        raise HTTPException(status_code=404, detail={"error": {"code": "PROFILE_NOT_FOUND", "message": "Profile not found."}})
    alerts = run_all_alerts(db, profile_id)
    return AlertsResponse(profile_id=profile_id, alerts=alerts)


# ---------------------------------------------------------------------------
# DELETE /api/profiles/{profile_id}
# ---------------------------------------------------------------------------
@router.delete(
    "/profiles/{profile_id}",
    summary="Delete a profile and all its data (rows + files)",
)
def delete_profile(profile_id: str, db: Session = Depends(get_db)):
    request_id = get_request_id()
    profile = profiles_repo.get_profile(db, profile_id)
    if not profile:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "PROFILE_NOT_FOUND", "message": f"Profile '{profile_id}' not found."}}
        )

    # Collect file paths before DB delete
    records = records_repo.get_records_by_profile(db, profile_id)
    file_paths = [r.file_path for r in records if r.file_path]
    record_count = len(records)

    # Delete DB rows (cascade)
    profiles_repo.delete_profile(db, profile_id)

    # Delete files
    files_deleted = 0
    for fp in file_paths:
        if delete_file(fp):
            files_deleted += 1
        else:
            log_record_event(request_id, "[omitted]", "file_delete_failed")

    log_record_event(request_id, profile_id, "profile_deleted")
    return {
        "deleted": True,
        "profile_id": profile_id,
        "records_deleted": record_count,
        "files_deleted": files_deleted,
    }
