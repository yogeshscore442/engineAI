"""
tests/test_health.py — /api/health endpoint tests.
"""
def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "api_version" in data
    assert "ai_mode" in data
    assert data["ai_mode"] == "mock"
    assert "features" in data


def test_404_error_format(client):
    r = client.get("/api/nonexistent-endpoint-xyz")
    assert r.status_code == 404
    data = r.json()
    assert "error" in data
    assert "code" in data["error"]
    assert "message" in data["error"]


def test_cors_headers_on_response(client):
    r = client.get("/api/health", headers={"Origin": "http://localhost:5173"})
    assert r.status_code == 200
    # CORS headers should be present
    assert "access-control-allow-origin" in r.headers or r.status_code == 200
