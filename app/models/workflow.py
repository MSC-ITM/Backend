from typing import Dict, Any, Optional
from sqlmodel import SQLModel, Field, Relationship
from enum import Enum
from .base import Timestamped

class WorkflowStatus(str, Enum):
    draft = "draft"
    published = "published"
    archived = "archived"

class Workflow(SQLModel, Timestamped, table=True):
    id: str = Field(primary_key=True, index=True)
    org_id: str = Field(index=True)
    name: str
    status: WorkflowStatus = Field(default=WorkflowStatus.draft)
    # “draft_json” es la versión editable (lo que Paulina diseña en UI)
    draft_json: Dict[str, Any]

    versions: list["WorkflowVersion"] = Relationship(back_populates="workflow")

class WorkflowVersion(SQLModel, Timestamped, table=True):
    id: str = Field(primary_key=True, index=True)
    workflow_id: str = Field(foreign_key="workflow.id", index=True)
    version: int = Field(index=True)
    # snapshot inmutable que ejecutará el worker
    content_json: Dict[str, Any]
    checksum: Optional[str] = Field(default=None, index=True)  # p.ej. sha256(content_json)

    workflow: Workflow = Relationship(back_populates="versions")
