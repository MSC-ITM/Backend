# src/main.py
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4
from fastapi import FastAPI, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from copy import deepcopy
from math import exp
from datetime import datetime, UTC
from sqlmodel import SQLModel, Field as SQLField, Session, select
import json


app = FastAPI(title="Workflow API", version="0.1.0")


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


# ------------------------- Endpoint IA (mock) -------------------------

@app.post(
    "/ia/suggestion",
    response_model=IASuggestionResponse,
    tags=["ia"],
    responses={
        200: {
            "description": "Sugerencias generadas.",
            "content": {
                "application/json": {
                    "examples": {
                        "ok_add_output_and_timeout": {
                            "summary": "Sugerencias típicas (agregar salida y timeout)",
                            "value": {
                                "suggestions": [
                                    {
                                        "kind": "add_node",
                                        "path": "steps[3]",
                                        "message": "Agregar nodo de salida ('Save to Database' o 'Mock Notification').",
                                        "confidence": 0.75,
                                        "detail": {
                                            "node": {"type": "Save to Database", "args": {"table": "dest_tabla"}},
                                            "position": 3
                                        }
                                    },
                                    {
                                        "kind": "parameter_hint",
                                        "path": "steps[0]",
                                        "message": "Configurar 'timeout' en HTTPS GET Request.",
                                        "confidence": 0.6,
                                        "detail": {"hint": {"param": "timeout", "value": 10}}
                                    }
                                ],
                                "rationale": "Reglas determinísticas básicas sobre orden y presencia de nodos.",
                                "confidence": 0.8
                            }
                        }
                    }
                }
            }
        },
        400: {
            "description": "Cuerpo inválido.",
            "content": {
                "application/json": {
                    "examples": {
                        "bad_body": {
                            "summary": "Body sin 'definition'",
                            "value": {"detail": "Unprocessable Entity"}
                        }
                    }
                }
            }
        },
        401: {
            "description": "No autorizado.",
            "content": {
                "application/json": {
                    "examples": {
                        "missing_or_invalid": {
                            "summary": "Falta Authorization o formato inválido",
                            "value": {"detail": "Missing or invalid token"}
                        },
                        "wrong_prefix": {
                            "summary": "Token no mock-*",
                            "value": {"detail": "Unauthorized"}
                        }
                    }
                }
            }
        },
    },
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "examples": {
                        "minimal": {
                            "summary": "Entrada mínima",
                            "value": {
                                "name": "etl-sencillo",
                                "definition": {
                                    "steps": [
                                        {"type": "HTTPS GET Request", "args": {"url": "https://ejemplo.com/data.csv"}},
                                        {"type": "Validate CSV File", "args": {"delimiter": ",", "columns": ["a","b"]}},
                                        {"type": "Simple Transform", "args": {"op": "uppercase", "field": "a"}}
                                    ]
                                },
                                "goals": ["rápido","barato"]
                            }
                        }
                    }
                }
            }
        }
    }
)
def ia_suggestion(req: IASuggestionRequest, authorization: Optional[str] = Header(default=None)) -> IASuggestionResponse:
    """
    Sugerencias determinísticas de ejemplo basadas en la presencia y orden de nodos.
    Requiere Authorization: Bearer mock-*.
    """
    proxy._validate_token(authorization)

    steps = req.definition.get("steps", [])
    types = [s.get("type") for s in steps if isinstance(s, dict)]
    suggestions: List[IASuggestionItem] = []

    has_output = any(t in ("Save to Database", "Mock Notification") for t in types)
    if not has_output:
        suggestions.append(
            IASuggestionItem(
                kind="add_node",
                path=f"steps[{max(len(steps), 0)}]",
                message="Agregar nodo de salida ('Save to Database' o 'Mock Notification').",
                confidence=0.75,
                detail={"node": {"type": "Save to Database", "args": {"table": "dest_tabla"}}, "position": len(steps)},
            )
        )

    if "Simple Transform" in types and "Validate CSV File" in types:
        idx_transform = types.index("Simple Transform")
        idx_validate = types.index("Validate CSV File")
        if idx_validate > idx_transform:
            suggestions.append(
                IASuggestionItem(
                    kind="reorder_nodes",
                    path=f"steps[{idx_validate}]",
                    message="Colocar 'Validate CSV File' antes de 'Simple Transform'.",
                    confidence=0.7,
                    detail={"new_order": list(range(len(steps)))},
                )
            )

    if "HTTPS GET Request" in types:
        idx_get = types.index("HTTPS GET Request")
        suggestions.append(
            IASuggestionItem(
                kind="parameter_hint",
                path=f"steps[{idx_get}]",
                message="Configurar 'timeout' en HTTPS GET Request.",
                confidence=0.6,
                detail={"hint": {"param": "timeout", "value": 10}},
            )
        )

    if not suggestions:
        suggestions.append(
            IASuggestionItem(
                kind="validation_issue",
                path="steps",
                message="Sin hallazgos relevantes; validar consistencia general.",
                confidence=0.5,
                detail={},
            )
        )

    return IASuggestionResponse(
        suggestions=suggestions,
        rationale="Reglas determinísticas básicas sobre orden y presencia de nodos.",
        confidence=0.8,
    )

