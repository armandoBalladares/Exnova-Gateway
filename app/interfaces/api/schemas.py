from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.enums import AccountType, Direction, InstrumentType, TradeOutcome


class SessionStatusOut(BaseModel):
    connected: bool
    account_type: AccountType


class BalanceOut(BaseModel):
    amount: float
    currency: str
    account_type: AccountType


class SwitchAccountIn(BaseModel):
    account_type: AccountType


class CandleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    open_time: int
    open: float
    high: float
    low: float
    close: float
    volume: float


class OpenAssetsOut(BaseModel):
    instrument: InstrumentType
    assets: list[str]


class OrderIn(BaseModel):
    asset: str = Field(min_length=3, max_length=20, examples=["EURUSD"])
    direction: Direction
    amount: float = Field(gt=0, examples=[1.0])
    expiration_minutes: int = Field(ge=1, le=60, examples=[1])

    @field_validator("asset")
    @classmethod
    def _normalize(cls, v: str) -> str:
        return v.strip().upper()


class OrderOut(BaseModel):
    order_id: str
    asset: str
    direction: Direction
    amount: float
    expiration_minutes: int
    account_type: AccountType


class OrderResultOut(BaseModel):
    order_id: str
    outcome: TradeOutcome
    profit: float | None


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: str


class ErrorOut(BaseModel):
    error: ErrorBody
