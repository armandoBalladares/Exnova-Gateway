import logging
import secrets

from fastapi import HTTPException, Request, Security
from fastapi.security import APIKeyHeader

from app.application.account_service import AccountService
from app.application.market_service import MarketService
from app.application.trading_service import TradingService
from app.core.audit import audit
from app.core.config import AppEnv
from app.core.context import client_ctx

logger = logging.getLogger(__name__)
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def authenticate(request: Request, api_key: str | None = Security(_api_key_header)) -> str:
    """Valida X-API-Key y devuelve el nombre del cliente (queda en todos los logs)."""
    settings = request.app.state.settings
    keys = settings.api_keys_map

    if not keys:
        if settings.app_env == AppEnv.LOCAL:
            client = "anonymous-local"
        else:  # defensa extra: la validación de Settings ya lo impide
            raise HTTPException(status_code=401, detail="API no configurada con claves")
    else:
        client = None
        if api_key:
            for known_key, name in keys.items():  # sin 'break': tiempo constante
                if secrets.compare_digest(known_key.encode(), api_key.encode()):
                    client = name
        if client is None:
            audit(
                "auth.api_key",
                "denied",
                path=request.url.path,
                client_ip=request.client.host if request.client else "-",
            )
            raise HTTPException(status_code=401, detail="API key inválida o ausente")

    request.state.client_id = client
    client_ctx.set(client)
    return client


def get_account_service(request: Request) -> AccountService:
    return request.app.state.container.account


def get_market_service(request: Request) -> MarketService:
    return request.app.state.container.market


def get_trading_service(request: Request) -> TradingService:
    return request.app.state.container.trading
