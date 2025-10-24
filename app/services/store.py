# app/services/store.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any

@dataclass
class WorkflowObj:
    id: str
    name: str
    status: str  # draft|published|archived
    version: int
    payload: Dict[str, Any] = field(default_factory=dict)

WORKFLOWS: Dict[str, WorkflowObj] = {}
PUBLISHED: set[str] = set()
