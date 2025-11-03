"""
Integrated Backend API
Connects Frontend (Steps+Edges format) with Worker (Nodes+depends_on format)
"""

from dotenv import load_dotenv
load_dotenv()

import os
from datetime import datetime, UTC
from typing import List, Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Depends, Security, UploadFile, File
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import create_engine

# Import our models
from .models import (
    # Auth models
    LoginRequest,
    LoginResponse,
    UserInfo,
    # Task Types
    TaskType,
    # Workflows
    Workflow,
    WorkflowListItem,
    WorkflowDetailDTO,
    CreateWorkflowDTO,
    UpdateWorkflowDTO,
    # Runs
    Run,
    RunDetailDTO,
    LogEntry,
    GetLogsOptions,
    # IA models
    IASuggestionRequest,
    IASuggestionResponse,
    IASuggestionItem,
    IAFixRequest,
    IAFixResponse,
    IAFixChangeItem,
    IAEstimateRequest,
    IAEstimateResponse,
    IAEstimateBreakdownItem,
)

from .repository import WorkflowRepository
from . import ia_client


# ============================================================================
# App Configuration
# ============================================================================

app = FastAPI(
    title="Workflow Orchestration API",
    version="1.0.0",
    description="Integrated Backend API for Frontend and Worker communication"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer(auto_error=False)


# ============================================================================
# Database Configuration (Shared with Worker)
# ============================================================================

# Use Worker's database path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "data", "workflows.db")

# Ensure data directory exists
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

DATABASE_URL = f"sqlite:///{DB_PATH}"
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False  # Set to True for SQL debugging
)

# Initialize repository
repo = WorkflowRepository(engine)
repo.create_schema()

print(f"[Backend] Using shared database: {DB_PATH}")


# ============================================================================
# Authentication
# ============================================================================

async def validate_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security)
) -> str:
    """
    Validate bearer token.
    For demo: accepts tokens starting with 'mock-'
    """
    if not credentials:
        raise HTTPException(status_code=401, detail="Unauthorized")

    token = credentials.credentials

    if not token.startswith("mock-"):
        raise HTTPException(status_code=401, detail="Unauthorized")

    return token


# ============================================================================
# Authentication Endpoints
# ============================================================================

@app.post("/login", response_model=LoginResponse, tags=["auth"])
def login(payload: LoginRequest) -> LoginResponse:
    """
    Mock authentication endpoint.
    Accepts username='demo', password='demo123'
    """
    if not (payload.username == "demo" and payload.password == "demo123"):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    user_id = str(uuid4())
    return LoginResponse(
        access_token=f"mock-{uuid4().hex[:12]}",
        token_type="bearer",
        user=UserInfo(id=user_id, name="Demo User"),
    )


# ============================================================================
# Task Types Endpoints
# ============================================================================

@app.get("/task-types", response_model=List[TaskType], tags=["task-types"])
async def get_task_types(token: str = Depends(validate_token)) -> List[TaskType]:
    """
    Get catalog of available task types.
    These correspond to the strategies implemented in the Worker.
    """
    task_types = [
        TaskType(
            type="http_get",
            display_name="Petición HTTP GET",
            version="1.0.0",
            params_schema={
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "headers": {"type": "object"},
                },
                "required": ["url"],
            },
        ),
        TaskType(
            type="validate_csv",
            display_name="Validar Archivo CSV",
            version="1.0.0",
            params_schema={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string"},
                    "columns": {"type": "array"},
                    "delimiter": {"type": "string"},
                },
                "required": ["file_path", "columns"],
            },
        ),
        TaskType(
            type="transform_simple",
            display_name="Transformación Simple",
            version="1.0.0",
            params_schema={
                "type": "object",
                "properties": {
                    "operations": {"type": "array"},
                },
                "required": ["operations"],
            },
        ),
        TaskType(
            type="save_db",
            display_name="Guardar en Base de Datos",
            version="1.0.0",
            params_schema={
                "type": "object",
                "properties": {
                    "table": {"type": "string"},
                    "mode": {"type": "string", "enum": ["append", "replace"]},
                },
                "required": ["table"],
            },
        ),
        TaskType(
            type="notify_mock",
            display_name="Notificación de Prueba",
            version="1.0.0",
            params_schema={
                "type": "object",
                "properties": {
                    "channel": {"type": "string"},
                    "message": {"type": "string"},
                },
                "required": ["channel", "message"],
            },
        ),
    ]
    return task_types


