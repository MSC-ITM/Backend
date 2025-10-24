from typing import Optional, Dict, Any
from sqlmodel import SQLModel, Field
from enum import Enum
from .base import Timestamped

class TriggerType(str, Enum):
    http = "http"       # webhook
    schedule = "schedule"  # cron
    event = "event"     # pub/sub u otro

class Trigger(SQLModel, Timestamped, table=True):
    id: str = Field(primary_key=True, index=True)
    org_id: str = Field(index=True)
    workflow_id: str = Field(foreign_key="workflow.id", index=True)

    type: TriggerType
    config: Dict[str, Any]  # p.ej. cron expr, secrets, path del webhook
    enabled: bool = Field(default=True, index=True)

    last_fired_at: Optional[str] = None  # ISO string o datetime si prefieres
