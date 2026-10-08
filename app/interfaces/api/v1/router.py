from fastapi import APIRouter

from app.interfaces.api.v1 import market, session, trading

api_router = APIRouter()
api_router.include_router(session.router)
api_router.include_router(market.router)
api_router.include_router(trading.router)
