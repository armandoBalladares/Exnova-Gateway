from dataclasses import dataclass

from app.domain.enums import AccountType, Direction, TradeOutcome


@dataclass(frozen=True, slots=True)
class Balance:
    amount: float
    currency: str
    account_type: AccountType


@dataclass(frozen=True, slots=True)
class Candle:
    open_time: int
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True, slots=True)
class OrderRequest:
    asset: str
    direction: Direction
    amount: float
    expiration_minutes: int


@dataclass(frozen=True, slots=True)
class PlacedOrder:
    order_id: str
    request: OrderRequest
    account_type: AccountType


@dataclass(frozen=True, slots=True)
class TradeResult:
    order_id: str
    outcome: TradeOutcome
    profit: float | None


@dataclass(frozen=True, slots=True)
class SessionStatus:
    connected: bool
    account_type: AccountType
