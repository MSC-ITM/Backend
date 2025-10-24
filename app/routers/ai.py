
from fastapi import APIRouter, Depends, status
from app.deps import auth_bearer

router = APIRouter()

@router.post("/ai/predict_cost_time", status_code=status.HTTP_200_OK)
def predict_cost_time(_: dict, user=Depends(auth_bearer)):
    return {"cost_estimated": 0.002, "time_estimated": 120, "breakdown": {"http.request": 60, "logic.switch": 10}}
