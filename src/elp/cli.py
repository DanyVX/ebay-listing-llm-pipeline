"""M0 CLI. No command makes a paid network call."""

import platform
from decimal import Decimal
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Annotated, Any, cast

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


@app.command("ingest")
def ingest_command(
    source: Annotated[Path, typer.Argument(help="Synthetic CSV or XLSX source")],
    output: Annotated[Path, typer.Option()] = Path("output/normalized.jsonl"),
    rejects: Annotated[Path, typer.Option()] = Path("output/rejects.csv"),
    duplicate_policy: str = "error",
    locale: str = "en_US",
) -> None:
    """Normalize supplier-like synthetic rows and isolate rejects."""
    from elp.ingest import ingest
    from elp.ingest.reader import DuplicatePolicy

    try:
        result = ingest(
            source,
            output,
            rejects,
            duplicate_policy=cast(DuplicatePolicy, duplicate_policy),
            locale=locale,
        )
    except (OSError, RuntimeError, ValueError) as exc:
        typer.echo(f"Ingest failed: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    typer.echo(f"accepted={result.accepted} rejected={result.rejected} output={result.output}")


@app.command("run")
def run_command(
    input_path: Annotated[Path, typer.Argument(help="Normalized JSONL input")],
    output: Annotated[Path, typer.Option()] = Path("output/listings.jsonl"),
    failures: Annotated[Path, typer.Option()] = Path("output/failures.jsonl"),
    state: Annotated[Path, typer.Option()] = Path("output/checkpoints.sqlite3"),
    concurrency: int = 4,
    dry_run: bool = False,
    provider: str = "offline",
    max_cost: Decimal = Decimal("0"),
    run_id: str = "offline",
) -> None:
    """Run a grounded offline baseline with cached, resumable row checkpoints."""
    import asyncio

    from elp.budget import BudgetLedger
    from elp.generate.batch import run_batch
    from elp.llm.adapters import BudgetedHttpClient, ProviderConfig

    client = None
    if provider != "offline":
        if provider not in {"anthropic", "openai_compatible"}:
            raise typer.BadParameter("unsupported provider")
        settings = Settings()
        if max_cost <= 0 or max_cost > settings.max_run_cost_usd:
            raise typer.BadParameter("set positive --max-cost within ELP_MAX_RUN_COST_USD")
        if not all((settings.api_key, settings.provider_model, settings.provider_base_url)):
            raise typer.BadParameter("provider credentials/model/base URL must be configured")
        if (
            settings.price_input_usd_per_million is None
            or settings.price_output_usd_per_million is None
        ):
            raise typer.BadParameter("explicit verified input/output token prices required")
        config = ProviderConfig(
            kind=cast(Any, provider),
            model=settings.provider_model,
            base_url=settings.provider_base_url,
            api_key=settings.api_key,
            input_per_million_usd=str(settings.price_input_usd_per_million),
            output_per_million_usd=str(settings.price_output_usd_per_million),
        )
        client = BudgetedHttpClient(
            config,
            BudgetLedger(settings.budget_db_path, max_cost, settings.max_day_cost_usd),
            run_id,
        )

    try:
        result = asyncio.run(
            run_batch(
                input_path,
                state,
                output,
                failures,
                load_policy(Path("configs/rules.yaml")),
                concurrency=concurrency,
                dry_run=dry_run,
                run_id=run_id,
                client=client,
            )
        )
    except (OSError, ValueError, RuntimeError) as exc:
        typer.echo(f"Batch run failed: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    typer.echo(
        f"total={result.total} processed={result.processed} cached={result.cached} "
        f"ok={result.success} warn={result.warning} failed={result.failed}"
    )


@app.command("validate")
def validate_command(
    path: Annotated[Path, typer.Argument(help="Listing JSONL input")],
) -> None:
    """Validate every output listing against the strict schema."""
    from elp.schema import Listing

    valid = invalid = 0
    try:
        with path.open(encoding="utf-8") as stream:
            for line in stream:
                if not line.strip():
                    continue
                try:
                    Listing.model_validate_json(line)
                    valid += 1
                except ValueError:
                    invalid += 1
    except OSError as exc:
        typer.echo(f"Cannot read listings: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    typer.echo(f"valid={valid} invalid={invalid}")
    if invalid:
        raise typer.Exit(code=2)


@app.command("export")
def export_command(
    source: Annotated[Path, typer.Argument(help="Validated listing JSONL")],
    output: Annotated[Path, typer.Option()] = Path("output/export.csv"),
    fmt: str = "csv",
) -> None:
    """Export safe flat CSV or typed JSONL; never upload to eBay."""
    from elp.export import export_listings

    try:
        count = export_listings(source, output, fmt)
    except (OSError, ValueError) as exc:
        typer.echo(f"Export failed: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    typer.echo(f"exported={count} file={output}")


@app.command("eval")
def eval_command(
    sample: int = 100,
    output: Annotated[Path, typer.Option()] = Path("results/offline.json"),
) -> None:
    """Run measured synthetic CPU-only benchmark, not a real-model evaluation."""
    from eval.benchmark import run

    try:
        result = run(sample, output)
    except (OSError, ValueError) as exc:
        typer.echo(f"Evaluation failed: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    typer.echo(
        f"kind={result['kind']} rows={result['rows']} failed={result['failed']} output={output}"
    )


@app.command("costs")
def costs_command() -> None:
    """Inspect explicit cost limits. No paid client is CLI-enabled."""
    budget_check()


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
