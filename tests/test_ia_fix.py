# tests/test_ia_fix.py
from typing import Dict, Any, List

AUTH = {"Authorization": "Bearer mock-abc"}


def _post(client, body: Dict[str, Any]):
    return client.post("/ia/fix", json=body, headers=AUTH)


def test_ia_fix_requires_auth(client):
    body = {"name": "w", "definition": {"steps": []}}
    resp = client.post("/ia/fix", json=body)
    assert resp.status_code == 401
    assert resp.json().get("detail") in ("Unauthorized", "Missing or invalid token")


def test_ia_fix_contract_minimum(client):
    body = {
        "name": "etl-sencillo",
        "definition": {"steps": []},
        "logs": "optional logs text",
    }
    resp = _post(client, body)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    # Contrato mínimo
    assert isinstance(data, dict)
    assert "patched_definition" in data and isinstance(data["patched_definition"], dict)
    assert "changes" in data and isinstance(data["changes"], list)
    assert "rationale" in data and isinstance(data["rationale"], str)
    assert "confidence" in data and isinstance(data["confidence"], (int, float))


def test_ia_fix_sets_timeout_if_missing(client):
    body = {
        "name": "w",
        "definition": {
            "steps": [
                {"type": "HTTPS GET Request", "args": {"url": "https://ejemplo.com/data.csv"}},
            ]
        },
    }
    resp = _post(client, body)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    steps: List[Dict[str, Any]] = data["patched_definition"]["steps"]
    assert steps[0]["type"] == "HTTPS GET Request"
    # Debe establecer timeout=10 si no estaba
    assert steps[0]["args"].get("timeout") == 10

    # Debe reportar el cambio como parameter_set
    kinds = {c.get("kind") for c in data["changes"]}
    assert "parameter_set" in kinds


def test_ia_fix_adds_output_if_missing(client):
    body = {
        "name": "w",
        "definition": {
            "steps": [
                {"type": "Validate CSV File", "args": {"delimiter": ",", "columns": ["a", "b"]}},
                {"type": "Simple Transform", "args": {"op": "uppercase", "field": "a"}},
            ]
        },
    }
    resp = _post(client, body)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    steps: List[Dict[str, Any]] = data["patched_definition"]["steps"]
    types = [s.get("type") for s in steps]
    # Debe existir un nodo de salida tras la corrección
    assert any(t in ("Save to Database", "Mock Notification") for t in types)

    kinds = {c.get("kind") for c in data["changes"]}
    assert "add_node" in kinds


def test_ia_fix_reorders_validate_before_transform(client):
    body = {
        "name": "w",
        "definition": {
            "steps": [
                {"type": "Simple Transform", "args": {"op": "uppercase", "field": "a"}},
                {"type": "Validate CSV File", "args": {"delimiter": ",", "columns": ["a", "b"]}},
                {"type": "Save to Database", "args": {"table": "dest_tabla"}},
            ]
        },
    }
    resp = _post(client, body)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    steps: List[Dict[str, Any]] = data["patched_definition"]["steps"]
    types = [s.get("type") for s in steps]

    # 'Validate CSV File' debe quedar antes de 'Simple Transform'
    assert types.index("Validate CSV File") < types.index("Simple Transform")

    kinds = {c.get("kind") for c in data["changes"]}
    assert "reorder_nodes" in kinds


def test_openapi_includes_ia_fix_path(client):
    resp = client.get("/openapi.json", headers=AUTH)
    assert resp.status_code == 200, resp.text
    spec = resp.json()
    paths = spec.get("paths", {})
    assert "/ia/fix" in paths, "Falta path OpenAPI: /ia/fix"
    assert "post" in paths["/ia/fix"]
