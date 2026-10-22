"""
routers/ask.py — P3: Grounded Q&A endpoint.
POST /api/profiles/{profile_id}/ask
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.repositories.profiles_repo import profile_exists
from app.schemas import AskRequest, AskResponse
from app.services.ask import answer_question

router = APIRouter()


@router.post(
    "/profiles/{profile_id}/ask",
    response_model=AskResponse,
    summary="Ask a health question grounded in your records",
)
def ask(
    profile_id: str,
    payload: AskRequest,
    db: Session = Depends(get_db),
):
    if not profile_exists(db, profile_id):
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "PROFILE_NOT_FOUND", "message": f"Profile '{profile_id}' not found."}}
        )
    return answer_question(db, profile_id, payload.question, lang=payload.lang)
