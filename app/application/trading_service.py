from app.application.policies import TradingPolicy
from app.core.audit import audit
from app.domain.entities import OrderRequest, PlacedOrder, TradeResult
from app.domain.enums import AccountType
from app.domain.exceptions import DomainError, PolicyViolationError, TradingDisabledError
from app.domain.ports import BrokerGateway


class TradingService:
    """Casos de uso: operar. Aquí viven los guardarraíles y la auditoría."""

    def __init__(self, gateway: BrokerGateway, policy: TradingPolicy) -> None:
        self._gateway = gateway
        self._policy = policy

    def _enforce_policy(self, order: OrderRequest) -> None:
        if not self._policy.trading_enabled:
            raise TradingDisabledError("El trading está deshabilitado (TRADING_ENABLED=false)")
        if self._gateway.account_type == AccountType.REAL and not self._policy.allow_real_trading:
            raise PolicyViolationError("Operar en cuenta REAL no está permitido en este entorno")
        if order.amount > self._policy.max_trade_amount:
            raise PolicyViolationError(
                f"El monto {order.amount} supera el máximo permitido ({self._policy.max_trade_amount})"
            )

    async def place_order(self, order: OrderRequest) -> PlacedOrder:
        account_type = self._gateway.account_type
        base = {
            "asset": order.asset,
            "direction": order.direction.value,
            "amount": order.amount,
            "expiration_minutes": order.expiration_minutes,
            "account_type": account_type.value,
        }
        audit("trading.order.requested", "received", **base)

        try:
            self._enforce_policy(order)
        except PolicyViolationError as exc:
            audit("trading.order.rejected", "denied", reason=str(exc), error_code=exc.code, **base)
            raise

        try:
            order_id = await self._gateway.place_order(order)
        except DomainError as exc:
            audit("trading.order.placed", "failed", error=str(exc), error_code=exc.code, **base)
            raise

        audit("trading.order.placed", "success", order_id=order_id, **base)
        return PlacedOrder(order_id=order_id, request=order, account_type=account_type)

    async def get_result(self, order_id: str, timeout_seconds: int) -> TradeResult:
        result = await self._gateway.get_order_result(order_id, timeout_seconds)
        audit(
            "trading.order.result",
            "success",
            order_id=order_id,
            trade_outcome=result.outcome.value,
            profit=result.profit,
        )
        return result
