from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import mcp_oauth

router = APIRouter(prefix="/api/mcp-login", tags=["mcp-login"])


class DeviceStartIn(BaseModel):
    user_name: str
    server: str


def _require_user(name: str) -> str:
    name = name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="user_name required")
    return name


@router.get("/status")
def oauth_status(user_name: str):
    return {"servers": mcp_oauth.status_for_user(_require_user(user_name))}


@router.post("/start")
def device_start(body: DeviceStartIn):
    try:
        return mcp_oauth.start_device_flow(_require_user(body.user_name), body.server)
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown mcp server") from None


@router.get("/flows/{flow_id}")
def device_poll(flow_id: str):
    result = mcp_oauth.poll_flow(flow_id)
    if result.get("status") == "error" and result.get("error") == "unknown_flow":
        raise HTTPException(status_code=404, detail="unknown flow")
    return result
