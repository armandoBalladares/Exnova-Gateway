from fastapi import APIRouter, Depends

from app.application.account_service import AccountService
from app.interfaces.api.deps import authenticate, get_account_service
from app.interfaces.api.schemas import BalanceOut, SessionStatusOut, SwitchAccountIn

router = APIRouter(tags=["session & account"], dependencies=[Depends(authenticate)])


@router.get("/session/status", response_model=SessionStatusOut)
async def session_status(svc: AccountService = Depends(get_account_service)):
    return SessionStatusOut.model_validate(await svc.status(), from_attributes=True)


@router.post("/session/connect", response_model=SessionStatusOut)
async def session_connect(
    svc: AccountService = Depends(get_account_service), client: str = Depends(authenticate)
):
    return SessionStatusOut.model_validate(await svc.connect(initiator=client), from_attributes=True)


@router.post("/session/disconnect", response_model=SessionStatusOut)
async def session_disconnect(
    svc: AccountService = Depends(get_account_service), client: str = Depends(authenticate)
):
    return SessionStatusOut.model_validate(await svc.disconnect(initiator=client), from_attributes=True)


@router.get("/account/balance", response_model=BalanceOut)
async def balance(svc: AccountService = Depends(get_account_service)):
    return BalanceOut.model_validate(await svc.balance(), from_attributes=True)


@router.post("/account/switch", response_model=SessionStatusOut)
async def switch_account(body: SwitchAccountIn, svc: AccountService = Depends(get_account_service)):
    return SessionStatusOut.model_validate(await svc.switch_account(body.account_type), from_attributes=True)
