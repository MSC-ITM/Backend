
from fastapi import APIRouter, Depends, status
from app.deps import auth_bearer

router = APIRouter()

@router.post("/workflows/{workflow_id}/triggers", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def create_trigger(workflow_id: str, _: dict, user=Depends(auth_bearer)):
    return {"error": {"code": "NOT_IMPLEMENTED", "message": "TDD stub"}}
