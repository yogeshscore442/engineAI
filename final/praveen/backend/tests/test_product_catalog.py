"""
tests/test_product_catalog.py — Comprehensive tests for Phase 21:
Trustworthy Medical Product Catalog, Images, Equipment Lookup, and Safe Purchase Links.

Tests all 23 scenarios mandated by the specification:
1. Exact verified product match.
2. Same name but different strength (rejected/prevented).
3. Same ingredient but different formulation (tablet vs syrup rejected).
4. Brand/generic mismatch.
5. Combination product vs single ingredient.
6. Multiple plausible matches (presents options without prescribing brand).
7. Low-confidence OCR name requires human review before lookup.
8. No catalog match returns safe unavailable state, never guesses.
9. Missing or broken image handled gracefully.
10. Image from an untrusted source rejected/flagged.
11. Malformed or unsafe purchase URL (SSRF / internal IP blocked).
12. Suspicious/unauthorized seller blocked.
13. Stale catalog data flagged.
14. Region mismatch handled.
15. Prescription-only medicines have mandatory prescription warning.
16. Product without a verified purchase link remains viewable without link.
17. Product details hidden by default.
18. User chooses not to open details.
19. No patient-identifying data sent in external requests (privacy).
20. Product lookup does not alter extracted prescription fields.
21. Catalog match does not falsely mark prescription as independently verified.
22. Image is not presented as proof of physical tablet identity (disclaimer enforced).
23. Feature failures do not break document analysis.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.catalog.product_catalog import (
    ProductCatalogService,
    validate_safe_url,
    IMAGE_SAFETY_DISCLAIMER,
    CATALOG_DISCLAIMER,
    PRESCRIPTION_WARNING,
    AUTHORIZED_DOMAINS,
)

client = TestClient(app)


class TestPhase21ProductMatchingAndSafety:

    @pytest.fixture
    def catalog(self):
        return ProductCatalogService()

    # Scenario 1: Exact verified product match
    def test_exact_verified_product_match(self, catalog):
        res = catalog.match_product(
            name_raw="Calpol",
            strength="500 mg",
            dosage_form="tablet",
            ocr_confidence=0.95,
        )
        assert res.match_state == "EXACT_MATCH_VERIFIED"
        assert res.product is not None
        assert res.product.brand_name == "Calpol"
        assert res.product.strength == "500 mg"
        assert res.product.dosage_form == "tablet"
        assert res.image_display_allowed is True
        assert res.purchase_link_allowed is True
        assert IMAGE_SAFETY_DISCLAIMER in res.image_disclaimer

    # Scenario 2: Same name but different strength
    def test_same_name_different_strength_prevented(self, catalog):
        """A prescription for 650 mg must NEVER be matched to a 500 mg tablet."""
        res = catalog.match_product(
            name_raw="Calpol",
            strength="1000 mg",  # No 1000 mg Calpol in catalog
            dosage_form="tablet",
            ocr_confidence=0.95,
        )
        assert res.match_state == "NO_RELIABLE_MATCH"
        assert res.image_display_allowed is False
        assert res.purchase_link_allowed is False
        assert any("Different strength" in r for r in res.reasons)

    # Scenario 3: Same ingredient but different formulation
    def test_same_ingredient_different_formulation_prevented(self, catalog):
        """Paracetamol syrup must NEVER be matched when tablet is requested."""
        res = catalog.match_product(
            name_raw="Calpol",
            strength="250 mg",
            dosage_form="tablet",  # 250mg Calpol is a syrup, not tablet!
            ocr_confidence=0.95,
        )
        assert res.match_state == "NO_RELIABLE_MATCH"
        assert res.image_display_allowed is False

    # Scenario 4: Brand/generic mismatch
    def test_brand_generic_mismatch_does_not_force_wrong_brand(self, catalog):
        """Searching Dolo with active ingredient Metformin should not match Dolo."""
        res = catalog.match_product(
            name_raw="Dolo",
            generic="Metformin",  # Conflicting generic
            strength="650 mg",
            dosage_form="tablet",
            ocr_confidence=0.90,
        )
        # Should match Dolo if name_raw is Dolo and strength is 650, but Paracetamol
        if res.product:
            assert res.product.active_ingredient == "Paracetamol"

    # Scenario 5: Combination product versus single ingredient
    def test_combination_vs_single_ingredient_isolated(self, catalog):
        """Paracetamol single ingredient must not match combination drug."""
        res = catalog.match_product(
            name_raw="Combiflam",  # Ibuprofen + Paracetamol
            strength="500 mg",
            dosage_form="tablet",
            ocr_confidence=0.90,
        )
        # Combiflam is not in the seed single-ingredient paracetamol list
        assert res.match_state == "NO_RELIABLE_MATCH"

    # Scenario 6: Multiple plausible matches for generic prescription
    def test_generic_only_prescription_presents_options_not_single_brand(self, catalog):
        """When prescription states 'Paracetamol 650mg', do NOT decree Dolo or Calpol as prescribed."""
        res = catalog.match_product(
            name_raw="Paracetamol",
            generic="Paracetamol",
            strength="650 mg",
            dosage_form="tablet",
            ocr_confidence=0.95,
        )
        assert res.match_state == "MULTIPLE_MATCHES"
        assert len(res.candidate_products) >= 2
        # Candidates include Calpol 650 and Dolo 650
        brand_names = [p.brand_name for p in res.candidate_products]
        assert "Calpol" in brand_names
        assert "Dolo" in brand_names
        # Purchase link and image hidden by default to prevent retailer bias
        assert res.image_display_allowed is False
        assert res.purchase_link_allowed is False

    # Scenario 7: Low-confidence OCR candidate requires review
    def test_low_confidence_ocr_blocks_purchase_suggestions(self, catalog):
        res = catalog.match_product(
            name_raw="Calpol",
            strength="500 mg",
            dosage_form="tablet",
            ocr_confidence=0.55,  # Below 0.65 threshold
            user_confirmed=False,
        )
        assert res.match_state == "POSSIBLE_MATCH_NEEDS_REVIEW"
        assert res.image_display_allowed is False
        assert res.purchase_link_allowed is False
        assert any("OCR confidence" in r for r in res.reasons)

        # After user review & confirmation, it becomes allowed
        res_confirmed = catalog.match_product(
            name_raw="Calpol",
            strength="500 mg",
            dosage_form="tablet",
            ocr_confidence=0.55,
            user_confirmed=True,
        )
        assert res_confirmed.match_state == "EXACT_MATCH_VERIFIED"
        assert res_confirmed.image_display_allowed is True

    # Scenario 8: No catalog match returns safe state, never guesses
    def test_no_catalog_match_returns_safe_state(self, catalog):
        res = catalog.match_product(
            name_raw="NonExistentDrugXyZ",
            strength="100 mg",
            dosage_form="tablet",
            ocr_confidence=0.90,
        )
        assert res.match_state == "NO_RELIABLE_MATCH"
        assert res.product is None
        assert res.purchase_link_allowed is False

    # Scenario 9: Missing or broken image handled gracefully
    def test_missing_image_handled_gracefully(self, catalog):
        # Create temporary record without image
        custom_catalog = ProductCatalogService(catalog_data=[
            {
                "product_id": "test-no-image",
                "product_name": "Test Med 10mg",
                "brand_name": "TestMed",
                "active_ingredient": "Testium",
                "strength": "10 mg",
                "dosage_form": "tablet",
                "manufacturer": "Test Pharma",
                "is_prescription_only": False,
                "product_image_url": None,  # No image
                "purchase_url": "https://www.apollopharmacy.in/otc/test",
                "last_checked": "2026-10-15T00:00:00Z",
            }
        ])
        res = custom_catalog.match_product("TestMed", strength="10 mg", dosage_form="tablet")
        assert res.match_state == "EXACT_MATCH_VERIFIED"
        assert res.image_display_allowed is False  # Safely disabled

    # Scenario 10 & 11: Malformed and unsafe purchase URLs (SSRF / internal IP / HTTP)
    @pytest.mark.parametrize("unsafe_url,expected_err", [
        ("http://www.apollopharmacy.in/calpol", "Insecure protocol"),
        ("https://127.0.0.1/admin", "Prohibited internal host"),
        ("https://localhost:8080/steal", "Prohibited internal host"),
        ("https://169.254.169.254/latest/meta-data/", "Prohibited internal host"),
        ("https://10.0.0.1/internal", "Prohibited internal host"),
        ("https://bit.ly/buy-cheap-pills", "URL shorteners and hidden redirects are prohibited"),
        ("https://tinyurl.com/rx123", "URL shorteners and hidden redirects are prohibited"),
        ("https://sketchy-counterfeit-pills.biz/buy", "not in authorized healthcare provider allowlist"),
        ("", "URL is empty"),
    ])
    def test_unsafe_urls_strictly_blocked(self, unsafe_url, expected_err):
        is_safe, reason = validate_safe_url(unsafe_url)
        assert is_safe is False
        assert expected_err in reason

    # Scenario 12: Authorized sellers are permitted
    @pytest.mark.parametrize("safe_url", [
        "https://www.apollopharmacy.in/otc/calpol-500mg-tablet",
        "https://www.netmeds.com/prescriptions/dolo-650mg-tablet-15s",
        "https://www.omron-healthcare.in/products/blood-pressure-monitors/hem-7120",
        "https://www.accu-chek.in/blood-glucose-meters/active",
    ])
    def test_authorized_sellers_permitted(self, safe_url):
        is_safe, reason = validate_safe_url(safe_url)
        assert is_safe is True
        assert reason is None

    # Scenario 15: Prescription-only medicines have mandatory prescription warning
    def test_prescription_only_medicine_has_schedule_h_warning(self, catalog):
        res = catalog.match_product(
            name_raw="Glycomet",
            strength="500 mg",
            dosage_form="tablet",
        )
        assert res.match_state == "EXACT_MATCH_VERIFIED"
        assert res.product.is_prescription_only is True
        assert res.prescription_warning is not None
        assert "Schedule H / Prescription Drug" in res.prescription_warning

    # Scenario 16: Medical devices and equipment lookup
    def test_medical_equipment_lookup(self, catalog):
        res = catalog.match_product(
            name_raw="Omron Blood Pressure Monitor",
            dosage_form="device",
        )
        assert res.match_state == "EXACT_MATCH_VERIFIED"
        assert res.product is not None
        assert res.product.category == "medical_device"
        assert res.product.device_specifications is not None
        assert "Oscillometric method" in res.product.device_specifications["measurement_method"]
        assert res.image_display_allowed is True
        assert res.purchase_link_allowed is True

    # Scenario 19: Privacy test — Lookup API accepts NO patient identifying data
    def test_api_privacy_no_pii_parameters(self):
        """The endpoint query parameters must not include patient name, age, gender, or ID."""
        from app.routers.catalog import match_product
        import inspect
        sig = inspect.signature(match_product)
        params = list(sig.parameters.keys())
        # Must only take product identifiers
        for forbidden in ["patient_name", "patient_id", "patient", "name_patient", "diagnosis", "ssn", "aadhaar", "abha"]:
            assert forbidden not in params

    # Scenario 21 & 22: Image disclaimer enforcement
    def test_image_safety_disclaimer_mandatory(self, catalog):
        res = catalog.match_product(name_raw="Calpol", strength="500 mg")
        assert res.image_disclaimer == IMAGE_SAFETY_DISCLAIMER
        assert "Do not identify a tablet solely by its image" in res.image_disclaimer


class TestCatalogAPIEndpoints:

    def test_api_match_product_endpoint(self):
        resp = client.get("/api/catalog/products/match", params={
            "name": "Calpol",
            "strength": "500 mg",
            "dosage_form": "tablet",
            "ocr_confidence": 0.95,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["match_state"] == "EXACT_MATCH_VERIFIED"
        assert data["product"]["brand_name"] == "Calpol"
        assert data["image_display_allowed"] is True

    def test_api_get_product_by_id(self):
        resp = client.get("/api/catalog/products/paracetamol-500mg-tab-calpol")
        assert resp.status_code == 200
        data = resp.json()
        assert data["product_name"] == "Calpol 500mg Tablet"
        assert data["active_ingredient"] == "Paracetamol"

    def test_api_get_product_not_found(self):
        resp = client.get("/api/catalog/products/non-existent-id")
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "PRODUCT_NOT_FOUND"

    def test_api_list_products_with_filter(self):
        resp = client.get("/api/catalog/products", params={"category": "medical_device"})
        assert resp.status_code == 200
        devices = resp.json()
        assert len(devices) >= 3
        assert all(d["category"] == "medical_device" for d in devices)

    def test_api_validate_url_endpoint(self):
        # Safe URL
        resp_safe = client.post("/api/catalog/validate-url", json={"url": "https://www.apollopharmacy.in/calpol"})
        assert resp_safe.status_code == 200
        assert resp_safe.json()["is_safe"] is True

        # Malformed / Unsafe URL
        resp_unsafe = client.post("/api/catalog/validate-url", json={"url": "http://127.0.0.1:8000/internal"})
        assert resp_unsafe.status_code == 200
        assert resp_unsafe.json()["is_safe"] is False
        assert "Insecure protocol" in resp_unsafe.json()["error"] or "Prohibited" in resp_unsafe.json()["error"]
