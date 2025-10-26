# src/main.py
# Updated to support flexible authentication

# Cargar variables de entorno desde .env
from dotenv import load_dotenv
load_dotenv()

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4
from fastapi import FastAPI, Header, HTTPException, status, Depends, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, ConfigDict, Field
from copy import deepcopy
from math import exp
from datetime import datetime, UTC
from sqlmodel import SQLModel, Field as SQLField, Session, select
import json
from . import ia_client
from typing import Optional


app = FastAPI(title="Workflow API", version="0.1.0")

# Security scheme for Swagger UI
security = HTTPBearer(auto_error=False)

# Función auxiliar para validar token
async def validate_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security)
) -> str:
    """
    Valida que el token sea válido (empiece con 'mock-').
    Compatible con Swagger UI (HTTPBearer) y peticiones directas con Authorization header.
    Retorna el token si es válido, sino lanza excepción 401.
    """
    # Si no hay credenciales, error 401
    if not credentials:
        raise HTTPException(status_code=401, detail="Unauthorized")

    token = credentials.credentials

    # Validar que el token empiece con "mock-"
    if not token.startswith("mock-"):
        raise HTTPException(status_code=401, detail="Unauthorized")

    return token


# ---------------------------- Modelos API ----------------------------

class LoginRequest(BaseModel):
    username: str = Field(..., json_schema_extra={"example": "demo"})
    password: str = Field(..., json_schema_extra={"example": "demo123"})


class UserInfo(BaseModel):
    id: str = Field(..., json_schema_extra={"example": "c6c0a7b5-2f9c-4b45-b5b4-5f1e6d3b2f9a"})
    name: str = Field(..., json_schema_extra={"example": "Demo User"})


class LoginResponse(BaseModel):
    access_token: str = Field(..., json_schema_extra={"example": "mock-abcdef123"})
    token_type: str = Field(..., json_schema_extra={"example": "bearer"})
    user: UserInfo


class WorkflowCreate(BaseModel):
    name: str = Field(..., json_schema_extra={"example": "etl-sencillo"})
    definition: Dict[str, Any] = Field(
        default_factory=dict,
        json_schema_extra={"example": {"steps": [{"type": "HTTPS GET Request", "args": {"url": "https://..."}}]}},
    )


class WorkflowMinimal(BaseModel):
    id: str = Field(..., json_schema_extra={"example": "5ca2f9e3-9bd8-4b6e-9b66-5a2d8e8f8c2a"})
    status: str = Field(..., json_schema_extra={"example": "en_progreso"})


class WorkflowItem(BaseModel):
    id: str
    name: str
    status: str
    created_at: str

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "5ca2f9e3-9bd8-4b6e-9b66-5a2d8e8f8c2a",
                "name": "etl-sencillo",
                "status": "en_progreso",
                "created_at": "2025-10-24T00:00:00Z",
            }
        }
    )


# -------------------- Modelo de tabla SQLModel --------------------

class WorkflowTable(SQLModel, table=True):
    """
    Representa la tabla 'workflow' en SQLite. Guarda también la definición (JSON) para futuras funciones del worker.
    """
    id: str = SQLField(primary_key=True, index=True)
    name: str
    status: str
    created_at: str
    definition: Optional[str] = None  # JSON serializado como TEXT


# ---------------------- Modelos IA (sugerencias) ----------------------

class IASuggestionRequest(BaseModel):
    name: str = Field(..., json_schema_extra={"example": "etl-sencillo"})
    definition: Dict[str, Any] = Field(
        ...,
        json_schema_extra={
            "example": {
                "steps": [
                    {"type": "HTTPS GET Request", "args": {"url": "https://ejemplo.com/data.csv"}},
                    {"type": "Validate CSV File", "args": {"delimiter": ",", "columns": ["a", "b"]}},
                    {"type": "Simple Transform", "args": {"op": "uppercase", "field": "a"}},
                    {"type": "Save to Database", "args": {"table": "dest_tabla"}}
                ]
            }
        },
    )
    goals: Optional[List[str]] = Field(
        default=None,
        json_schema_extra={"example": ["rápido", "barato"]},
    )


