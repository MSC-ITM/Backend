from pydantic import BaseModel

class WorkflowCreate(BaseModel):
    name: str
