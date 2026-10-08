"""Composition root: único lugar donde se instancian y conectan las dependencias."""
from dataclasses import dataclass

from app.application.account_service import AccountService
from app.application.market_service import MarketService
from app.application.policies import TradingPolicy
from app.application.trading_service import TradingService
from app.core.config import Settings
from app.domain.ports import BrokerGateway
from app.infrastructure.exnova.gateway import ExnovaGateway


@dataclass
class Container:
    settings: Settings
    gateway: BrokerGateway
    account: AccountService
    market: MarketService
    trading: TradingService


def build_container(settings: Settings, gateway: BrokerGateway | None = None) -> Container:
    gateway = gateway or ExnovaGateway(
        email=settings.exnova_email,
        password=settings.exnova_password.get_secret_value(),
        account_type=settings.exnova_account_type,
        reconnect_attempts=settings.exnova_reconnect_attempts,
        reconnect_delay_seconds=settings.exnova_reconnect_delay_seconds,
    )
    policy = TradingPolicy(
        trading_enabled=settings.trading_enabled,
        allow_real_trading=settings.allow_real_trading,
        max_trade_amount=settings.max_trade_amount,
    )
    return Container(
        settings=settings,
        gateway=gateway,
        account=AccountService(gateway, policy),
        market=MarketService(gateway),
        trading=TradingService(gateway, policy),
    )
