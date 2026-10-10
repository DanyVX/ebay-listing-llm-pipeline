"""M0 CLI. No command makes a paid network call."""

import platform
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError

from elp.policy import load_policy
from elp.settings import Settings

app = typer.Typer(help="Offline-first grounded listing pipeline (M0 scaffold).")


@app.command("policy-check")
def policy_check(
    path: Annotated[Path, typer.Option(help="Rules YAML path")] = Path("configs/rules.yaml"),
) -> None:
    """Validate evidence and schema; does not execute compliance checks."""
    try:
        policy = load_policy(path)
    except (OSError, ValueError, ValidationError) as exc:
        typer.echo(f"Policy configuration invalid: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    verified = sum(rule.status == "verified" for rule in policy.rules)
    unknown = sum(rule.status == "needs_marketplace_lookup" for rule in policy.rules)
    typer.echo(
        f"Policy metadata valid: version={policy.version}, "
        f"rules={len(policy.rules)}, verified={verified}, unknown_limits={unknown}"
    )


@app.command("budget-check")
def budget_check() -> None:
    """Show fail-closed limits without making calls or creating a database."""
    try:
        settings = Settings()
    except ValidationError as exc:
        typer.echo(f"Budget configuration invalid: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    typer.echo(
        f"Max USD/run={settings.max_run_cost_usd}; "
        f"max USD/day={settings.max_day_cost_usd}; "
        "no live provider configured"
    )


@app.command("environment")
def environment() -> None:
    """Print anonymous environment info for diagnosing local setup."""
    typer.echo(f"OS={platform.system()} {platform.machine()}; Python={platform.python_version()}")
    for package in ("pydantic", "pydantic-settings", "PyYAML", "typer"):
        try:
            typer.echo(f"{package}={version(package)}")
        except PackageNotFoundError:
            typer.echo(f"{package}=not installed")


if __name__ == "__main__":
    app()
