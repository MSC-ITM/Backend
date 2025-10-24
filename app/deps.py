
from fastapi import Header, HTTPException

async def auth_bearer(authorization: str | None = Header(default=None)):
    # Stub: acepta cualquier Bearer presente; para TDD se reemplazará
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    return {"sub": "u_demo", "org_id": "org_demo", "role": "owner"}
