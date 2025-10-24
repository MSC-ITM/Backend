# tests/test_workflows.py
import re

UUID_RE = r"^[0-9a-fA-F-]{36}$"
AUTH = {"Authorization": "Bearer mock-abc"}


def test_create_workflow_returns_201_and_en_progreso(client):
    """
    POST /workflow -> 201 Created con id UUID y estado 'en_progreso'.
    """
    payload = {
        "name": "etl-sencillo",
        "definition": {"steps": [{"type": "echo", "args": {"msg": "hola"}}]},
    }
    resp = client.post("/workflow", json=payload, headers=AUTH)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert re.match(UUID_RE, data.get("id", ""))
    assert data.get("status") == "en_progreso"


def test_get_workflow_status_found(client):
    """
    GET /workflows/{id}/status -> 200 OK con id y estado válido.
    """
    create = client.post("/workflow", json={"name": "job-1", "definition": {}}, headers=AUTH)
    wid = create.json()["id"]

    resp = client.get(f"/workflows/{wid}/status", headers=AUTH)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data.get("id") == wid
    assert data.get("status") in ("en_progreso", "completado", "error")


def test_get_workflow_status_not_found(client):
    """Id inexistente debe responder 404 Not Found."""
    resp = client.get(
        "/workflows/00000000-0000-0000-0000-000000000000/status", headers=AUTH
    )
    assert resp.status_code == 404
    assert resp.json().get("detail") in ("Not Found", "Workflow not found")


def test_list_workflows_includes_created(client):
    """GET /workflows retorna elementos que fueron creados previamente."""
    w1 = client.post("/workflow", json={"name": "w1", "definition": {}}, headers=AUTH).json()["id"]
    w2 = client.post("/workflow", json={"name": "w2", "definition": {}}, headers=AUTH).json()["id"]

    resp = client.get("/workflows", headers=AUTH)
    assert resp.status_code == 200, resp.text
    items = resp.json()
    assert isinstance(items, list)
    ids = {item["id"] for item in items}
    assert w1 in ids and w2 in ids


def test_list_workflows_requires_auth(client):
    """GET /workflows sin Authorization debe responder 401 Unauthorized."""
    resp = client.get("/workflows")
    assert resp.status_code == 401


def test_openapi_contains_expected_paths(client):
    """
    El documento OpenAPI debe exponer los paths mínimos.
    """
    resp = client.get("/openapi.json")
    assert resp.status_code == 200, resp.text
    spec = resp.json()
    paths = spec.get("paths", {})
    for p in ("/login", "/workflow", "/workflows", "/workflows/{id}/status"):
        assert p in paths, f"Falta path OpenAPI: {p}"
