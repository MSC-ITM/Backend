# tests/test_ia.py
from typing import Dict, Any

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


def test_ia_suggestion_requires_auth(client):
    resp = client.post("/ia/suggestion", json=VALID_BODY)
    assert resp.status_code == 401
    assert resp.json().get("detail") in ("Unauthorized", "Missing or invalid token")


def test_ia_suggestion_accepts_bearer_mock_and_returns_contract(client):
    resp = client.post("/ia/suggestion", json=VALID_BODY, headers=AUTH)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    # Validación del contrato mínimo
    assert isinstance(data, dict)
    assert "suggestions" in data and isinstance(data["suggestions"], list)
    assert "rationale" in data and isinstance(data["rationale"], str)
    assert "confidence" in data and isinstance(data["confidence"], (int, float))

    # Si hay sugerencias, valida la forma de cada elemento
    for s in data["suggestions"]:
        assert isinstance(s, dict)
        assert "kind" in s and isinstance(s["kind"], str)
        assert "path" in s and isinstance(s["path"], str)
        assert "message" in s and isinstance(s["message"], str)
        assert "confidence" in s and isinstance(s["confidence"], (int, float))
        # 'detail' es opcional pero, si existe, debe ser dict
        if "detail" in s:
            assert isinstance(s["detail"], dict)


def test_openapi_includes_ia_suggestion_path(client):
    resp = client.get("/openapi.json", headers=AUTH)
    assert resp.status_code == 200, resp.text
    spec = resp.json()
    paths = spec.get("paths", {})
    assert "/ia/suggestion" in paths, "Falta path OpenAPI: /ia/suggestion"
    # Debe ser POST
    assert "post" in paths["/ia/suggestion"]