class IASuggestionItem(BaseModel):
    kind: str = Field(..., json_schema_extra={"example": "add_node"})
    path: str = Field(..., json_schema_extra={"example": "steps[3]"})
    message: str = Field(..., json_schema_extra={"example": "Agregar nodo de salida 'Save to Database'."})
    confidence: float = Field(..., json_schema_extra={"example": 0.7})
    detail: Optional[Dict[str, Any]] = Field(
        default=None,
        json_schema_extra={
            "example": {"node": {"type": "Save to Database", "args": {"table": "dest_tabla"}}, "position": 3}
        },
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "kind": "parameter_hint",
                "path": "steps[0]",
                "message": "Configurar timeout en HTTPS GET Request.",
                "confidence": 0.6,
                "detail": {"hint": {"param": "timeout", "value": 10}},
            }
        }
    )


class IASuggestionResponse(BaseModel):
    suggestions: List[IASuggestionItem]
    rationale: str = Field(..., json_schema_extra={"example": "Reglas determinísticas básicas sobre orden y presencia de nodos."})
    confidence: float = Field(..., json_schema_extra={"example": 0.8})

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "suggestions": [
                    {
                        "kind": "reorder_nodes",
                        "path": "steps[2]",
                        "message": "Mover 'Validate CSV File' antes de 'Simple Transform'.",
                        "confidence": 0.75,
                        "detail": {"new_order": [0, 1, 2, 3]},
                    }
                ],
                "rationale": "Validar datos antes de transformar y asegurar nodo de salida.",
                "confidence": 0.8,
            }
        }
    )


# ---------------------- Modelos IA (fix) ----------------------

class IAFixRequest(BaseModel):
    name: str = Field(..., json_schema_extra={"example": "etl-sencillo"})
    definition: Dict[str, Any] = Field(
        ...,
        json_schema_extra={
            "example": {
                "steps": [
                    {"type": "HTTPS GET Request", "args": {"url": "https://ejemplo.com/data.csv"}},
                    {"type": "Simple Transform", "args": {"op": "uppercase", "field": "a"}}
                ]
            }
        },
    )
    logs: Optional[str] = Field(default=None, json_schema_extra={"example": "Error en paso 2 ..."})


class IAFixChangeItem(BaseModel):
    kind: str = Field(..., json_schema_extra={"example": "parameter_set"})
    path: str = Field(..., json_schema_extra={"example": "steps[0].args.timeout"})
    message: str = Field(..., json_schema_extra={"example": "Se estableció timeout=10 en HTTPS GET Request."})
    detail: Optional[Dict[str, Any]] = Field(
        default=None,
        json_schema_extra={"example": {"param": "timeout", "value": 10}},
    )


class IAFixResponse(BaseModel):
    patched_definition: Dict[str, Any]
    changes: List[IAFixChangeItem]
    rationale: str = Field(..., json_schema_extra={"example": "Correcciones determinísticas básicas."})
    confidence: float = Field(..., json_schema_extra={"example": 0.8})

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "patched_definition": {
                    "steps": [
                        {"type": "Validate CSV File", "args": {"delimiter": ",", "columns": ["a", "b"]}},
                        {"type": "Simple Transform", "args": {"op": "uppercase", "field": "a"}},
                        {"type": "Save to Database", "args": {"table": "dest_tabla"}}
                    ]
                },
                "changes": [
                    {"kind": "reorder_nodes", "path": "steps[1]", "message": "Reordenado Validate antes de Transform."},
                    {"kind": "add_node", "path": "steps[2]", "message": "Agregado nodo de salida."}
                ],
                "rationale": "Asegurar validación previa y salida definida.",
                "confidence": 0.8
            }
        }
    )


# ---------------------- Modelos IA (estimate) ----------------------

class IAEstimateRequest(BaseModel):
    name: str = Field(..., json_schema_extra={"example": "etl-sencillo"})
    definition: Dict[str, Any] = Field(
        ...,
        json_schema_extra={
            "example": {
                "steps": [
                    {"type": "HTTPS GET Request", "args": {"url": "https://ejemplo.com/data.csv"}},
                    {"type": "Validate CSV File", "args": {"delimiter": ",", "columns": ["a", "b"]}},
                    {"type": "Simple Transform", "args": {"op": "uppercase", "field": "a"}},
                    {"type": "Save to Database", "args": {"table": "dest_tabla"}}
                ]
            }
        },
    )
    goals: Optional[List[str]] = Field(default=None, json_schema_extra={"example": ["rápido", "barato"]})


