import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.bootstrap import Container, build_container
from app.core.config import Settings, get_settings
from app.core.logging import setup_logging
from app.domain.exceptions import DomainError
from app.interfaces.api.errors import register_exception_handlers
from app.interfaces.api.middleware import RequestContextMiddleware
from app.interfaces.api.v1 import health
from app.interfaces.api.v1.router import api_router

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None, container: Container | None = None) -> FastAPI:
    settings = settings or get_settings()
    setup_logging(settings)
    container = container or build_container(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info(
            "Iniciando aplicación",
            extra={"app_env": settings.app_env.value, "version": settings.app_version,
                   "trading_enabled": settings.trading_enabled,
                   "account_type": settings.exnova_account_type.value},
        )
        if settings.exnova_auto_connect:
            try:
                await container.account.connect(initiator="system")
            except DomainError as exc:
                # No tumbamos el proceso: /health/ready reportará 503 y /session/connect permite reintentar.
                logger.error("Conexión inicial a Exnova fallida", extra={"error": str(exc)})
        yield
        await container.account.disconnect(initiator="system")
        logger.info("Aplicación detenida")

    app = FastAPI(
        title="Exnova Gateway API",
        version=settings.app_version,
        debug=settings.debug,
        lifespan=lifespan,
        docs_url=None if settings.is_prod else "/docs",
        redoc_url=None if settings.is_prod else "/redoc",
        openapi_url=None if settings.is_prod else "/openapi.json",
    )
    app.state.settings = settings
    app.state.container = container

    if settings.cors_origins_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins_list,
            allow_methods=["GET", "POST"],
            allow_headers=["X-API-Key", "Content-Type", "X-Request-ID"],
        )
    app.add_middleware(RequestContextMiddleware)  # el último añadido es el más externo

    register_exception_handlers(app)
    app.include_router(health.router)
    app.include_router(api_router, prefix=settings.api_prefix)
    return app
