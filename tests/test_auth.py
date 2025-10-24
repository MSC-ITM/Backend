# tests/test_auth.py
import re

UUID_RE = r"^[0-9a-fA-F-]{36}$"


def test_login_success(client):
    """
    Contrato:
    POST /login
    200 OK -> access_token mock, token_type 'bearer', user con UUID y nombre.
    """
    payload = {"username": "demo", "password": "demo123"}
    resp = client.post("/login", json=payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert isinstance(data.get("access_token"), str)
    assert data.get("access_token").startswith("mock-")
    assert data.get("token_type") == "bearer"

    user = data.get("user") or {}
    assert re.match(UUID_RE, user.get("id", ""))
    assert user.get("name") == "Demo User"


def test_login_unauthorized(client):
    """Credenciales inválidas deben responder 401 Unauthorized."""
    payload = {"username": "demo", "password": "wrong"}
    resp = client.post("/login", json=payload)
    assert resp.status_code == 401
    assert resp.json().get("detail") in ("Invalid credentials", "Unauthorized")


def test_workflow_requires_auth_header(client):
    """Las rutas de workflows requieren encabezado Authorization Bearer."""
    resp = client.post("/workflow", json={"name": "w", "definition": {}})
    assert resp.status_code == 401
    assert resp.json().get("detail") in ("Unauthorized", "Missing or invalid token")


def test_workflow_accepts_bearer_mock(client):
    """Cualquier token con prefijo 'mock-' es aceptado por el mock de auth."""
    headers = {"Authorization": "Bearer mock-xyz"}
    resp = client.post("/workflow", json={"name": "w", "definition": {}}, headers=headers)
    assert resp.status_code == 201
