import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.domain.exceptions import (
    BrokerAuthError,
    BrokerConnectionError,
    BrokerOperationError,
    DomainError,
    InvalidRequestError,
    OrderRejectedError,
    PolicyViolationError,
)

logger = logging.getLogger(__name__)

# El orden importa: subclases primero.
_STATUS_BY_ERROR: list[tuple[type[DomainError], int]] = [
    (PolicyViolationError, 403),
    (InvalidRequestError, 400),
    (OrderRejectedError, 422),
    (BrokerAuthError, 502),
    (BrokerConnectionError, 503),
    (BrokerOperationError, 502),
]


def _body(request: Request, code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message, "request_id": getattr(request.state, "request_id", "-")}}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def _domain(request: Request, exc: DomainError) -> JSONResponse:
        status = next((s for cls, s in _STATUS_BY_ERROR if isinstance(exc, cls)), 400)
        logger.warning("Error de dominio", extra={"error_code": exc.code, "detail": str(exc), "status": status})
        return JSONResponse(status_code=status, content=_body(request, exc.code, str(exc)))

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=_body(request, "validation_error", "; ".join(
                f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()
            )),
        )

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Error no controlado")
        return JSONResponse(status_code=500, content=_body(request, "internal_error", "Error interno del servidor"))
