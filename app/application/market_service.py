from app.domain.entities import Candle
from app.domain.enums import InstrumentType
from app.domain.exceptions import InvalidRequestError
from app.domain.ports import BrokerGateway

VALID_INTERVALS = {1, 5, 10, 15, 30, 60, 120, 300, 600, 900, 1800, 3600, 7200, 14400, 28800, 43200, 86400}
MAX_CANDLES = 1000


class MarketService:
    """Casos de uso: datos de mercado (solo lectura)."""

    def __init__(self, gateway: BrokerGateway) -> None:
        self._gateway = gateway

    async def candles(
        self, asset: str, interval_seconds: int, count: int, end_time: int | None = None
    ) -> list[Candle]:
        if interval_seconds not in VALID_INTERVALS:
            raise InvalidRequestError(f"interval inválido. Permitidos: {sorted(VALID_INTERVALS)}")
        if not 1 <= count <= MAX_CANDLES:
            raise InvalidRequestError(f"count debe estar entre 1 y {MAX_CANDLES}")
        return await self._gateway.get_candles(asset.upper(), interval_seconds, count, end_time)

    async def open_assets(self, instrument: InstrumentType) -> list[str]:
        return await self._gateway.get_open_assets(instrument)

    async def profits(self, asset: str | None = None) -> dict[str, dict[str, float]]:
        return await self._gateway.get_profits(asset.upper() if asset else None)
