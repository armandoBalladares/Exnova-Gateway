from app.application.policies import TradingPolicy
from app.core.audit import audit
from app.domain.entities import Balance, SessionStatus
from app.domain.enums import AccountType
from app.domain.exceptions import DomainError, PolicyViolationError
from app.domain.ports import BrokerGateway


class AccountService:
    """Casos de uso: sesión con el broker y cuenta."""

    def __init__(self, gateway: BrokerGateway, policy: TradingPolicy) -> None:
        self._gateway = gateway
        self._policy = policy

    async def connect(self, initiator: str = "api") -> SessionStatus:
        try:
            await self._gateway.connect()
        except DomainError as exc:
            audit("session.connect", "failed", initiator=initiator, error=str(exc), error_code=exc.code)
            raise
        audit("session.connect", "success", initiator=initiator, account_type=self._gateway.account_type.value)
        return await self.status()

    async def disconnect(self, initiator: str = "api") -> SessionStatus:
        await self._gateway.disconnect()
        audit("session.disconnect", "success", initiator=initiator)
        return await self.status()

    async def status(self) -> SessionStatus:
        return SessionStatus(
            connected=await self._gateway.is_connected(),
            account_type=self._gateway.account_type,
        )

    async def balance(self) -> Balance:
        return await self._gateway.get_balance()

    async def switch_account(self, target: AccountType) -> SessionStatus:
        if target == AccountType.REAL and not self._policy.allow_real_trading:
            audit("account.switch", "denied", target=target.value, reason="real_trading_not_allowed")
            raise PolicyViolationError("El cambio a cuenta REAL no está permitido en este entorno")
        previous = self._gateway.account_type.value
        try:
            await self._gateway.switch_account(target)
        except DomainError as exc:
            audit("account.switch", "failed", target=target.value, error=str(exc), error_code=exc.code)
            raise
        audit("account.switch", "success", previous=previous, target=target.value)
        return await self.status()
