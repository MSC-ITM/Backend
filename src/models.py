"""
Backend Data Models
Integrates Frontend (Steps+Edges) with Worker (Nodes+depends_on)
"""

from sqlmodel import SQLModel, Field
from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime


# ============================================================================
# SHARED DATABASE MODELS (Shared with Worker)
# ============================================================================

class WorkflowTable(SQLModel, table=True):
    """
    Shared table between Backend API and Worker.
    Worker polls this table for workflows with status='en_espera'.
    Uses Worker's nomenclature and format.
    """
    __tablename__ = "workflowtable"

    id: str = Field(primary_key=True)
    name: str
    status: str  # "en_espera", "en_progreso", "completado", "fallido"
    created_at: str  # ISO timestamp
    updated_at: str  # ISO timestamp
    definition: Optional[str] = None  # JSON with nodes (Worker format)


# ============================================================================
# BACKEND-SPECIFIC MODELS (Frontend format storage)
# ============================================================================

class WorkflowMetadata(SQLModel, table=True):
    """
    Additional workflow metadata not used by Worker.
    Stores Frontend-specific fields.
    """
    __tablename__ = "workflow_metadata"

    id: str = Field(primary_key=True, foreign_key="workflowtable.id")
    description: str = ""
    schedule_cron: Optional[str] = None
    active: bool = True


class StepTable(SQLModel, table=True):
    """
    Stores individual workflow steps (Frontend format).
    Converted to Worker's 'nodes' format when executing.
    """
    __tablename__ = "steps"

    id: str = Field(primary_key=True)
    workflow_id: str = Field(foreign_key="workflowtable.id")
    node_key: str  # Stable node identifier
    type: str  # Task type (http_get, validate_csv, etc.)
    params: str  # JSON serialized parameters


class EdgeTable(SQLModel, table=True):
    """
    Stores workflow edges (Frontend format).
    Converted to Worker's 'depends_on' arrays when executing.
    """
    __tablename__ = "edges"

    id: str = Field(primary_key=True)
    workflow_id: str = Field(foreign_key="workflowtable.id")
    from_node_key: str  # Source node
    to_node_key: str  # Target node


# ============================================================================
# PYDANTIC MODELS (API DTOs)
# ============================================================================

# --- Authentication ---

class LoginRequest(BaseModel):
    username: str
    password: str


class UserInfo(BaseModel):
    id: str
    name: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserInfo


# --- Task Types ---

class TaskType(BaseModel):
    """Task type definition (catalog)"""
    type: str
    display_name: str
    version: str
    params_schema: Dict[str, Any]


# --- Workflows ---

class Workflow(BaseModel):
    """Workflow entity (Frontend format)"""
    id: str
    name: str
    description: str
    schedule_cron: Optional[str] = None
    active: bool
    created_at: str


class StepDTO(BaseModel):
    """Step DTO for API (without id for creation)"""
    node_key: str
    type: str
    params: Dict[str, Any]


class StepResponse(BaseModel):
    """Step response (with id)"""
    id: str
    workflow_id: str
    node_key: str
    type: str
    params: Dict[str, Any]


class EdgeDTO(BaseModel):
    """Edge DTO for API (without id for creation)"""
    from_node_key: str
    to_node_key: str


class EdgeResponse(BaseModel):
    """Edge response (with id)"""
    id: str
    workflow_id: str
    from_node_key: str
    to_node_key: str


class CreateWorkflowDTO(BaseModel):
    """Request to create a workflow"""
    name: str
    description: str = ""
    schedule_cron: Optional[str] = None
    steps: List[StepDTO]
    edges: List[EdgeDTO]


class UpdateWorkflowDTO(BaseModel):
    """Request to update a workflow"""
    name: Optional[str] = None
    description: Optional[str] = None
    schedule_cron: Optional[str] = None
    active: Optional[bool] = None
    steps: Optional[List[StepDTO]] = None
    edges: Optional[List[EdgeDTO]] = None


class WorkflowDetailDTO(BaseModel):
    """Workflow with steps and edges"""
    workflow: Workflow
    steps: List[StepResponse]
    edges: List[EdgeResponse]


class WorkflowListItem(BaseModel):
    """Workflow summary for list view"""
    id: str
    name: str
    description: str
    schedule_cron: Optional[str] = None
    active: bool
    created_at: str


# --- Runs (Executions) ---

class Run(BaseModel):
    """Workflow execution run"""
    id: str
    workflow_id: str
    state: str  # "Pending", "Running", "Succeeded", "Failed", "Canceled"
    started_at: Optional[str] = None
    finished_at: Optional[str] = None


class TaskInstance(BaseModel):
    """Individual task execution within a run"""
    id: str
    run_id: str
    node_key: str
    type: str
    state: str  # "Pending", "Running", "Succeeded", "Failed", "Retry"
    try_count: int = 0
    max_retries: int = 3
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    error: Optional[str] = None


class RunDetailDTO(BaseModel):
    """Run with task instances"""
    run: Run
    tasks: List[TaskInstance]


# --- Logs ---

class LogEntry(BaseModel):
    """Log entry for run execution"""
    id: str
    run_id: str
    task_instance_id: Optional[str] = None
    level: str  # "INFO", "WARNING", "ERROR", "DEBUG"
    message: str
    ts: str  # ISO timestamp


class GetLogsOptions(BaseModel):
    """Options for fetching logs"""
    task: Optional[str] = None
    page: int = 1
    limit: int = 100


# --- AI Services ---

class IASuggestionRequest(BaseModel):
    name: str
    definition: Dict[str, Any]
    goals: Optional[List[str]] = None


class IASuggestionItem(BaseModel):
    kind: str
    path: str
    message: str
    confidence: float
    detail: Optional[Dict[str, Any]] = None


class IASuggestionResponse(BaseModel):
    suggestions: List[IASuggestionItem]
    rationale: str
    confidence: float


class IAFixRequest(BaseModel):
    name: str
    definition: Dict[str, Any]
    logs: Optional[str] = None


class IAFixChangeItem(BaseModel):
    kind: str
    path: str
    message: str
    detail: Optional[Dict[str, Any]] = None


class IAFixResponse(BaseModel):
    patched_definition: Dict[str, Any]
    changes: List[IAFixChangeItem]
    rationale: str
    confidence: float


class IAEstimateRequest(BaseModel):
    name: str
    definition: Dict[str, Any]
    goals: Optional[List[str]] = None


class IAEstimateBreakdownItem(BaseModel):
    step_index: int
    type: str
    time: float
    cost: float


class IAEstimateResponse(BaseModel):
    estimated_runtime_seconds: float
    estimated_cost: float
    complexity_score: float
    breakdown: List[IAEstimateBreakdownItem]
    rationale: str
    confidence: float
