import logging
from typing import Any

_audit_logger = logging.getLogger("audit")


def audit(action: str, outcome: str, **details: Any) -> None:
    """Registra un evento de auditoría.

    action  : qué ocurrió  (p.ej. 'trading.order.placed')
    outcome : resultado    ('received' | 'success' | 'failed' | 'denied')
    details : datos del evento (nunca secretos; además se redactan automáticamente)

    Quién (client_id), correlación (request_id) y cuándo (ts) los añade el formateador.
    """
    _audit_logger.info(action, extra={"audit": True, "action": action, "outcome": outcome, **details})
