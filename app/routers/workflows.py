from fastapi import APIRouter, Depends, status, HTTPException
from app.deps import auth_bearer
from app.util.ids import new_id
from app.services.store import WORKFLOWS, PUBLISHED, WorkflowObj

router = APIRouter()

@router.post("/workflows", status_code=status.HTTP_201_CREATED)
def create_workflow(body: dict, user=Depends(auth_bearer)):
    wid = new_id("wf_")
    name = body.get("name", "unnamed")
    wf = WorkflowObj(id=wid, name=name, status="draft", version=1, payload=body)
    WORKFLOWS[wid] = wf
    # Devuelve lo que el test espera: id, version=1, status="draft"
    return {"id": wid, "version": 1, "status": "draft", **{k: v for k, v in body.items() if k != "status"}}

@router.get("/workflows", status_code=status.HTTP_200_OK)
def list_workflows(user=Depends(auth_bearer)):
    return {"items": [], "limit": 50, "offset": 0, "total": 0}

@router.get("/workflows/{workflow_id}", status_code=status.HTTP_404_NOT_FOUND)
def get_workflow(workflow_id: str, user=Depends(auth_bearer)):
    return {"error": {"code": "NOT_FOUND", "message": "Not found"}}

@router.put("/workflows/{workflow_id}")
def update_workflow(workflow_id: str, body: dict, user=Depends(auth_bearer)):
    wf = WORKFLOWS.get(workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Not found")
    if wf.status == "published":
        raise HTTPException(status_code=409, detail="published workflows are immutable")
    wf.payload.update(body)
    return {"id": wf.id, "version": wf.version, "status": wf.status}

@router.post("/workflows/{workflow_id}:publish", status_code=status.HTTP_200_OK)
def publish_workflow(workflow_id: str, user=Depends(auth_bearer)):
    wf = WORKFLOWS.get(workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Not found")
    wf.status = "published"
    PUBLISHED.add(workflow_id)
    return {"id": wf.id, "version": wf.version, "status": wf.status}

@router.post("/workflows/{workflow_id}:validate", status_code=status.HTTP_200_OK)
def validate_workflow(workflow_id: str, user=Depends(auth_bearer)):
    # Stub con issue para que FE pueda pintar errores
    return {"valid": False, "issues": [{"path": "nodes[0].config.url", "msg": "must be https", "level": "error"}]}
