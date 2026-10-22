"""
app/routers/catalog.py — Medical Product Details, Images, Equipment Lookup,
and Safe Purchase Link API (Phase 21).

Endpoints:
- GET  /api/catalog/products/match: Exact-matches extracted medicine or device to catalog.
- GET  /api/catalog/products/{product_id}: Retrieves verified product details by ID.
- GET  /api/catalog/products: Lists verified catalog products by category.
- POST /api/catalog/validate-url: Validates external purchase URL safety (SSRF/allowlist).
"""
from __future__ import annotations

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from app.catalog.product_catalog import (
    catalog_service,
    ProductRecord,
    ProductMatchResult,
    validate_safe_url,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/catalog", tags=["Medical Product Catalog"])


class ValidateUrlRequest(BaseModel):
    url: str


class ValidateUrlResponse(BaseModel):
    url: str
    is_safe: bool
    error: Optional[str] = None


@router.get("/products/match", response_model=ProductMatchResult)
def match_product(
    name: str = Query(..., description="Prescribed or recognized product/medicine name"),
    generic: Optional[str] = Query(None, description="Active generic ingredient"),
    strength: Optional[str] = Query(None, description="Medication strength e.g. 500 mg"),
    dosage_form: Optional[str] = Query(None, description="Dosage form e.g. tablet, syrup, device"),
    ocr_confidence: float = Query(1.0, ge=0.0, le=1.0, description="OCR confidence for the extracted field"),
    user_confirmed: bool = Query(False, description="Whether the user explicitly reviewed and confirmed the field"),
):
    """
    Finds a verified medical product match using exact matching rules.
    Guarantees:
    - Never substitutes different strengths or formulations.
    - Low-confidence OCR requires user confirmation before purchase links are allowed.
    - Preserves privacy: does not accept patient details or prescription documents.
    """
    return catalog_service.match_product(
        name_raw=name,
        generic=generic,
        strength=strength,
        dosage_form=dosage_form,
        ocr_confidence=ocr_confidence,
        user_confirmed=user_confirmed,
    )


@router.get("/products/{product_id}", response_model=ProductRecord)
def get_product_by_id(product_id: str):
    """Retrieves verified medical product or device record by product ID."""
    prod = catalog_service.get_product(product_id)
    if not prod:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "PRODUCT_NOT_FOUND", "message": f"Product '{product_id}' not found in verified catalog"}},
        )
    return prod


@router.get("/products", response_model=list[ProductRecord])
def list_catalog_products(category: Optional[str] = Query(None, description="Optional category filter: medicine, medical_device, supplement")):
    """Lists verified products in the medical catalog."""
    return catalog_service.list_products(category=category)


@router.post("/validate-url", response_model=ValidateUrlResponse)
def validate_url_safety(body: ValidateUrlRequest):
    """
    Validates an external healthcare product or purchase link:
    - Strict HTTPS
    - SSRF prevention (no internal IPs, cloud metadata, or localhost)
    - Blocked shorteners and open redirects
    - Authorized healthcare domain allowlist
    """
    is_safe, err = validate_safe_url(body.url)
    return ValidateUrlResponse(url=body.url, is_safe=is_safe, error=err)
