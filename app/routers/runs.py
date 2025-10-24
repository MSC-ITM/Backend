from fastapi import APIRouter, Depends, status, HTTPException
from app.deps import auth_bearer
from app.services.store import PUBLISHED

router = APIRouter()

@router.post("/runs", status_code=status.HTTP_201_CREATED)
def create_run(body: dict, user=Depends(auth_bearer)):
    wid = body.get("workflow_id")
    # Acepta 'wf_demo' como publicado (seed simulado) o cualquier workflow publicado en memoria
    if wid != "wf_demo" and wid not in PUBLISHED:
        raise HTTPException(status_code=404, detail="workflow not found or not published")
    return {"id": "run_demo", "workflow_id": wid, "status": "queued"}

@router.get("/runs/{run_id}", status_code=status.HTTP_404_NOT_FOUND)
def get_run(run_id: str, user=Depends(auth_bearer)):
    return {"error": {"code": "NOT_FOUND", "message": "Not found"}}
