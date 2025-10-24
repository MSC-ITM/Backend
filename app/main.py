
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from app.routers import workflows, runs, catalog, triggers, ai, artifacts

app = FastAPI(title="Workflow Orchestration API", version="0.1.0", openapi_url="/openapi.json")

# Routers (placeholders para TDD: muchos endpoints devolverán 501)
app.include_router(workflows.router, prefix="/api/v0", tags=["workflows"])
app.include_router(runs.router, prefix="/api/v0", tags=["runs"])
app.include_router(catalog.router, prefix="/api/v0", tags=["catalog"])
app.include_router(triggers.router, prefix="/api/v0", tags=["triggers"])
app.include_router(ai.router, prefix="/api/v0", tags=["ai"])
app.include_router(artifacts.router, prefix="/api/v0", tags=["artifacts"])

@app.get("/api/v0/healthz")
def healthz():
    return {"status": "ok"}

@app.middleware("http")
async def add_request_id_header(request: Request, call_next):
    # Simple stub de request-id (en producción usar lib/uuid/trace)
    resp: Response = await call_next(request)
    resp.headers.setdefault("X-Request-Id", "dev-stub")
    return resp

@app.exception_handler(Exception)
async def default_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL",
                "message": "Unhandled error",
                "details": [{"path": "", "msg": str(exc)}],
            }
        },
    )
