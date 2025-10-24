from datetime import datetime
from sqlmodel import SQLModel, Field
from typing import Optional, Dict, Any

class Workflow(SQLModel, table=True):
    id: str = Field(primary_key=True)
    org_id: str
    name: str
    status: str  # draft|published|archived
    draft_json: Dict[str, Any] = Field(sa_column_kwargs={"nullable": False})
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class WorkflowVersion(SQLModel, table=True):
    id: str = Field(primary_key=True)
    workflow_id: str = Field(foreign_key="workflow.id")
    version: int
    content_json: Dict[str, Any] = Field(sa_column_kwargs={"nullable": False})
    created_at: datetime = Field(default_factory=datetime.utcnow)
