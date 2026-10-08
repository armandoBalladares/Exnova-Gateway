from contextvars import ContextVar

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")
client_ctx: ContextVar[str] = ContextVar("client_id", default="-")