class IAEstimateBreakdownItem(BaseModel):
    step_index: int = Field(..., json_schema_extra={"example": 0})
    type: str = Field(..., json_schema_extra={"example": "HTTPS GET Request"})
    time: float = Field(..., json_schema_extra={"example": 3.2})  # segundos
    cost: float = Field(..., json_schema_extra={"example": 0.001})  # costo relativo (mock)


class IAEstimateResponse(BaseModel):
    estimated_runtime_seconds: float = Field(..., json_schema_extra={"example": 12.5})
    estimated_cost: float = Field(..., json_schema_extra={"example": 0.003})
    complexity_score: float = Field(..., json_schema_extra={"example": 0.42})
    breakdown: List[IAEstimateBreakdownItem]
    rationale: str = Field(..., json_schema_extra={"example": "Estimación determinística basada en tipo y número de pasos."})
    confidence: float = Field(..., json_schema_extra={"example": 0.8})


# --------------------- Repositorio en memoria ---------------------

class InMemoryWorkflowRepo:
    """Repositorio simple en memoria para almacenar workflows durante la ejecución del proceso."""

    def __init__(self) -> None:
        self._store: Dict[str, WorkflowItem] = {}

    def create(self, name: str) -> WorkflowItem:
        wid = str(uuid4())
        item = WorkflowItem(
            id=wid,
            name=name,
            status="en_progreso",
            created_at = datetime.now(UTC).replace(microsecond=0).isoformat(),
        )
        self._store[wid] = item
        return item

    def get(self, wid: str) -> Optional[WorkflowItem]:
        return self._store.get(wid)

    def list(self) -> List[WorkflowItem]:
        return list(self._store.values())


_repo = InMemoryWorkflowRepo()


# --------------------- Repositorio SQLModel ---------------------

class SQLiteWorkflowRepo:
    """
    Implementación de repositorio usando SQLModel + SQLite (puede operar en memoria).
    Compatible con la interfaz del repositorio en memoria.
    """

    def __init__(self, engine):
        self.engine = engine

    def create_schema(self) -> None:
        """Crea las tablas necesarias en el motor proporcionado."""
        SQLModel.metadata.create_all(self.engine)

    def create(self, name: str, definition: Optional[Dict[str, Any]] = None) -> WorkflowItem:
        """Inserta un nuevo workflow y devuelve un WorkflowItem."""
        wid = str(uuid4())
        now = datetime.now(UTC).replace(microsecond=0).isoformat()

        with Session(self.engine) as session:
            record = WorkflowTable(
                id=wid,
                name=name,
                status="en_progreso",
                created_at=now,
                definition=json.dumps(definition or {}),
            )
            session.add(record)
            session.commit()
        return WorkflowItem(id=wid, name=name, status="en_progreso", created_at=now)

    def get(self, wid: str) -> Optional[WorkflowItem]:
        """Obtiene un workflow por ID, o None si no existe."""
        with Session(self.engine) as session:
            stmt = select(WorkflowTable).where(WorkflowTable.id == wid)
            record = session.exec(stmt).first()
            if not record:
                return None
            return WorkflowItem(
                id=record.id,
                name=record.name,
                status=record.status,
                created_at=record.created_at,
            )

    def list(self) -> List[WorkflowItem]:
        """Devuelve todos los workflows registrados."""
        with Session(self.engine) as session:
            records = session.exec(select(WorkflowTable)).all()
            return [
                WorkflowItem(
                    id=r.id,
                    name=r.name,
                    status=r.status,
                    created_at=r.created_at,
                )
                for r in records
            ]


# ----------------------------- Proxy -----------------------------

class AuthProxy:
    """Proxy de autenticación que valida el token y delega operaciones al repositorio."""

    def __init__(self, repo: InMemoryWorkflowRepo) -> None:
        self._repo = repo

    def _validate_token(self, authorization: Optional[str]) -> None:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing or invalid token")
        token = authorization.split(" ", 1)[1].strip()
        if not token.startswith("mock-"):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    def create_workflow(self, authorization: Optional[str], name: str) -> WorkflowMinimal:
        self._validate_token(authorization)
        item = self._repo.create(name=name)
        return WorkflowMinimal(id=item.id, status=item.status)

    def get_workflow_status(self, authorization: Optional[str], wid: str) -> WorkflowMinimal:
        self._validate_token(authorization)
        item = self._repo.get(wid)
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")
        return WorkflowMinimal(id=item.id, status=item.status)

    def list_workflows(self, authorization: Optional[str]) -> List[WorkflowItem]:
        self._validate_token(authorization)
        return self._repo.list()


