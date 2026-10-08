from fastapi import APIRouter, Depends, Query

from app.application.market_service import MarketService
from app.domain.enums import InstrumentType
from app.interfaces.api.deps import authenticate, get_market_service
from app.interfaces.api.schemas import CandleOut, OpenAssetsOut

router = APIRouter(prefix="/market", tags=["market"], dependencies=[Depends(authenticate)])


@router.get("/candles", response_model=list[CandleOut])
async def candles(
    asset: str = Query(..., min_length=3, max_length=20, examples=["EURUSD"]),
    interval: int = Query(60, description="Tamaño de vela en segundos"),
    count: int = Query(100, ge=1, le=1000),
    end_time: int | None = Query(None, description="Epoch (s). Por defecto: ahora"),
    svc: MarketService = Depends(get_market_service),
):
    result = await svc.candles(asset, interval, count, end_time)
    return [CandleOut.model_validate(c, from_attributes=True) for c in result]


@router.get("/assets/open", response_model=OpenAssetsOut)
async def open_assets(
    instrument: InstrumentType = Query(InstrumentType.TURBO),
    svc: MarketService = Depends(get_market_service),
):
    return OpenAssetsOut(instrument=instrument, assets=await svc.open_assets(instrument))


@router.get("/profits")
async def profits(asset: str | None = Query(None), svc: MarketService = Depends(get_market_service)):
    return await svc.profits(asset)
