"""Validated runtime settings. Paid usage is disabled by default."""

from decimal import Decimal
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ELP_", env_file=".env", extra="ignore", validate_default=True
    )

    max_run_cost_usd: Decimal = Decimal("0")
    max_day_cost_usd: Decimal = Decimal("0")
    budget_db_path: Path = Path(".elp_budget.sqlite3")
    log_level: str = "INFO"
    json_logs: bool = False

    @field_validator("max_run_cost_usd", "max_day_cost_usd")
    @classmethod
    def nonnegative_finite_money(cls, value: Decimal) -> Decimal:
        if not value.is_finite() or value < 0:
            raise ValueError("cost limits must be finite, non-negative USD values")
        return value

    @field_validator("log_level")
    @classmethod
    def supported_log_level(cls, value: str) -> str:
        normalized = value.upper()
        if normalized not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("ELP_LOG_LEVEL must be DEBUG, INFO, WARNING, ERROR or CRITICAL")
        return normalized
