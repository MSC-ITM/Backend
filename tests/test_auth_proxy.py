# tests/test_auth_proxy.py
from typing import List, Optional
from datetime import datetime
from uuid import uuid4
from datetime import datetime, UTC
import pytest
from fastapi import HTTPException

# Clases importadas del módulo principal para conservar el contrato.
from src.main import AuthProxy, WorkflowItem  # noqa: E402


class FakeRepo:
    """Repositorio falso para verificar delegación sin dependencias externas."""

    def __init__(self) -> None:
        self.created_names: List[str] = []
        self.items_by_id = {}
        self.items_list: List[WorkflowItem] = []

    def create(self, name: str) -> WorkflowItem:
        self.created_names.append(name)
        wid = str(uuid4())
        item = WorkflowItem(
            id=wid,
            name=name,
            status="en_progreso",
            created_at=datetime.now(UTC).replace(microsecond=0).isoformat(),
        )
        self.items_by_id[wid] = item
        self.items_list.append(item)
        return item

    def get(self, wid: str) -> Optional[WorkflowItem]:
        return self.items_by_id.get(wid)

    def list(self) -> List[WorkflowItem]:
        return list(self.items_list)


def test_create_rejects_missing_authorization():
    proxy = AuthProxy(repo=FakeRepo())
    with pytest.raises(HTTPException) as exc:
        proxy.create_workflow(authorization=None, name="w")
    assert exc.value.status_code == 401
    assert exc.value.detail in ("Missing or invalid token", "Unauthorized")


def test_create_rejects_non_bearer_format():
    proxy = AuthProxy(repo=FakeRepo())
    with pytest.raises(HTTPException) as exc:
        proxy.create_workflow(authorization="Token mock-abc", name="w")
    assert exc.value.status_code == 401
    assert exc.value.detail in ("Missing or invalid token", "Unauthorized")


def test_create_rejects_non_mock_token():
    proxy = AuthProxy(repo=FakeRepo())
    with pytest.raises(HTTPException) as exc:
        proxy.create_workflow(authorization="Bearer real-123", name="w")
    assert exc.value.status_code == 401
    assert exc.value.detail == "Unauthorized"


def test_create_accepts_mock_and_delegates():
    repo = FakeRepo()
    proxy = AuthProxy(repo=repo)

    res = proxy.create_workflow(authorization="Bearer mock-xyz", name="job-1")
    # Verifica contrato de salida mínimo
    assert res.status == "en_progreso"
    # Verifica delegación al repositorio
    assert repo.created_names == ["job-1"]


def test_get_status_404_when_missing():
    repo = FakeRepo()
    proxy = AuthProxy(repo=repo)

    with pytest.raises(HTTPException) as exc:
        proxy.get_workflow_status(authorization="Bearer mock-xyz", wid="00000000-0000-0000-0000-000000000000")
    assert exc.value.status_code == 404
    assert exc.value.detail in ("Workflow not found", "Not Found")


def test_get_status_returns_minimal_model():
    repo = FakeRepo()
    proxy = AuthProxy(repo=repo)

    created = repo.create("w")
    res = proxy.get_workflow_status(authorization="Bearer mock-xyz", wid=created.id)
    assert res.id == created.id
    assert res.status in ("en_progreso", "completado", "error")


def test_list_requires_auth():
    proxy = AuthProxy(repo=FakeRepo())
    with pytest.raises(HTTPException) as exc:
        proxy.list_workflows(authorization=None)
    assert exc.value.status_code == 401


def test_list_returns_items_from_repo():
    repo = FakeRepo()
    proxy = AuthProxy(repo=repo)
    # Precarga dos elementos en el repositorio falso
    repo.create("w1")
    repo.create("w2")

    items = proxy.list_workflows(authorization="Bearer mock-abc")
    assert isinstance(items, list)
    assert len(items) >= 2
    names = {i.name for i in items}
    assert {"w1", "w2"}.issubset(names)
