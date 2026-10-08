import pytest
from fastapi.testclient import TestClient

from app.bootstrap import build_container
from app.core.config import AppEnv, Settings
from app.domain.entities import Balance, Candle, OrderRequest, TradeResult
from app.domain.enums import AccountType, InstrumentType, TradeOutcome
from app.domain.exceptions import BrokerConnectionError
from app.main import create_app


class FakeGateway:
    """Broker simulado: permite probar toda la API sin tocar Exnova."""

    def __init__(self) -> None:
        self._account_type = AccountType.PRACTICE
        self.connected = False
        self.orders: list[OrderRequest] = []

    @property
    def account_type(self) -> AccountType:
        return self._account_type

    async def connect(self) -> None:
        self.connected = True

    async def disconnect(self) -> None:
        self.connected = False

    async def is_connected(self) -> bool:
        return self.connected

    def _need(self) -> None:
        if not self.connected:
            raise BrokerConnectionError("sin sesión")

    async def get_balance(self) -> Balance:
        self._need()
        return Balance(1000.0, "USD", self._account_type)

    async def switch_account(self, account_type: AccountType) -> None:
        self._need()
        self._account_type = account_type

    async def get_candles(self, asset, interval_seconds, count, end_time):
        self._need()
        return [Candle(1700000000 + i * interval_seconds, 1.0, 1.1, 0.9, 1.05, 10) for i in range(count)]

    async def get_open_assets(self, instrument: InstrumentType):
        self._need()
        return ["EURUSD", "GBPUSD"]

    async def get_profits(self, asset):
        self._need()
        return {"EURUSD": {"turbo": 0.85, "binary": 0.8}}

    async def place_order(self, order: OrderRequest) -> str:
        self._need()
        self.orders.append(order)
        return "123456"

    async def get_order_result(self, order_id, timeout_seconds):
        return TradeResult(order_id, TradeOutcome.WIN, 0.85)


def make_client(tmp_path, *, trading_enabled=True, max_amount=10.0) -> tuple[TestClient, FakeGateway]:
    settings = Settings(
        app_env=AppEnv.DEV,
        api_keys="tester:secret-key",
        exnova_auto_connect=False,
        trading_enabled=trading_enabled,
        max_trade_amount=max_amount,
        log_dir=str(tmp_path / "logs"),
        log_format="console",
    )
    gateway = FakeGateway()
    app = create_app(settings, build_container(settings, gateway))
    return TestClient(app), gateway


@pytest.fixture
def client(tmp_path):
    c, _ = make_client(tmp_path)
    with c:
        yield c


@pytest.fixture
def headers():
    return {"X-API-Key": "secret-key"}
