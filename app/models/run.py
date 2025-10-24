from typing import Optional, Dict, Any
from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship
from enum import Enum
from .base import Timestamped

class RunStatus(str, Enum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    canceled = "canceled"

class Run(SQLModel, Timestamped, table=True):
    id: str = Field(primary_key=True, index=True)
    org_id: str = Field(index=True)
    workflow_id: str = Field(foreign_key="workflow.id", index=True)
    workflow_version_id: str = Field(foreign_key="workflowversion.id", index=True)

    status: RunStatus = Field(default=RunStatus.queued, index=True)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    # para parámetros de ejecución (inputs del usuario/disparador)
    params: Optional[Dict[str, Any]] = None
    # para métricas de ejecución general (duración total, etc.)
    metrics: Optional[Dict[str, Any]] = None
    # para error de alto nivel (stack, mensaje)
    error: Optional[Dict[str, Any]] = None

    steps: list["RunStep"] = Relationship(back_populates="run")

class StepStatus(str, Enum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    skipped = "skipped"

class RunStep(SQLModel, Timestamped, table=True):
    id: str = Field(primary_key=True, index=True)
    run_id: str = Field(foreign_key="run.id", index=True)

    node_id: str = Field(index=True)        # ID del nodo en el grafo (del snapshot)
    node_type: str = Field(index=True)      # p.ej. "http.request"
    label: Optional[str] = None

    status: StepStatus = Field(default=StepStatus.queued, index=True)
    attempt: int = Field(default=1)

    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    # request/response/materializado por el worker
    input: Optional[Dict[str, Any]] = None
    output: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None

    run: Run = Relationship(back_populates="steps")