# ============================================================================
# Workflow Endpoints
# ============================================================================

@app.post("/workflows", response_model=WorkflowDetailDTO, status_code=201, tags=["workflows"])
async def create_workflow(
    data: CreateWorkflowDTO,
    token: str = Depends(validate_token)
) -> WorkflowDetailDTO:
    """
    Create a new workflow.
    Converts Frontend format (steps + edges) to Worker format (nodes with depends_on).
    """
    return repo.create_workflow(data)


@app.get("/workflows", response_model=List[WorkflowListItem], tags=["workflows"])
async def list_workflows(token: str = Depends(validate_token)) -> List[WorkflowListItem]:
    """Get list of all workflows"""
    return repo.list_workflows()


@app.get("/workflows/{id}", response_model=WorkflowDetailDTO, tags=["workflows"])
async def get_workflow(id: str, token: str = Depends(validate_token)) -> WorkflowDetailDTO:
    """Get workflow by ID with steps and edges"""
    workflow = repo.get_workflow(id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow


@app.put("/workflows/{id}", response_model=WorkflowDetailDTO, tags=["workflows"])
async def update_workflow(
    id: str,
    data: UpdateWorkflowDTO,
    token: str = Depends(validate_token)
) -> WorkflowDetailDTO:
    """Update workflow"""
    workflow = repo.update_workflow(id, data)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow


@app.delete("/workflows/{id}", status_code=204, tags=["workflows"])
async def delete_workflow(id: str, token: str = Depends(validate_token)):
    """Delete workflow"""
    success = repo.delete_workflow(id)
    if not success:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return None


# ============================================================================
# Workflow Execution Endpoints
# ============================================================================

@app.post("/workflows/{id}/runs", response_model=Run, tags=["runs"])
async def trigger_workflow(id: str, token: str = Depends(validate_token)) -> Run:
    """
    Trigger workflow execution.
    Sets workflow status to 'en_espera' so Worker picks it up.
    """
    run = repo.trigger_workflow(id)
    if not run:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return run


@app.get("/workflows/{workflow_id}/runs", response_model=List[Run], tags=["runs"])
async def get_workflow_runs(
    workflow_id: str,
    token: str = Depends(validate_token)
) -> List[Run]:
    """Get execution history for a workflow"""
    return repo.get_workflow_runs(workflow_id)


@app.get("/runs/{run_id}", response_model=RunDetailDTO, tags=["runs"])
async def get_run_detail(run_id: str, token: str = Depends(validate_token)) -> RunDetailDTO:
    """Get run details with task instances"""
    run_detail = repo.get_run_detail(run_id)
    if not run_detail:
        raise HTTPException(status_code=404, detail="Run not found")
    return run_detail


@app.get("/runs/{run_id}/logs", response_model=List[LogEntry], tags=["runs"])
async def get_run_logs(
    run_id: str,
    task: Optional[str] = None,
    page: int = 1,
    limit: int = 100,
    token: str = Depends(validate_token)
) -> List[LogEntry]:
    """
    Get logs for a run.
    Generates synthetic logs from noderun data since Worker doesn't expose structured logs yet.
    """
    return repo.get_run_logs(run_id, task)


@app.post("/runs/{run_id}/cancel", response_model=Run, tags=["runs"])
async def cancel_run(run_id: str, token: str = Depends(validate_token)) -> Run:
    """
    Cancel a running workflow.
    Currently not implemented - Worker doesn't support cancellation yet.
    """
    raise HTTPException(status_code=501, detail="Cancellation not implemented")


# ============================================================================
# IA Service Endpoints
# ============================================================================

@app.post("/ia/suggestion", response_model=IASuggestionResponse, tags=["ia"])
async def ia_suggestion(
    payload: IASuggestionRequest,
    token: str = Depends(validate_token),
) -> IASuggestionResponse:
    """
    Get AI suggestions for workflow improvement.
    Uses Gemini API for intelligent analysis.
    """
    try:
        client = ia_client.get_ia_client()
        result = client.suggest(payload.definition)

        suggestions_list = []
        for change in result.get("suggested_changes", []):
            # Construir detail basado en el tipo de operación
            detail = {}
            if change.get("op") == "add_arg" or change.get("op") == "modify_arg":
                detail = {
                    "arg_name": change.get("arg_name"),
                    "arg_value": change.get("arg_value")
                }
            elif change.get("op") == "add_node":
                detail = {"node": change.get("node")}
            elif change.get("op") == "reorder":
                detail = change.get("detail", {})
            else:
                detail = change.get("detail", {})

            suggestions_list.append(
                IASuggestionItem(
                    kind=change.get("op", "unknown"),
                    path=f"steps[{change.get('target_step_index', -1)}]",
                    message=change.get("reason", change.get("message", "Optimización sugerida")),
                    confidence=change.get("confidence", 0.75),
                    detail=detail,
                )
            )

        return IASuggestionResponse(
            suggestions=suggestions_list,
            rationale=result.get("rationale", ""),
            confidence=result.get("confidence", 0.0),
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error getting AI suggestions: {str(e)}"
        )


@app.post("/ia/fix", response_model=IAFixResponse, tags=["ia"])
async def ia_fix(
    payload: IAFixRequest,
    token: str = Depends(validate_token),
) -> IAFixResponse:
    """
    Get AI fixes for workflow errors.
    Uses Gemini API to analyze and fix issues.
    """
    try:
        client = ia_client.get_ia_client()
        result = client.fix(payload.definition, payload.logs)

        changes_list = []
        for note in result.get("notes", []):
            if "timeout" in note.lower():
                changes_list.append(
                    IAFixChangeItem(
                        kind="parameter_set",
                        path="steps[*].args.timeout",
                        message=note,
                        detail={"param": "timeout", "value": 10}
                    )
                )
            elif "salida" in note.lower() or "notification" in note.lower():
                changes_list.append(
                    IAFixChangeItem(
                        kind="add_node",
                        path="steps[-1]",
                        message=note,
                        detail={"node": {"type": "Mock Notification"}}
                    )
                )
            elif "reorden" in note.lower():
                changes_list.append(
                    IAFixChangeItem(
                        kind="reorder_nodes",
                        path="steps",
                        message=note,
                        detail={}
                    )
                )
            else:
                changes_list.append(
                    IAFixChangeItem(
                        kind="parameter_set",
                        path="unknown",
                        message=note,
                        detail={}
                    )
                )

        return IAFixResponse(
            patched_definition=result.get("patched_definition", payload.definition),
            changes=changes_list,
            rationale=". ".join(result.get("notes", [])) if result.get("notes") else "Fixes applied by AI.",
            confidence=0.9,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error getting AI fixes: {str(e)}"
        )


@app.post("/ia/estimate", response_model=IAEstimateResponse, tags=["ia"])
async def ia_estimate(
    payload: IAEstimateRequest,
    token: str = Depends(validate_token),
) -> IAEstimateResponse:
    """
    Get AI estimation for workflow execution.
    Uses Gemini API to estimate time and cost.
    """
    try:
        client = ia_client.get_ia_client()
        result = client.estimate(payload.definition)
        return IAEstimateResponse(
            estimated_runtime_seconds=result.get("estimated_time_seconds", 0.0),
            estimated_cost=result.get("estimated_cost_usd", 0.0),
            complexity_score=result.get("complexity_score", 0.0),
            breakdown=result.get("breakdown", []),
            rationale=result.get("assumptions", [""])[0] if result.get("assumptions") else "",
            confidence=result.get("confidence", 0.0),
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error getting AI estimation: {str(e)}"
        )


# ============================================================================
# Health Check
# ============================================================================

@app.get("/health", tags=["health"])
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(UTC).isoformat(),
        "database": "connected",
        "database_path": DB_PATH
    }


# ============================================================================
# FILE UPLOAD ENDPOINTS
# ============================================================================

@app.post("/files/upload-csv", tags=["files"])
async def upload_csv(
    file: UploadFile = File(...),
    token: str = Depends(validate_token)
):
    """
    Upload a CSV file to the server for use in workflows.
    Returns the path where the file was saved.
    """
    # Validate file type
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed")

    # Create uploads directory if it doesn't exist
    upload_dir = os.path.join(os.path.dirname(DB_PATH), "uploads")
    os.makedirs(upload_dir, exist_ok=True)

    # Generate unique filename
    file_id = uuid4().hex[:8]
    safe_filename = f"{file_id}_{file.filename}"
    file_path = os.path.join(upload_dir, safe_filename)

    # Save file
    try:
        contents = await file.read()
        with open(file_path, "wb") as f:
            f.write(contents)

        return {
            "success": True,
            "filename": safe_filename,
            "path": file_path,
            "size": len(contents),
            "original_name": file.filename
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error saving file: {str(e)}")

