"""
db.py — SQLAlchemy engine, session factory, and startup helpers.
Uses WAL mode, FK enforcement, and busy timeout for SQLite.
Postgres-portable: no SQLite-specific types used in models.
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

logger = logging.getLogger(__name__)


def _apply_sqlite_pragmas(dbapi_conn, _connection_record):
    """Apply performance and correctness pragmas for SQLite."""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    try:
        cursor.execute("PRAGMA journal_mode=WAL")
    except Exception:
        pass
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()


def _build_engine():
    settings = get_settings()
    url = settings.database_url
    connect_args = {}
    engine_kwargs = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
        if url in ("sqlite://", "sqlite:///:memory:", "sqlite:///"):
            from sqlalchemy.pool import StaticPool
            engine_kwargs["poolclass"] = StaticPool
    engine = create_engine(
        url,
        connect_args=connect_args,
        **engine_kwargs,
    )
    if url.startswith("sqlite"):
        event.listen(engine, "connect", _apply_sqlite_pragmas)
    return engine



engine = _build_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: yields a DB session, always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def db_session():
    """Context-manager session for use in scripts/services outside FastAPI."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db():
    """Create all tables (idempotent). Called at startup."""
    from app import models  # noqa: F401 — ensure models are registered
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created / verified.")