proxy = AuthProxy(_repo)


# --------------------------- Endpoints ---------------------------

@app.post("/login", response_model=LoginResponse, tags=["auth"])
def login(payload: LoginRequest) -> LoginResponse:
    """
    Autenticación de ejemplo:
    - username: demo
    - password: demo123
    """
    if not (payload.username == "demo" and payload.password == "demo123"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    user_id = str(uuid4())
    return LoginResponse(
        access_token="mock-" + str(uuid4()).replace("-", "")[:12],
        token_type="bearer",
        user=UserInfo(id=user_id, name="Demo User"),
    )


@app.post("/workflow", response_model=WorkflowMinimal, status_code=status.HTTP_201_CREATED, tags=["workflows"])
def create_workflow(req: WorkflowCreate, authorization: Optional[str] = Header(default=None)) -> WorkflowMinimal:
    return proxy.create_workflow(authorization=authorization, name=req.name)


@app.get("/workflows/{id}/status", response_model=WorkflowMinimal, tags=["workflows"])
def get_workflow_status(id: str, authorization: Optional[str] = Header(default=None)) -> WorkflowMinimal:
    return proxy.get_workflow_status(authorization=authorization, wid=id)


@app.get("/workflows", response_model=List[WorkflowItem], tags=["workflows"])
def list_workflows(authorization: Optional[str] = Header(default=None)) -> List[WorkflowItem]:
    return proxy.list_workflows(authorization=authorization)


# ------------------------- Endpoint IA -------------------------

@app.post("/ia/suggestion", response_model=IASuggestionResponse, tags=["ia"])
async def ia_suggestion(
    payload: IASuggestionRequest,
    token: str = Depends(validate_token),
) -> IASuggestionResponse:
    """
    Devuelve sugerencias generadas por el agente IA usando Gemini.

    Raises:
        HTTPException: 500 si la API de IA falla después de 3 reintentos
    """
    try:
        client = ia_client.get_ia_client()
        result = client.suggest(payload.definition)

        # Mapeo de la respuesta del cliente al modelo de respuesta de la API
        suggestions_list = []
        for change in result.get("suggested_changes", []):
            suggestions_list.append(
                IASuggestionItem(
                    kind=change.get("op", "unknown"),
                    path=f"steps[{change.get('target_step_index', -1)}]",
                    message=change.get("reason", "No message provided."),
                    confidence=0.5,
                    detail={"arg_name": change.get("arg_name"), "arg_value": change.get("arg_value")},
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
            detail=f"Error al obtener sugerencias de la API de IA después de múltiples intentos: {str(e)}"
        )


@app.post("/ia/fix", response_model=IAFixResponse, tags=["ia"])
async def ia_fix(
    payload: IAFixRequest,
    token: str = Depends(validate_token),
) -> IAFixResponse:
    """
    Devuelve una versión corregida del workflow usando Gemini.

    Raises:
        HTTPException: 500 si la API de IA falla después de 3 reintentos
    """
    try:
        client = ia_client.get_ia_client()
        result = client.fix(payload.definition, payload.logs)

        # Mapear la respuesta del cliente al modelo de respuesta de la API
        changes_list = []
        for note in result.get("notes", []):
            # Parsear las notas para crear cambios estructurados
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
            rationale=". ".join(result.get("notes", [])) if result.get("notes") else "Correcciones aplicadas por IA.",
            confidence=0.9,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener correcciones de la API de IA después de múltiples intentos: {str(e)}"
        )


@app.post("/ia/estimate", response_model=IAEstimateResponse, tags=["ia"])
async def ia_estimate(
    payload: IAEstimateRequest,
    token: str = Depends(validate_token),
) -> IAEstimateResponse:
    """
    Devuelve una estimación de tiempo y costo del workflow usando Gemini.

    Raises:
        HTTPException: 500 si la API de IA falla después de 3 reintentos
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
            detail=f"Error al obtener estimación de la API de IA después de múltiples intentos: {str(e)}"
        )
