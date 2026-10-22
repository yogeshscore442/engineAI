"""Regression coverage for audit findings; no external provider calls."""
import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from app.services import ai_client, files


@pytest.mark.parametrize('endpoint', ['timeline', 'alerts', 'trends?test=HbA1c'])
def test_missing_profile_reads_do_not_create_patients(client, endpoint):
    pid = 'missing-audit-profile'
    assert client.get(f'/api/profiles/{pid}/{endpoint}').status_code == 404
    assert client.get(f'/api/profiles/{pid}').status_code == 404


@pytest.mark.parametrize('name', ['', '   ', 'a' * 201])
def test_invalid_profile_names(client, name):
    result = client.post('/api/profiles', json={'name': name})
    assert result.status_code == 422
    assert result.json()['error']['code'] == 'VALIDATION_ERROR'


def test_empty_question(client, default_profile_id):
    result = client.post(f'/api/profiles/{default_profile_id}/ask', json={'question': '  '})
    assert result.status_code == 422
    assert 'error' in result.json()


def test_file_path_containment(tmp_path, monkeypatch):
    allowed = tmp_path / 'uploads'
    allowed.mkdir()
    sibling = tmp_path / 'uploads-private'
    sibling.mkdir()
    secret = sibling / 'secret.txt'
    secret.write_text('synthetic')
    valid = allowed / 'scan.pdf'
    valid.write_bytes(b'%PDF')
    monkeypatch.setattr(files, 'get_settings', lambda: SimpleNamespace(upload_dir_resolved=allowed))
    assert files.get_file_path(str(secret)) is None
    assert files.get_file_path(str(allowed)) is None
    assert files.get_file_path(str(valid)) == valid


def test_upload_read_is_bounded(monkeypatch):
    monkeypatch.setattr(files, 'get_settings', lambda: SimpleNamespace(max_upload_bytes=4, max_upload_mb=1))
    upload = SimpleNamespace(filename='scan.pdf', read=AsyncMock(return_value=b'%PDF!'))
    with pytest.raises(HTTPException) as exc:
        asyncio.run(files.validate_and_read_upload(upload))
    assert exc.value.status_code == 413
    upload.read.assert_awaited_once_with(5)


def test_missing_engine_has_explicit_failure(monkeypatch):
    client = ai_client.RealAIClient.__new__(ai_client.RealAIClient)
    client._extract_fn = None
    client._load_error = 'synthetic missing dependency'
    monkeypatch.setattr(ai_client, 'get_settings', lambda: SimpleNamespace(allow_mock_fallback=False))
    with pytest.raises(RuntimeError, match='not available'):
        asyncio.run(client.extract(b'document'))


def test_cors_rejects_unlisted_origin_on_errors(client):
    response = client.get('/api/records/missing', headers={'Origin': 'https://untrusted.example'})
    assert response.status_code == 404
    assert 'access-control-allow-origin' not in response.headers


def test_unknown_trend_does_not_invent_unit(client, default_profile_id):
    result = client.get(f'/api/profiles/{default_profile_id}/trends?test=unknown-analyte')
    assert result.status_code == 200
    assert result.json()['unit'] is None


def test_ask_timeout_does_not_wait_for_worker(monkeypatch):
    import time
    from app.services import ask
    def slow_provider(*args):
        time.sleep(0.3)
        return 'late answer'
    monkeypatch.setattr(ask, '_call_gemini_raw', slow_provider)
    start = time.perf_counter()
    assert ask._ask_gemini_with_timeout('synthetic', 'question', '', 'en', timeout_sec=0.01) is None
    assert time.perf_counter() - start < 0.2


def test_ask_excludes_unconfirmed_documents(monkeypatch):
    from app.services import ask
    monkeypatch.setattr(ask, 'get_records_by_profile', lambda *args: [SimpleNamespace(status='draft')])
    context, sources = ask._build_patient_context(None, 'synthetic')
    assert sources == []
    assert 'No uploaded' in context


@pytest.mark.parametrize('record', [
    {'doc_type': 12},
    {'doc_type': 'lab_report', 'doc_date': '2026-02-30'},
    {'doc_type': 'lab_report', 'tests': [{'name': 5}]},
    {'doc_type': 'lab_report', 'tests': [{'value': 'NaN'}]},
    {'doc_type': 'prescription', 'medicines': [{'confidence': 2}]},
])
def test_bad_confirm_data_is_rejected(record):
    from app.services.validators import validate_record_json
    assert validate_record_json(record)[0] is False


def test_specific_question_does_not_answer_with_unrelated_test(monkeypatch):
    from app.services import ask
    monkeypatch.setattr(ask, '_get_api_key', lambda: '')
    monkeypatch.setattr(ask, 'get_records_by_profile', lambda *args: [])
    monkeypatch.setattr(ask, 'get_tests_by_name', lambda *args: [])
    answer = ask.answer_question(None, 'synthetic', 'What is my HbA1c result?')
    assert 'No confirmed HbA1c' in answer.answer
    assert answer.sources == []


@pytest.mark.parametrize('path', ['/', '/upload', '/docs', '/openapi.json', '/api/profiles'])
def test_readonly_routes(client, path):
    assert client.get(path).status_code == 200


def test_ask_api_and_missing_profile(client, default_profile_id, monkeypatch):
    from app.services import ask
    monkeypatch.setattr(ask, '_get_api_key', lambda: '')
    response = client.post(f'/api/profiles/{default_profile_id}/ask', json={'question': 'Hello'})
    assert response.status_code == 200
    assert response.json()['answer']
    assert client.post('/api/profiles/no-such-profile/ask', json={'question': 'Hello'}).status_code == 404


def test_cors_permits_local_frontend(client):
    response = client.options('/api/health', headers={'Origin': 'http://localhost:5173', 'Access-Control-Request-Method': 'GET'})
    assert response.status_code == 200
    assert response.headers['access-control-allow-origin'] == 'http://localhost:5173'


def test_method_not_allowed(client):
    response = client.post('/api/health')
    assert response.status_code == 405
    assert response.json()['error']['code'] == 'METHOD_NOT_ALLOWED'
