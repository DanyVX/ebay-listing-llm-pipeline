from typer.testing import CliRunner

from elp.cli import app

runner = CliRunner()


def test_budget_check_is_offline(monkeypatch):
    monkeypatch.setenv("ELP_MAX_RUN_COST_USD", "0")
    monkeypatch.setenv("ELP_MAX_DAY_COST_USD", "0")
    result = runner.invoke(app, ["budget-check"])
    assert result.exit_code == 0
    assert "no live provider configured" in result.output


def test_policy_check_reports_missing_lookup():
    result = runner.invoke(app, ["policy-check"])
    assert result.exit_code == 0
    assert "unknown_limits=2" in result.output


def test_policy_check_invalid_file_exits(tmp_path):
    result = runner.invoke(app, ["policy-check", "--path", str(tmp_path / "absent.yaml")])
    assert result.exit_code == 2


def test_environment_command_is_anonymous():
    result = runner.invoke(app, ["environment"])
    assert result.exit_code == 0
    assert "Python=" in result.output
