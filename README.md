# backend-api — API puente (FastAPI)

Este repositorio implementa el **backend API-puente** del proyecto **“Orquestador de Workflows con IA”**.  
La API expone contratos REST/OpenAPI para que el Frontend consuma y para que el módulo de IA entregue sugerencias, fixes y estimaciones.  
**No contiene lógica de negocio**: la ejecución real de workflows y el esquema definitivo pertenecen al **Worker**.

---

## 🧩 Componentes y responsabilidades

| Componente | Responsable | Descripción |
|-------------|-------------|--------------|
| **Frontend** | Paulina | UI para crear, editar, ejecutar y monitorear workflows. Consume esta API. |
| **Backend API (este repo)** | Julio | Endpoints REST + OpenAPI; autenticación Proxy; persistencia mínima. Sin reglas de negocio. |
| **Worker** | Eugenio | Ejecuta workflows, actualiza estados y logs; define el **esquema final** de la BD. |
| **Módulo IA** | (IA asistida) | Sugiere, corrige y estima a partir de la definición de workflows. |

---

## ⚙️ Principios de diseño

- **API como puente:** los handlers solo enrutan; la lógica vive en el Worker.  
- **Simplicidad y TDD:** primero pruebas (pytest), luego implementación.  
- **Contratos claros:** OpenAPI autogenerado con ejemplos ricos.  
- **Propiedad de datos:** el Worker define el esquema estable; la API se adapta.  
- **Sin dependencias innecesarias:** SQLModel solo cuando aporta valor.

---

## 🚀 Endpoints (MVP Etapas 1–3)

### Autenticación
- `POST /login` → mock (patrón Proxy).
  - Requiere `Authorization: Bearer mock-*`.
  - **Request Body:** `{ "username": "user", "password": "password" }`
  - **Response:** `{ "access_token": "mock-token-...", "token_type": "bearer" }`
  - **Nota:** La autenticación es un mock. Cualquier `username`/`password` es válido. El cliente debe enviar el `access_token` en las cabeceras de las peticiones protegidas (`Authorization: Bearer mock-token-...`).

### Workflows
- `POST /workflow` → crea registro (status `"en_progreso"`).
  - **Request Body:** `{ "name": "Mi Primer Workflow", "definition": { "nodes": [...], "edges": [...] } }`
  - **Response (201 Created):** `{ "id": 1, "name": "Mi Primer Workflow", "status": "en_progreso", "created_at": "...", "updated_at": "..." }`

- `GET /workflows/{id}/status`
  - **Response:** `{ "id": 1, "status": "completado" }`

- `GET /workflows`
  - **Response:** `[ { "id": 1, "name": "Mi Primer Workflow", "status": "completado" }, ... ]`

### IA (mock determinístico)
- `POST /ia/suggestion` → genera sugerencias sobre nodos y parámetros.
  - **Request Body:** `{ "workflow_definition": { ... } }`
  - **Response:** `{ "suggestions": [ { "type": "add_node", "details": "..." } ] }`

- `POST /ia/fix` → aplica correcciones básicas.
  - **Request Body:** `{ "workflow_definition": { ... } }`
  - **Response:** `{ "fixed_definition": { ... }, "changes_applied": [ "..." ] }`

- `POST /ia/estimate` → estima tiempo, costo y complejidad.
  - **Request Body:** `{ "workflow_definition": { ... } }`
  - **Response:** `{ "time_seconds": 120, "cost_units": 5, "complexity_score": 0.75 }`

---

## 🧱 Estructura mínima
## 🧱 Estructura del Proyecto

backend-api/
├── src/
│ └── main.py # App FastAPI, modelos, repos (in-memory / SQLModel)
├── tests/ # Pytest (TDD)
│   └── main.py       # Aplicación FastAPI: endpoints, modelos Pydantic/SQLModel.
├── tests/
│   └── test_main.py  # Pruebas unitarias y de integración para los endpoints.
└── docs/
└── BD_DISENIO.md # Diseño de base de datos provisional (para Worker)
    └── BD_DISENIO.md # Diseño de la Base de Datos (especificación para el Worker).

---

## 🔧 Variables de Entorno

Para configurar la aplicación, se pueden crear un archivo `.env` en la raíz del proyecto.

```
MOCK_TOKEN_SECRET="tu-secreto-aqui" # Opcional: Clave para firmar tokens de prueba.
```


> Etapa 3 usa **SQLite en memoria compartida** (sin archivos .db) para pruebas.

---

## 🖥️ Ejecución local

```bash
# Activar entorno virtual
source .venv/bin/activate        # macOS/Linux
# .\.venv\Scripts\Activate.ps1   # Windows PowerShell

# Instalar dependencias
pip install fastapi uvicorn sqlmodel pytest httpx

# Iniciar servidor
uvicorn src.main:app --reload --port 8000

Documentación API
## ✅ Pruebas

Para ejecutar el conjunto de pruebas (requiere `pytest` y `httpx`):

```bash
pytest
```

## 📚 Documentación API
Swagger UI → http://127.0.0.1:8000/docs
ReDoc → http://127.0.0.1:8000/redoc