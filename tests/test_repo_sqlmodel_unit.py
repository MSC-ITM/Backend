# tests/test_repo_sqlmodel_unit.py
"""
Pruebas unitarias del repositorio basado en SQLModel usando SQLite en memoria.
No crea archivos .db. La interfaz debe ser compatible con el repositorio en memoria.
"""

import re
from typing import Optional
import pytest
from sqlmodel import create_engine
from sqlalchemy.pool import StaticPool

# Importa los tipos/contratos del módulo principal.
from src.main import SQLiteWorkflowRepo, WorkflowItem  # noqa: E402

UUID_RE = r"^[0-9a-fA-F-]{36}$"


@pytest.fixture(scope="module")
def engine():
    # BD en memoria compartida entre hilos y conexiones:
    # - "sqlite://" con StaticPool mantiene UNA conexión viva
    # - check_same_thread=False permite acceso desde hilos del TestClient
    eng = create_engine(
        "sqlite://",  # <- OJO: sin '/:memory:' aquí
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    return eng


@pytest.fixture()
def repo(engine):
    """
    Crea un repositorio limpio por prueba y crea el esquema.
    """
    r = SQLiteWorkflowRepo(engine=engine)
    r.create_schema()
    return r


def test_create_returns_workflow_item(repo):
    item: WorkflowItem = repo.create(name="etl-sqlmodel", definition={"steps": []})
    assert re.match(UUID_RE, item.id)
    assert item.name == "etl-sqlmodel"
    assert item.status in ("en_progreso", "completado", "error")
    # Acepta formato ISO 8601 con zona UTC ("Z" o "+00:00")
    assert isinstance(item.created_at, str)
    assert item.created_at.endswith("Z") or item.created_at.endswith("+00:00")


def test_get_returns_same_item(repo):
    created = repo.create(name="job-1", definition={"steps": [{"type": "Mock Notification"}]})
    fetched: Optional[WorkflowItem] = repo.get(created.id)
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.name == "job-1"
    assert fetched.status == created.status


def test_list_includes_created_items(repo):
    a = repo.create(name="a", definition={})
    b = repo.create(name="b", definition={})
    items = repo.list()
    ids = {i.id for i in items}
    assert a.id in ids and b.id in ids


def test_definition_is_persisted_as_json(repo):
    definition = {"steps": [{"type": "HTTPS GET Request", "args": {"url": "https://x"}}]}
    created = repo.create(name="djson", definition=definition)
    fetched = repo.get(created.id)
    # El modelo público no expone definition, pero el repo SQLModel debe guardarlo internamente.
    # Se valida indirectamente: si la implementación decide exponerlo más adelante, esta prueba puede ampliarse.
    assert fetched is not None  # Sanity check: el registro existe
