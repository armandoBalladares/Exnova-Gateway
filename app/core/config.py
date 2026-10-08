import os
from enum import Enum
from functools import lru_cache

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.domain.enums import AccountType

# Se lee ANTES de instanciar Settings para decidir qué archivo .env.<entorno> cargar.
_APP_ENV = os.getenv("APP_ENV", "local")


class AppEnv(str, Enum):
    LOCAL = "local"
    DEV = "dev"
    STAGING = "staging"
    PROD = "prod"


class Settings(BaseSettings):
    # Precedencia (menor a mayor): .env < .env.<APP_ENV> < variables de entorno del SO
    model_config = SettingsConfigDict(
        env_file=(".env", f".env.{_APP_ENV}"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Aplicación ---
    app_name: str = "exnova-gateway"
    app_version: str = "1.0.0"
    app_env: AppEnv = AppEnv.LOCAL
    debug: bool = False
    api_prefix: str = "/api/v1"
    cors_origins: str = ""  # separados por coma

    # --- Seguridad de la API (formato: "nombre:clave,nombre2:clave2") ---
    api_keys: str = ""

    # --- Exnova ---
    exnova_email: str = ""
    exnova_password: SecretStr = SecretStr("")
    exnova_account_type: AccountType = AccountType.PRACTICE
    exnova_auto_connect: bool = True
    exnova_reconnect_attempts: int = 3
    exnova_reconnect_delay_seconds: float = 2.0

    # --- Guardarraíles de trading ---
    trading_enabled: bool = False
    allow_real_trading: bool = False
    max_trade_amount: float = 10.0

    # --- Logging / Auditoría ---
    log_level: str = "INFO"
    log_format: str = "json"  # json | console
    log_dir: str = "logs"
    log_max_bytes: int = 10 * 1024 * 1024
    log_backup_count: int = 10

    @field_validator("log_level")
    @classmethod
    def _upper_level(cls, v: str) -> str:
        return v.upper()

    @property
    def api_keys_map(self) -> dict[str, str]:
        """Devuelve {clave: nombre_cliente}."""
        result: dict[str, str] = {}
        for item in (p.strip() for p in self.api_keys.split(",")):
            if not item:
                continue
            name, sep, key = item.partition(":")
            if not sep or not name.strip() or not key.strip():
                raise ValueError("API_KEYS debe tener el formato 'nombre:clave,nombre2:clave2'")
            result[key.strip()] = name.strip()
        return result

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_prod(self) -> bool:
        return self.app_env == AppEnv.PROD

    @model_validator(mode="after")
    def _validate_environment_rules(self) -> "Settings":
        keys = self.api_keys_map  # valida el formato
        if self.app_env in (AppEnv.STAGING, AppEnv.PROD):
            if not keys:
                raise ValueError("API_KEYS es obligatorio en staging/prod")
            if self.debug:
                raise ValueError("DEBUG no puede estar activo en staging/prod")
        if self.allow_real_trading and self.app_env != AppEnv.PROD:
            raise ValueError("ALLOW_REAL_TRADING=true solo se permite con APP_ENV=prod")
        if self.exnova_account_type == AccountType.REAL and not self.allow_real_trading:
            raise ValueError("EXNOVA_ACCOUNT_TYPE=REAL requiere ALLOW_REAL_TRADING=true")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
