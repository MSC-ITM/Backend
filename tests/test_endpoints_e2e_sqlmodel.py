# tests/test_endpoints_e2e_sqlmodel.py
"""
Pruebas E2E: se intercambia el repositorio global de la app por uno basado en SQLModel (SQLite en memoria).
Los handlers no cambian; se valida compatibilidad del contrato con la nueva persistencia.
"""

import re
import pytest
from sqlmodel import create_engine
from sqlalchemy.pool import StaticPool

UUID_RE = r"^[0-9a-fA-F-]{36}$"
AUTH = {"Authorization": "Bearer mock-e2e"}

@pytest.fixture(scope="module")
def engine():
    return create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )


@pytest.fixture(autouse=True, scope="module")
def swap_repo_to_sqlmodel(engine):
    """
    Intercambia el repositorio global _repo de la app por SQLiteWorkflowRepo
    y reconstruye el proxy para que use el nuevo repo.
    """
    from src import main
    from src.main import SQLiteWorkflowRepo, AuthProxy

    sql_repo = SQLiteWorkflowRepo(engine=engine)
    sql_repo.create_schema()

    # Swap de dependencias globales
    main._repo = sql_repo
    main.proxy = AuthProxy(main._repo)

    yield

    # No se requiere teardown específico: engine en memoria muere al finalizar el proceso.


def test_create_workflow_persists_in_sqlmodel(client):
    payload = {"name": "w-e2e", "definition": {"steps": []}}
    resp = client.post("/workflow", json=payload, headers=AUTH)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert re.match(UUID_RE, data.get("id", ""))
    assert data.get("status") == "en_progreso"


def test_list_then_contains_created(client):
    # Crea dos workflows
    w1 = client.post("/workflow", json={"name": "a", "definition": {}}, headers=AUTH).json()["id"]
    w2 = client.post("/workflow", json={"name": "b", "definition": {}}, headers=AUTH).json()["id"]

    # Lista y valida presencia
    resp = client.get("/workflows", headers=AUTH)
    assert resp.status_code == 200, resp.text
    items = resp.json()
    ids = {i["id"] for i in items}
    assert w1 in ids and w2 in ids


def test_status_found_uses_sqlmodel_store(client):
    create = client.post("/workflow", json={"name": "stat", "definition": {}}, headers=AUTH)
    wid = create.json()["id"]

    resp = client.get(f"/workflows/{wid}/status", headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == wid
    assert data["status"] in ("en_progreso", "completado", "error")
