"""Adaptador del puerto BrokerGateway usando la librería https://github.com/zagmi/exnova
(fork de iqoptionapi).

La librería es SÍNCRONA, mantiene un WebSocket en hilos propios y no es thread-safe, así que:
  * todas las llamadas se ejecutan en un threadpool (no bloquean el event loop), y
  * se serializan con un RLock.

TODO el conocimiento de la librería vive en este archivo: si cambia su API, solo se toca aquí.
"""
import functools
import logging
import threading
import time
from typing import Any, Callable, TypeVar

import anyio.to_thread

from app.domain.entities import Balance, Candle, OrderRequest, TradeResult
from app.domain.enums import AccountType, InstrumentType, TradeOutcome
from app.domain.exceptions import (
    BrokerAuthError,
    BrokerConnectionError,
    BrokerOperationError,
    OrderRejectedError,
)

logger = logging.getLogger(__name__)
T = TypeVar("T")


class ExnovaGateway:
    def __init__(
        self,
        email: str,
        password: str,
        account_type: AccountType = AccountType.PRACTICE,
        reconnect_attempts: int = 3,
        reconnect_delay_seconds: float = 2.0,
    ) -> None:
        self._email = email
        self._password = password
        self._account_type = account_type
        self._attempts = max(1, reconnect_attempts)
        self._delay = reconnect_delay_seconds
        self._client: Any = None
        self._lock = threading.RLock()

    # ------------------------------------------------------------------ utilidades
    @property
    def account_type(self) -> AccountType:
        return self._account_type

    async def _call(self, fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        return await anyio.to_thread.run_sync(functools.partial(fn, *args, **kwargs))

    def _require_client(self) -> Any:
        if self._client is None:
            raise BrokerConnectionError("No hay sesión activa con Exnova")
        return self._client

    # ------------------------------------------------------------------ conexión
    def _connect_sync(self) -> None:
        if not self._email or not self._password:
            raise BrokerAuthError("Credenciales de Exnova no configuradas (EXNOVA_EMAIL / EXNOVA_PASSWORD)")
        try:
            from exnova.stable_api import Exnova  # import perezoso: facilita tests sin la librería
        except ImportError as exc:  # pragma: no cover
            raise BrokerConnectionError("La librería 'exnova' no está instalada") from exc

        with self._lock:
            self._close_sync()
            try:
                client = Exnova(self._email, self._password)
                ok, reason = client.connect()
            except Exception as exc:
                raise BrokerConnectionError(f"Error conectando con Exnova: {type(exc).__name__}") from exc
            if not ok:
                text = str(reason).lower()
                detail = str(reason)[:200]
                if any(w in text for w in ("invalid", "credential", "password", "unauthor", "401")):
                    raise BrokerAuthError(f"Exnova rechazó las credenciales: {detail}")
                raise BrokerConnectionError(f"Exnova rechazó la conexión: {detail}")
            client.change_balance(self._account_type.value)
            self._client = client
        logger.info("Conectado a Exnova", extra={"account_type": self._account_type.value})

    def _close_sync(self) -> None:
        with self._lock:
            if self._client is not None:
                try:
                    self._client.api.close()
                except Exception:  # noqa: BLE001 - cierre best-effort
                    logger.debug("Error cerrando sesión previa", exc_info=True)
                self._client = None

    def _is_connected_sync(self) -> bool:
        with self._lock:
            if self._client is None:
                return False
            try:
                return bool(self._client.check_connect())
            except Exception:  # noqa: BLE001
                return False

    def _ensure_connected_sync(self) -> None:
        if self._is_connected_sync():
            return
        last_error: Exception | None = None
        for attempt in range(1, self._attempts + 1):
            try:
                logger.warning("Reconectando a Exnova", extra={"attempt": attempt, "max_attempts": self._attempts})
                self._connect_sync()
                return
            except BrokerAuthError:
                raise  # reintentar con credenciales malas solo arriesga un bloqueo de cuenta
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                time.sleep(self._delay * attempt)
        raise BrokerConnectionError("No fue posible (re)conectar con Exnova") from last_error

    async def connect(self) -> None:
        await self._call(self._connect_sync)

    async def disconnect(self) -> None:
        await self._call(self._close_sync)

    async def is_connected(self) -> bool:
        return await self._call(self._is_connected_sync)

    # ------------------------------------------------------------------ cuenta
    def _get_balance_sync(self) -> Balance:
        self._ensure_connected_sync()
        with self._lock:
            client = self._require_client()
            return Balance(
                amount=float(client.get_balance()),
                currency=str(client.get_currency()),
                account_type=self._account_type,
            )

    async def get_balance(self) -> Balance:
        return await self._call(self._get_balance_sync)

    def _switch_sync(self, account_type: AccountType) -> None:
        self._ensure_connected_sync()
        with self._lock:
            self._require_client().change_balance(account_type.value)
            self._account_type = account_type

    async def switch_account(self, account_type: AccountType) -> None:
        await self._call(self._switch_sync, account_type)

    # ------------------------------------------------------------------ mercado
    def _candles_sync(self, asset: str, interval: int, count: int, end_time: int | None) -> list[Candle]:
        self._ensure_connected_sync()
        with self._lock:
            raw = self._require_client().get_candles(asset, interval, count, end_time or time.time())
        if not raw:
            raise BrokerOperationError(f"Sin velas para '{asset}' (¿activo inválido o mercado cerrado?)")
        return [
            Candle(
                open_time=int(c["from"]),
                open=float(c["open"]),
                high=float(c["max"]),
                low=float(c["min"]),
                close=float(c["close"]),
                volume=float(c.get("volume", 0) or 0),
            )
            for c in raw
        ]

    async def get_candles(
        self, asset: str, interval_seconds: int, count: int, end_time: int | None
    ) -> list[Candle]:
        return await self._call(self._candles_sync, asset, interval_seconds, count, end_time)

    def _open_assets_sync(self, instrument: InstrumentType) -> list[str]:
        self._ensure_connected_sync()
        with self._lock:
            data = self._require_client().get_all_open_time()  # llamada lenta (varios segundos)
        group = data.get(instrument.value, {})
        return sorted(name for name, info in group.items() if info.get("open"))

    async def get_open_assets(self, instrument: InstrumentType) -> list[str]:
        return await self._call(self._open_assets_sync, instrument)

    def _profits_sync(self, asset: str | None) -> dict[str, dict[str, float]]:
        self._ensure_connected_sync()
        with self._lock:
            data = self._require_client().get_all_profit()
        if asset:
            data = {asset: data[asset]} if asset in data else {}
        return {k: {kk: float(vv) for kk, vv in v.items()} for k, v in data.items()}

    async def get_profits(self, asset: str | None) -> dict[str, dict[str, float]]:
        return await self._call(self._profits_sync, asset)

    # ------------------------------------------------------------------ trading
    def _place_order_sync(self, order: OrderRequest) -> str:
        self._ensure_connected_sync()
        with self._lock:
            status, order_id = self._require_client().buy(
                order.amount, order.asset, order.direction.value, order.expiration_minutes
            )
        if not status:
            raise OrderRejectedError(f"Exnova rechazó la orden: {str(order_id)[:200]}")
        return str(order_id)

    async def place_order(self, order: OrderRequest) -> str:
        return await self._call(self._place_order_sync, order)

    def _read_closed_order_sync(self, order_id: str) -> TradeResult | None:
        key: Any = int(order_id) if order_id.isdigit() else order_id
        with self._lock:
            client = self._require_client()
            try:
                order = client.get_async_order(key)
            except Exception:  # noqa: BLE001 - aún sin datos para esa orden
                return None
        msg = ((order or {}).get("option-closed") or {}).get("msg") or {}
        if not msg:
            return None
        raw = str(msg.get("win", "")).lower()
        amount = float(msg.get("amount", 0) or 0)
        win_amount = float(msg.get("win_amount", 0) or 0)
        if raw == "win":
            return TradeResult(order_id, TradeOutcome.WIN, round(win_amount - amount, 2))
        if raw in ("loose", "loss", "lose"):
            return TradeResult(order_id, TradeOutcome.LOSS, round(-amount, 2))
        return TradeResult(order_id, TradeOutcome.DRAW, 0.0)

    async def get_order_result(self, order_id: str, timeout_seconds: int) -> TradeResult:
        # Sondeo asíncrono: no retiene un hilo durante la espera (a diferencia de check_win_v4, que bloquea).
        deadline = anyio.current_time() + timeout_seconds
        while True:
            result = await self._call(self._read_closed_order_sync, order_id)
            if result is not None:
                return result
            if anyio.current_time() >= deadline:
                return TradeResult(order_id, TradeOutcome.PENDING, None)
            await anyio.sleep(1.0)
