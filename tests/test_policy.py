from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from elp.policy import PolicyConfig, PolicyRule, load_policy
from elp.settings import Settings


def test_project_policy_loads():
    cfg = load_policy(Path("configs/rules.yaml"))
    assert cfg.marketplace == "EBAY_US"
    assert any(x.id == "title_max_chars" and x.value == 80 for x in cfg.rules)
    assert any(x.status == "needs_marketplace_lookup" for x in cfg.rules)


def test_verified_rule_needs_documented_provenance():
    with pytest.raises(ValidationError):
        PolicyRule.model_validate(
            {"id": "max", "status": "verified", "severity": "error", "value": 80}
        )


def test_marketplace_unknown_never_uses_guessed_value():
    with pytest.raises(ValidationError):
        PolicyRule.model_validate(
            {"id": "unknown", "status": "needs_marketplace_lookup",
             "severity": "error", "value": 50}
        )


def test_future_verification_rejected():
    with pytest.raises(ValidationError):
        PolicyRule.model_validate(
            {"id": "future", "status": "verified", "severity": "error",
             "value": 80, "verified_on": date(2099, 1, 1),
             "source_url": "https://developer.ebay.com/test"}
        )


def test_duplicate_ids_rejected():
    rule = PolicyRule(id="local", status="local_safeguard", severity="warn", value=True)
    with pytest.raises(ValidationError):
        PolicyConfig(version="x", marketplace="EBAY_US", rules=[rule, rule])


def test_malformed_policy_rejected(tmp_path):
    path = tmp_path / "rules.yaml"
    path.write_text("- unexpected list", encoding="utf-8")
    with pytest.raises(ValueError, match="mapping"):
        load_policy(path)


def test_settings_zero_by_default(monkeypatch):
    monkeypatch.delenv("ELP_MAX_RUN_COST_USD", raising=False)
    monkeypatch.delenv("ELP_MAX_DAY_COST_USD", raising=False)
    settings = Settings(_env_file=None)
    assert settings.max_run_cost_usd == 0
    assert settings.max_day_cost_usd == 0


def test_settings_rejects_negative_cost(monkeypatch):
    monkeypatch.setenv("ELP_MAX_RUN_COST_USD", "-1")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)