@app.post(
    "/ia/fix",
    response_model=IAFixResponse,
    tags=["ia"],
    responses={
        200: {
            "description": "Definición corregida y lista de cambios.",
            "content": {
                "application/json": {
                    "examples": {
                        "fix_reorder_and_add_output": {
                            "summary": "Reordenar Validate y agregar salida",
                            "value": {
                                "patched_definition": {
                                    "steps": [
                                        {"type": "Validate CSV File", "args": {"delimiter": ",", "columns": ["a","b"]}},
                                        {"type": "Simple Transform", "args": {"op": "uppercase", "field": "a"}},
                                        {"type": "Save to Database", "args": {"table": "dest_tabla"}}
                                    ]
                                },
                                "changes": [
                                    {
                                        "kind": "reorder_nodes",
                                        "path": "steps[1]",
                                        "message": "Reordenado 'Validate CSV File' antes de 'Simple Transform'."
                                    },
                                    {
                                        "kind": "add_node",
                                        "path": "steps[2]",
                                        "message": "Agregado nodo de salida 'Save to Database'.",
                                        "detail": {"node": {"type": "Save to Database", "args": {"table": "dest_tabla"}}, "position": 2}
                                    }
                                ],
                                "rationale": "Correcciones determinísticas básicas sobre orden, parámetros y salida.",
                                "confidence": 0.8
                            }
                        }
                    }
                }
            }
        },
        400: {
            "description": "Cuerpo inválido.",
            "content": {
                "application/json": {
                    "examples": {
                        "bad_body": {
                            "summary": "Body sin 'steps'",
                            "value": {"detail": "Unprocessable Entity"}
                        }
                    }
                }
            }
        },
        401: {
            "description": "No autorizado.",
            "content": {
                "application/json": {
                    "examples": {
                        "missing_or_invalid": {
                            "summary": "Falta Authorization o formato inválido",
                            "value": {"detail": "Missing or invalid token"}
                        },
                        "wrong_prefix": {
                            "summary": "Token no mock-*",
                            "value": {"detail": "Unauthorized"}
                        }
                    }
                }
            }
        },
    },
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "examples": {
                        "needs_reorder_and_output": {
                            "summary": "Transform antes de Validate y sin salida",
                            "value": {
                                "name": "etl-sencillo",
                                "definition": {
                                    "steps": [
                                        {"type": "Simple Transform", "args": {"op": "uppercase", "field": "a"}},
                                        {"type": "Validate CSV File", "args": {"delimiter": ",", "columns": ["a","b"]}}
                                    ]
                                },
                                "logs": "optional context"
                            }
                        }
                    }
                }
            }
        }
    }
)
def ia_fix(req: IAFixRequest, authorization: Optional[str] = Header(default=None)) -> IAFixResponse:
    """
    Aplica correcciones determinísticas mínimas:
    - Agrega nodo de salida si falta.
    - Reordena 'Validate CSV File' antes de 'Simple Transform' si están invertidos.
    - Establece timeout=10 en 'HTTPS GET Request' si falta.
    """
    proxy._validate_token(authorization)

    patched = deepcopy(req.definition) if isinstance(req.definition, dict) else {"steps": []}
    steps: List[Dict[str, Any]] = patched.setdefault("steps", [])
    changes: List[IAFixChangeItem] = []

    # 1) HTTPS GET Request -> timeout=10 si falta
    for i, st in enumerate(steps):
        if not isinstance(st, dict):
            continue
        if st.get("type") == "HTTPS GET Request":
            st.setdefault("args", {})
            if "timeout" not in st["args"]:
                st["args"]["timeout"] = 10
                changes.append(
                    IAFixChangeItem(
                        kind="parameter_set",
                        path=f"steps[{i}].args.timeout",
                        message="Se estableció timeout=10 en HTTPS GET Request.",
                        detail={"param": "timeout", "value": 10},
                    )
                )

    # 2) Reordenar Validate CSV antes de Simple Transform si corresponde
    types = [s.get("type") if isinstance(s, dict) else None for s in steps]
    if "Validate CSV File" in types and "Simple Transform" in types:
        idx_validate = types.index("Validate CSV File")
        idx_transform = types.index("Simple Transform")
        if idx_validate > idx_transform:
            node_validate = steps.pop(idx_validate)
            # Recalcular índice de transform si se desplazó
            types = [s.get("type") if isinstance(s, dict) else None for s in steps]
            idx_transform = types.index("Simple Transform")
            steps.insert(idx_transform, node_validate)
            changes.append(
                IAFixChangeItem(
                    kind="reorder_nodes",
                    path=f"steps[{idx_validate}]",
                    message="Reordenado 'Validate CSV File' antes de 'Simple Transform'.",
                )
            )

    # 3) Agregar salida si no existe
    types = [s.get("type") if isinstance(s, dict) else None for s in steps]
    has_output = any(t in ("Save to Database", "Mock Notification") for t in types)
    if not has_output:
        new_node = {"type": "Save to Database", "args": {"table": "dest_tabla"}}
        steps.append(new_node)
        changes.append(
            IAFixChangeItem(
                kind="add_node",
                path=f"steps[{len(steps)-1}]",
                message="Agregado nodo de salida 'Save to Database'.",
                detail={"node": new_node, "position": len(steps)-1},
            )
        )

    return IAFixResponse(
        patched_definition=patched,
        changes=changes,
        rationale="Correcciones determinísticas básicas sobre orden, parámetros y salida.",
        confidence=0.8,
    )

