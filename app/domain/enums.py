from enum import Enum


class AccountType(str, Enum):
    PRACTICE = "PRACTICE"
    REAL = "REAL"


class Direction(str, Enum):
    CALL = "call"
    PUT = "put"


class TradeOutcome(str, Enum):
    WIN = "win"
    LOSS = "loss"
    DRAW = "draw"
    PENDING = "pending"


class InstrumentType(str, Enum):
    BINARY = "binary"
    TURBO = "turbo"
    DIGITAL = "digital"
    FOREX = "forex"
    CRYPTO = "crypto"
    CFD = "cfd"
