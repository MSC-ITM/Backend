from typing import Optional, Dict, Any
from sqlmodel import SQLModel, Field
from enum import Enum
from .base import Timestamped

class ArtifactKind(str, Enum):
    generic = "generic"
    http_response = "http_response"
    file = "file"
    image = "image"
    json = "json"

class Artifact(SQLModel, Timestamped, table=True):
    id: str = Field(primary_key=True, index=True)
    org_id: str = Field(index=True)
    run_id: Optional[str] = Field(default=None, foreign_key="run.id", index=True)
    step_id: Optional[str] = Field(default=None, foreign_key="runstep.id", index=True)

    name: str
    kind: ArtifactKind = Field(default=ArtifactKind.generic, index=True)

    # Dónde lo almacenó el worker (S3, FS, etc.)
    uri: Optional[str] = None
    size_bytes: Optional[int] = None
    meta: Optional[Dict[str, Any]] = None
