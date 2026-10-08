class DomainError(Exception):
    """Base de todos los errores controlados del dominio."""

    code = "domain_error"


class InvalidRequestError(DomainError):
    code = "invalid_request"


class PolicyViolationError(DomainError):
    code = "policy_violation"


class TradingDisabledError(PolicyViolationError):
    code = "trading_disabled"


class BrokerConnectionError(DomainError):
    code = "broker_unavailable"


class BrokerAuthError(DomainError):
    code = "broker_auth_failed"


class OrderRejectedError(DomainError):
    code = "order_rejected"


class BrokerOperationError(DomainError):
    code = "broker_operation_failed"
