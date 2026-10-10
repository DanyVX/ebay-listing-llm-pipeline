"""Policy-evidence configuration. M0 validates rules; it does not enforce them."""

from datetime import date
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


class PolicyRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    status: Literal["verified", "local_safeguard", "needs_marketplace_lookup"]
    severity: Literal["error", "warn"]
    value: int | bool | str | list[str] | None
    source_url: HttpUrl | None = None
    verified_on: date | None = None

    @model_validator(mode="after")
    def validate_evidence(self) -> "PolicyRule":
        if self.status == "verified":
            if self.source_url is None or self.verified_on is None:
                raise ValueError(f"{self.id}: verified rules require a source and date")
            if self.verified_on > date.today():
                raise ValueError(f"{self.id}: verification date cannot be in the future")
        elif self.verified_on is not None:
            raise ValueError(f"{self.id}: unverified rules cannot carry a verification date")
        if self.status == "needs_marketplace_lookup" and self.value is not None:
            raise ValueError(f"{self.id}: unknown limits must remain null")
        return self


class PolicyConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str = Field(min_length=1)
    marketplace: str = Field(min_length=1)
    rules: list[PolicyRule] = Field(min_length=1)

    @model_validator(mode="after")
    def require_unique_rule_ids(self) -> "PolicyConfig":
        ids = [rule.id for rule in self.rules]
        if len(ids) != len(set(ids)):
            raise ValueError("policy rule IDs must be unique")
        return self


def load_policy(path: Path) -> PolicyConfig:
    raw: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("policy YAML must contain a mapping")
    return PolicyConfig.model_validate(raw)
