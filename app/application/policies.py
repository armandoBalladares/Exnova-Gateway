from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TradingPolicy:
    trading_enabled: bool
    allow_real_trading: bool
    max_trade_amount: float
