"""
repositories/profiles_repo.py — All DB queries for Profile model.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.models import Profile


def get_profile(db: Session, profile_id: str) -> Optional[Profile]:
    return db.query(Profile).filter(Profile.profile_id == profile_id).first()


def get_all_profiles(db: Session) -> list[Profile]:
    return db.query(Profile).order_by(Profile.created_at.asc()).all()


def create_profile(db: Session, profile_id: str, name: str, relation: str = "self",
                   abha_id: Optional[str] = None) -> Profile:
    profile = Profile(profile_id=profile_id, name=name, relation=relation, abha_id=abha_id)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def update_profile_abha(db: Session, profile_id: str, abha_id: str) -> Optional[Profile]:
    profile = get_profile(db, profile_id)
    if not profile:
        return None
    profile.abha_id = abha_id
    profile.abha_linked_mock = True
    db.commit()
    db.refresh(profile)
    return profile


def delete_profile(db: Session, profile_id: str) -> bool:
    profile = get_profile(db, profile_id)
    if not profile:
        return False
    db.delete(profile)
    db.commit()
    return True


def profile_exists(db: Session, profile_id: str) -> bool:
    return db.query(Profile.profile_id).filter(Profile.profile_id == profile_id).first() is not None
