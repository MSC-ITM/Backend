# tests/test_ia_estimate.py
from typing import Dict, Any, List

AUTH = {"Authorization": "Bearer mock-abc"}

VALID_BODY: Dict[str, Any] = {
    "name": "etl-sencillo",
    "definition": {
        "steps": [
            {"type": "HTTPS GET Request", "args": {"url": "https://ejemplo.com/data.csv"}},
            {"type": "Validate CSV File", "args": {"delimiter": ",", "columns": ["a", "b"]}},
            {"type": "Simple Transform", "args": {"op": "uppercase", "field": "a"}},
            {"type": "Save to Database", "args": {"table": "dest_tabla"}},
        ]
    },
    "goals": ["rápido", "barato"],
}


def test_ia_estimate_requires_auth(client):
    resp = client.post("/ia/estimate", json=VALID_BODY)
    assert resp.status_code == 401
    assert resp.json().get("detail") in ("Unauthorized", "Missing or invalid token")


def test_ia_estimate_contract_minimum(client):
    resp = client.post("/ia/estimate", json=VALID_BODY, headers=AUTH)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    # Campos principales
    assert "estimated_runtime_seconds" in data and isinstance(data["estimated_runtime_seconds"], (int, float))
    assert "estimated_cost" in data and isinstance(data["estimated_cost"], (int, float))
    assert "complexity_score" in data and isinstance(data["complexity_score"], (int, float))
    assert 0.0 <= data["complexity_score"] <= 1.0
    assert "breakdown" in data and isinstance(data["breakdown"], list)
    assert "rationale" in data and isinstance(data["rationale"], str)
    assert "confidence" in data and isinstance(data["confidence"], (int, float))

    # Breakdown por paso
    for i, item in enumerate(data["breakdown"]):
        assert isinstance(item, dict)
        assert item.get("step_index") == i
        assert isinstance(item.get("type"), str)
        assert isinstance(item.get("time"), (int, float))
        assert isinstance(item.get("cost"), (int, float))


def test_openapi_includes_ia_estimate_path(client):
    resp = client.get("/openapi.json", headers=AUTH)
    assert resp.status_code == 200, resp.text
    spec = resp.json()
    paths = spec.get("paths", {})
    assert "/ia/estimate" in paths, "Falta path OpenAPI: /ia/estimate"
    assert "post" in paths["/ia/estimate"]
