"""Cross-module regressions. External LLM responses are fixtures, never live."""
import asyncio
import json
import sys
from pathlib import Path

import pytest

from app.integration import AI_PROJECT_ROOT, DISCLAIMER
from app.services import ai_client
from app.services.normalizer import normalize_test
from tests.conftest import make_fake_png

sys.path.insert(0, str(AI_PROJECT_ROOT))
import ai_engine
import ai_engine.extract as extraction
import ai_engine.summarize as summarization


@pytest.fixture
def integrated_ai(monkeypatch):
    monkeypatch.setenv("USE_MOCK_AI", "false")
    monkeypatch.setenv("DISABLE_CACHE", "true")
    monkeypatch.setattr(summarization, "_call_summarize_llm", lambda *a: "")
    real = ai_client.RealAIClient()
    assert real._extract_fn is ai_engine.extract_record
    monkeypatch.setattr(ai_client, "_AI_CLIENT", real)
    return real


@pytest.mark.parametrize("doc_type", ["lab_report", "prescription", "discharge_summary"])
def test_full_module_flow(client, default_profile_id, integrated_ai, monkeypatch, doc_type):
    fixture = json.loads((AI_PROJECT_ROOT / "contract" / f"mock_{doc_type}.json").read_text(encoding="utf-8"))
    calls = []
    def provider(*args):
        calls.append(args)
        # Exercise the real JSON-fence parser (previously missing import re).
        return "```json\n" + json.dumps(fixture) + "\n```"
    monkeypatch.setattr(extraction, "_call_llm", provider)
    content = make_fake_png() + doc_type.encode()
    upload = client.post(f"/api/profiles/{default_profile_id}/records", files={"file": (f"{doc_type}.png", content, "image/png")})
    assert upload.status_code == 201, upload.text
    rid = upload.json()["record_id"]
    draft = upload.json()["record"]
    record = draft["record_json"]
    assert calls, "Must run Yogesh's extraction, not backend mock mode"
    assert not record.get("error"), record
    assert draft["source"] == "ai"
    assert record["record_id"] == rid
    assert record["doc_type"] == doc_type
    assert record["disclaimer"] == DISCLAIMER
    assert "safety_alerts" not in record
    assert client.get(f"/api/records/{rid}/file").content == content
    record["doc_date"] = "2026-10-01"
    for test in record["tests"]:
        test.pop("date", None)
    confirmed = client.put(f"/api/records/{rid}", json={"record": record})
    assert confirmed.status_code == 200, confirmed.text
    result = confirmed.json()
    assert result["status"] == "confirmed"
    assert result["doc_date"] == "2026-10-01"
    assert result["record_json"]["summary_en"]
    timeline = client.get(f"/api/profiles/{default_profile_id}/timeline").json()["items"]
    assert any(r["record_id"] == rid and r["doc_date"] == "2026-10-01" for r in timeline)
    assert client.get(f"/api/records/{rid}/fhir").json()["resourceType"] == "Bundle"
    for test in result["tests"]:
        if test["value"] is not None:
            points = client.get(f"/api/profiles/{default_profile_id}/trends", params={"test": test["name_canonical"]}).json()["points"]
            assert any(p["record_id"] == rid and p["date"] == "2026-10-01" for p in points)
    again = client.put(f"/api/records/{rid}", json={"record": record}).json()
    assert len(again["tests"]) == len(result["tests"])


def test_adapter_signature_and_cleanup(monkeypatch):
    paths = []
    def extract(path, mime, lang_hint="auto"):
        paths.append(Path(path))
        assert Path(path).read_bytes() == b"document"
        assert mime == "application/pdf"
        assert lang_hint == "ta"
        return {"error": None}
    monkeypatch.setattr(ai_engine, "extract_record", extract)
    result = asyncio.run(ai_client.RealAIClient().extract(b"document", "../../scan.pdf", "ta"))
    assert result["source"] == "ai"
    assert not paths[0].exists()


def test_real_error_can_be_retried(client, default_profile_id, integrated_ai):
    content = b"%PDF-invalid-integration"
    def upload():
        return client.post(f"/api/profiles/{default_profile_id}/records", files={"file": ("broken.pdf", content, "application/pdf")})
    first, second = upload(), upload()
    assert first.status_code == second.status_code == 201
    assert first.json()["record_id"] != second.json()["record_id"]
    record = first.json()["record"]
    assert record["needs_review"] is True
    assert record["record_json"]["error"]["code"] == "EXTRACTION_FAILED"
    assert record["source"] == "ai"


def test_unknown_units_do_not_receive_wrong_ranges():
    result = normalize_test({"name": "Fasting Blood Glucose", "value": 5.5, "unit": "mmol/L", "flag": "NORMAL"})
    assert result.get("ref_low") is None
    assert result.get("ref_high") is None
    assert result["flag"] == "UNKNOWN"


def test_correction_refreshes_summary_and_flag(client, default_profile_id):
    upload = client.post(f"/api/profiles/{default_profile_id}/records", files={"file": ("lab.png", make_fake_png() + b"correction", "image/png")})
    rid = upload.json()["record_id"]
    record = upload.json()["record"]["record_json"]
    record["tests"] = [{"name": "HbA1c", "value": 5.0, "unit": "%", "ref_low": 4.0, "ref_high": 5.6, "flag": "HIGH", "explanation_en": "Old high value"}]
    record["summary_en"] = "Old high value"
    result = client.put(f"/api/records/{rid}", json={"record": record})
    assert result.status_code == 200, result.text
    data = result.json()["record_json"]
    assert data["tests"][0]["flag"] == "NORMAL"
    assert "Old high value" not in data["summary_en"]
    assert "within" in data["tests"][0]["explanation_en"]


def test_bad_confirm_list_is_422(client, default_profile_id):
    upload = client.post(f"/api/profiles/{default_profile_id}/records", files={"file": ("lab.png", make_fake_png() + b"invalid-list", "image/png")})
    rid = upload.json()["record_id"]
    response = client.put(f"/api/records/{rid}", json={"record": {"doc_type": "lab_report", "tests": [None]}})
    assert response.status_code == 422


def test_yogesh_brand_catalog_is_loaded():
    from app.catalog.brands_loader import load_brands, get_generic
    load_brands(AI_PROJECT_ROOT / "ai_engine" / "brands.csv")
    assert get_generic("Dolo 650") == "paracetamol"


def test_deterministic_summary_never_calls_provider(monkeypatch):
    def forbidden(*args):
        raise AssertionError("Deterministic mode must not call a provider")
    monkeypatch.setattr(summarization, "_call_summarize_llm", forbidden)
    result = summarization.build_summaries({"tests": [], "medicines": []}, use_llm=False)
    assert result["summary_en"] and result["summary_ta"] and result["summary_hi"]
