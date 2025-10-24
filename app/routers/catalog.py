
from fastapi import APIRouter, Depends, status
from app.deps import auth_bearer

router = APIRouter()

@router.get("/catalog/nodes", status_code=status.HTTP_200_OK)
def catalog_nodes(user=Depends(auth_bearer)):
    return {
        "items": [
            {
                "type": "http.request",
                "category": "Network",
                "display": {"label": "HTTP Request", "icon": "Globe", "accent": "blue"},
                "ports": {"in": [], "out": [{"name": "main"}, {"name": "error"}]},
                "configSchema": {
                    "type": "object",
                    "required": ["url", "method"],
                    "properties": {
                        "method": {"type": "string", "enum": ["GET", "POST", "PUT", "PATCH", "DELETE"]},
                        "url": {"type": "string", "format": "uri"},
                        "headers": {"type": "object", "additionalProperties": {"type": "string"}},
                        "body": {"type": ["object", "string", "null"]}
                    },
                    "uiHints": {"sections": [{"title": "Request", "fields": ["method", "url", "headers", "body"]}]}
                },
            },
            {
                "type": "logic.switch",
                "category": "Logic",
                "display": {"label": "Switch (If)", "icon": "GitBranch", "accent": "amber"},
                "ports": {"in": [{"name": "main"}], "out": [{"name": "case_1"}, {"name": "case_2"}, {"name": "default"}]},
                "configSchema": {"type": "object", "properties": {"cases": {"type": "array", "items": {"type": "string"}}}},
            },
        ]
    }
