"""
main.py — FastAPI application entry point.
- CORS for http://localhost:5173 (frontend)
- All routers registered under /api
- Global exception handlers (no 500 stack traces ever)
- Lifespan: init DB, seed default profile, load catalogs
"""
from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import get_settings
from app.db import init_db
from app.schemas import HealthResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("health_copilot")


# ---------------------------------------------------------------------------
# Rate limiter (upload endpoints)
# ---------------------------------------------------------------------------
settings = get_settings()
limiter = Limiter(key_func=get_remote_address, default_limits=[settings.upload_rate_limit])


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init DB, seed default profile, load catalog data."""
    logger.info("Starting Health Copilot backend...")
    init_db()
    _seed_default_profile()
    _load_catalogs()
    logger.info("Backend ready. Swagger UI at /docs")
    yield
    logger.info("Shutting down Health Copilot backend.")


def _seed_default_profile():
    """Seed default and demo profiles if they do not exist."""
    from app.db import db_session
    from app.repositories.profiles_repo import get_profile, create_profile
    try:
        with db_session() as db:
            for pid, name in [("default", "Default User"), ("demo-patient-001", "Demo Patient"), ("patient-002", "Priya Sharma")]:
                p = get_profile(db, pid)
                if not p:
                    create_profile(db, profile_id=pid, name=name, relation="self")
                    logger.info("Seeded profile: %s", pid)
    except Exception as exc:
        logger.warning("Could not seed profiles: %s", type(exc).__name__)


def _load_catalogs():
    """Load brands.csv (falls back to built-ins if not found)."""
    from pathlib import Path
    from app.catalog.brands_loader import load_brands
    from app.integration import AI_PROJECT_ROOT
    brands_csv = AI_PROJECT_ROOT / "ai_engine" / "brands.csv"
    load_brands(brands_csv if brands_csv.exists() else None)


# ---------------------------------------------------------------------------
# App creation
# ---------------------------------------------------------------------------
app = FastAPI(
    title="AI Health Copilot API",
    description=(
        "Backend API for the AI Health Copilot. Manages health records, "
        "FHIR R4 export, mock ABHA integration, and profile timelines.\n\n"
        "**Disclaimer**: FHIR R4-style, ABDM-ready structure. Not ABDM certified."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS — allow frontend origin (and development origins)
import os as _os
_cors_origins = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://localhost:8080",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
]
# Add production/deployed origins from ALLOWED_ORIGINS env var (comma-separated)
_extra_origins = _os.environ.get("ALLOWED_ORIGINS", "")
if _extra_origins:
    _cors_origins.extend([o.strip() for o in _extra_origins.split(",") if o.strip()])

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


# ---------------------------------------------------------------------------
# Global exception handlers — never expose stack traces
# ---------------------------------------------------------------------------
def _err(code: str, message: str, status_code: int) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.detail,
        )
    code_map = {
        400: "BAD_REQUEST",
        404: "NOT_FOUND",
        409: "CONFLICT",
        413: "FILE_TOO_LARGE",
        415: "UNSUPPORTED_MEDIA_TYPE",
        422: "VALIDATION_ERROR",
    }
    code = code_map.get(exc.status_code, "ERROR")
    msg = exc.detail if isinstance(exc.detail, str) else "An error occurred."
    return _err(code, msg, exc.status_code)


@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    if isinstance(exc, HTTPException) and isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.detail,
        )
    return _err("NOT_FOUND", f"The endpoint {request.url.path} was not found.", 404)



@app.exception_handler(405)
async def method_not_allowed_handler(request: Request, exc):
    return _err("METHOD_NOT_ALLOWED", "Method not allowed.", 405)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc):
    try:
        detail = exc.errors()[0].get("msg", "Validation error") if hasattr(exc, "errors") else str(exc)
    except Exception:
        detail = "Validation error"
    return _err("VALIDATION_ERROR", str(detail), 422)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception on %s: %s", request.url.path, type(exc).__name__)
    return _err(
        "INTERNAL_ERROR",
        "An unexpected error occurred. Please retry or contact support.",
        500,
    )


# ---------------------------------------------------------------------------
# Request logging middleware (privacy-safe: no patient data)
# ---------------------------------------------------------------------------
@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    req_id = str(uuid.uuid4())[:8]
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "[%s] %s %s → %d (%.1fms)",
        req_id, request.method, request.url.path, response.status_code, duration_ms
    )
    return response


# ---------------------------------------------------------------------------
# Router registration
# ---------------------------------------------------------------------------
from app.routers import records, profiles, fhir, abha, ask, upload_ui, catalog  # noqa: E402

app.include_router(upload_ui.router, tags=["Upload UI"])
app.include_router(records.router, prefix="/api", tags=["Records"])
app.include_router(profiles.router, prefix="/api", tags=["Profiles"])
app.include_router(fhir.router, prefix="/api", tags=["FHIR"])
app.include_router(abha.router, prefix="/api", tags=["ABHA (Mock)"])
app.include_router(ask.router, prefix="/api", tags=["Ask"])
app.include_router(catalog.router, prefix="/api", tags=["Medical Product Catalog"])


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------
@app.get("/api/health", response_model=HealthResponse, tags=["System"])
def health():
    cfg = get_settings()
    return HealthResponse(
        status="ok",
        api_version=cfg.api_version,
        schema_version=cfg.schema_version,
        ai_mode="mock" if cfg.use_mock_ai else "real",
        features={
            "ask": cfg.feature_ask,
            "abha_mock": cfg.feature_abha_mock,
            "family_profiles": cfg.feature_family_profiles,
        },
    )
