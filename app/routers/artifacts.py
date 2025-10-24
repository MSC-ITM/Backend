
from fastapi import APIRouter, Depends, status
from app.deps import auth_bearer

router = APIRouter()

@router.get("/runs/{run_id}/artifacts", status_code=status.HTTP_200_OK)
def list_artifacts(run_id: str, user=Depends(auth_bearer)):
    return {"items": [], "total": 0}