@app.post(
    "/ia/estimate",
    response_model=IAEstimateResponse,
    tags=["ia"],
    responses={
        200: {
            "description": "Estimación de tiempo, costo y complejidad.",
            "content": {
                "application/json": {
                    "examples": {
                        "ok_breakdown": {
                            "summary": "Estimación típica con 4 pasos",
                            "value": {
                                "estimated_runtime_seconds": 8.7,
                                "estimated_cost": 0.0031,
                                "complexity_score": 0.46,
                                "breakdown": [
                                    {"step_index": 0, "type": "HTTPS GET Request", "time": 2.7, "cost": 0.00102},
                                    {"step_index": 1, "type": "Validate CSV File", "time": 1.8, "cost": 0.00051},
                                    {"step_index": 2, "type": "Simple Transform", "time": 1.35, "cost": 0.00034},
                                    {"step_index": 3, "type": "Save to Database", "time": 2.25, "cost": 0.00085}
                                ],
                                "rationale": "Estimación determinística basada en tipo y cantidad de pasos, con ajustes por goals.",
                                "confidence": 0.8
                            }
                        }
                    }
                }
            }
        },
        400: {
            "description": "Cuerpo inválido.",
            "content": {
                "application/json": {
                    "examples": {
                        "bad_body": {
                            "summary": "Body sin 'definition'",
                            "value": {"detail": "Unprocessable Entity"}
                        }
                    }
                }
            }
        },
        401: {
            "description": "No autorizado.",
            "content": {
                "application/json": {
                    "examples": {
                        "missing_or_invalid": {
                            "summary": "Falta Authorization o formato inválido",
                            "value": {"detail": "Missing or invalid token"}
                        },
                        "wrong_prefix": {
                            "summary": "Token no mock-*",
                            "value": {"detail": "Unauthorized"}
                        }
                    }
                }
            }
        },
    },
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "examples": {
                        "typical_4_steps": {
                            "summary": "GET + Validate + Transform + Save",
                            "value": {
                                "name": "etl-sencillo",
                                "definition": {
                                    "steps": [
                                        {"type": "HTTPS GET Request", "args": {"url": "https://ejemplo.com/data.csv"}},
                                        {"type": "Validate CSV File", "args": {"delimiter": ",", "columns": ["a","b"]}},
                                        {"type": "Simple Transform", "args": {"op": "uppercase", "field": "a"}},
                                        {"type": "Save to Database", "args": {"table": "dest_tabla"}}
                                    ]
                                },
                                "goals": ["rápido","barato"]
                            }
                        }
                    }
                }
            }
        }
    }
)
def ia_estimate(req: IAEstimateRequest, authorization: Optional[str] = Header(default=None)) -> IAEstimateResponse:
    """
    Estimación determinística simple en función del tipo y cantidad de pasos.
    Requiere Authorization: Bearer mock-*.
    """
    proxy._validate_token(authorization)

    steps = req.definition.get("steps", [])
    types = [s.get("type") for s in steps if isinstance(s, dict)]

    # Parámetros base por tipo (tiempo en segundos, costo relativo)
    BASE = {
        "HTTPS GET Request": (3.0, 0.0012),
        "Validate CSV File": (2.0, 0.0006),
        "Simple Transform": (1.5, 0.0004),
        "Save to Database": (2.5, 0.0010),
        "Mock Notification": (0.8, 0.0002),
    }
    DEFAULT = (1.0, 0.0003)

    breakdown: List[IAEstimateBreakdownItem] = []
    total_time = 0.0
    total_cost = 0.0

    for i, t in enumerate(types):
        base_time, base_cost = BASE.get(t, DEFAULT)
        # Ajuste simple por "goals" si está presente
        time = base_time
        cost = base_cost
        goals = req.goals or []
        if "rápido" in goals:
            time *= 0.9
        if "barato" in goals:
            cost *= 0.85

        breakdown.append(
            IAEstimateBreakdownItem(step_index=i, type=t or "Unknown", time=round(time, 3), cost=round(cost, 6))
        )
        total_time += time
        total_cost += cost

    # Complejidad acotada a [0,1] según cantidad y diversidad de tipos (mock)
    diversity = len(set(types)) if types else 0
    raw_complexity = 0.15 * len(types) + 0.1 * diversity
    complexity_score = 1 - exp(-raw_complexity)  # mapea creciente a (0,1)
    complexity_score = max(0.0, min(1.0, complexity_score))

    return IAEstimateResponse(
        estimated_runtime_seconds=round(total_time, 3),
        estimated_cost=round(total_cost, 6),
        complexity_score=round(complexity_score, 3),
        breakdown=breakdown,
        rationale="Estimación determinística basada en tipo y cantidad de pasos, con ajustes por goals.",
        confidence=0.8,
    )
