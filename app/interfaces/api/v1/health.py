from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.application.account_service import AccountService
from app.interfaces.api.deps import get_account_service

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live", summary="Liveness: el proceso responde")
async def live() -> dict:
    return {"status": "alive"}


@router.get("/ready", summary="Readiness: hay sesión activa con Exnova")
async def ready(account: AccountService = Depends(get_account_service)):
    status = await account.status()
    body = {"status": "ready" if status.connected else "not_ready", "broker_connected": status.connected}
    return JSONResponse(status_code=200 if status.connected else 503, content=body)
