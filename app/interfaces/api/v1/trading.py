from fastapi import APIRouter, Depends, Query

from app.application.trading_service import TradingService
from app.domain.entities import OrderRequest
from app.interfaces.api.deps import authenticate, get_trading_service
from app.interfaces.api.schemas import OrderIn, OrderOut, OrderResultOut

router = APIRouter(prefix="/trading", tags=["trading"], dependencies=[Depends(authenticate)])


@router.post("/orders", response_model=OrderOut, status_code=201)
async def place_order(body: OrderIn, svc: TradingService = Depends(get_trading_service)):
    placed = await svc.place_order(
        OrderRequest(
            asset=body.asset,
            direction=body.direction,
            amount=body.amount,
            expiration_minutes=body.expiration_minutes,
        )
    )
    return OrderOut(
        order_id=placed.order_id,
        asset=placed.request.asset,
        direction=placed.request.direction,
        amount=placed.request.amount,
        expiration_minutes=placed.request.expiration_minutes,
        account_type=placed.account_type,
    )


@router.get("/orders/{order_id}/result", response_model=OrderResultOut)
async def order_result(
    order_id: str,
    timeout_seconds: int = Query(0, ge=0, le=120, description="0 = consulta inmediata; >0 espera hasta el cierre"),
    svc: TradingService = Depends(get_trading_service),
):
    result = await svc.get_result(order_id, timeout_seconds)
    return OrderResultOut(order_id=result.order_id, outcome=result.outcome, profit=result.profit)
