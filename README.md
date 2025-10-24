
# Workflow Backend (API-first, TDD)

Backend para orquestación de workflows con IA. Stack: FastAPI + SQLModel/SQLAlchemy + Redis.
Enfoque **OpenAPI-first** y **TDD**

## Requisitos
- Python 3.11+
- (Opcional) Redis y Postgres si deseas probar más allá de los tests iniciales.

## Uso rápido (dev)
```bash
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .[dev]
uvicorn app.main:app --reload
```

## Ejecutar tests
```bash
pytest -q
```

## Validar OpenAPI con Schemathesis
```bash
schemathesis run spec/openapi/openapi.yaml --checks all --stateful=links
```
