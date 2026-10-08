"""Logging estructurado (JSON) con redacción de secretos.

Tres destinos:
  * stdout         -> recolectable por Docker / Kubernetes / Loki / ELK / CloudWatch
  * logs/app.log   -> log técnico de la aplicación (rotativo)
  * logs/audit.log -> pista de auditoría (rotativo, siempre JSON, logger "audit")
"""
import json
import logging
import re
import sys
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from app.core.config import Settings
from app.core.context import client_ctx, request_id_ctx

_SENSITIVE_KEYS = {
    "password", "passwd", "token", "ssid", "secret",
    "authorization", "api_key", "apikey", "x-api-key",
}
_SENSITIVE_RE = re.compile(
    r"""(?i)("?(?:password|passwd|token|ssid|secret|authorization|api[_-]?key)"?\s*[:=]\s*)("[^"]*"|'[^']*'|[^\s,;}]+)"""
)
_RESERVED = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {"message", "asctime"}


def scrub(text: str) -> str:
    return _SENSITIVE_RE.sub(r"\1***", text)


def redact(value: Any, key: str | None = None) -> Any:
    if key and key.lower() in _SENSITIVE_KEYS:
        return "***"
    if isinstance(value, dict):
        return {k: redact(v, str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(v) for v in value]
    return value


class ContextFilter(logging.Filter):
    """Inyecta request_id y client_id en cada registro."""

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            record.request_id = request_id_ctx.get()
        if not hasattr(record, "client_id"):
            record.client_id = client_ctx.get()
        return True


class JsonFormatter(logging.Formatter):
    def __init__(self, service: str, env: str) -> None:
        super().__init__()
        self._service = service
        self._env = env

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "service": self._service,
            "env": self._env,
            "message": scrub(record.getMessage()),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED:
                payload[key] = redact(value, key)
        if record.exc_info:
            payload["exception"] = scrub(self.formatException(record.exc_info))
        return json.dumps(payload, default=str, ensure_ascii=False)


def _rotating(path: Path, settings: Settings) -> RotatingFileHandler:
    return RotatingFileHandler(
        path, maxBytes=settings.log_max_bytes, backupCount=settings.log_backup_count, encoding="utf-8"
    )


def setup_logging(settings: Settings) -> None:
    log_dir = Path(settings.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    json_fmt = JsonFormatter(settings.app_name, settings.app_env.value)
    if settings.log_format == "json":
        console_fmt: logging.Formatter = json_fmt
    else:
        console_fmt = logging.Formatter(
            "%(asctime)s %(levelname)-7s [%(request_id)s|%(client_id)s] %(name)s: %(message)s"
        )

    ctx_filter = ContextFilter()

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(console_fmt)
    console.addFilter(ctx_filter)

    app_file = _rotating(log_dir / "app.log", settings)
    app_file.setFormatter(json_fmt)
    app_file.addFilter(ctx_filter)

    audit_file = _rotating(log_dir / "audit.log", settings)
    audit_file.setFormatter(json_fmt)
    audit_file.addFilter(ctx_filter)

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(settings.log_level)
    root.addHandler(console)
    root.addHandler(app_file)

    audit_logger = logging.getLogger("audit")
    audit_logger.handlers.clear()
    audit_logger.setLevel(logging.INFO)
    audit_logger.propagate = False  # no duplicar en app.log
    audit_logger.addHandler(audit_file)
    audit_logger.addHandler(console)

    # Uvicorn usa nuestros handlers; el access log lo hace nuestro middleware.
    for name in ("uvicorn", "uvicorn.error"):
        lg = logging.getLogger(name)
        lg.handlers.clear()
        lg.propagate = True
    access = logging.getLogger("uvicorn.access")
    access.handlers.clear()
    access.propagate = False

    # Librerías que a nivel DEBUG podrían volcar tokens/SSID.
    for name in ("websocket", "exnova", "iqoptionapi", "urllib3"):
        logging.getLogger(name).setLevel(logging.WARNING)
