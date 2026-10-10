"""Offline benchmark executes the pipeline and records measured environment and outcome."""

import argparse
import asyncio
import importlib.metadata
import json
import platform
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

from elp.generate.batch import run_batch
from elp.policy import load_policy

PACKAGES = ("pydantic", "pydantic-settings", "httpx", "jinja2", "nh3")


def commit_hash() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def environment() -> dict[str, object]:
    packages = {}
    for package in PACKAGES:
        try:
            packages[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            packages[package] = "not-installed"
    return {
        "platform": platform.platform(),
        "cpu": platform.processor() or platform.machine(),
        "python": sys.version.split()[0],
        "libraries": packages,
        "git_commit": commit_hash(),
        "recorded_at_utc": datetime.now(UTC).isoformat(),
        "gpu": "not used: CPU-only baseline",
    }


def run(sample_size: int, output: Path) -> dict[str, object]:
    if sample_size < 1:
        raise ValueError("sample_size must be positive")
    source = Path("data/sample/eval100.jsonl")
    rows = source.read_text(encoding="utf-8").splitlines()[:sample_size]
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        input_path = root / "input.jsonl"
        input_path.write_text("\n".join(rows) + "\n", encoding="utf-8")
        started = time.perf_counter()
        result = asyncio.run(run_batch(
            input_path,
            root / "state.sqlite3",
            root / "listings.jsonl",
            root / "failed.jsonl",
            load_policy(Path("configs/rules.yaml")),
            run_id="offline-eval",
            concurrency=4,
        ))
        elapsed = time.perf_counter() - started
        payload: dict[str, object] = {
            "kind": "offline_deterministic_baseline",
            "prompt_version": "v1",
            "rows": result.total,
            "success": result.success,
            "warn": result.warning,
            "failed": result.failed,
            "cost_usd": "0",
            "elapsed_seconds": elapsed,
            "environment": environment(),
            "limitations": [
                "No pretrained model or paid API was used",
                "Synthetic evaluation fixtures only",
                "This measures software execution, not LLM quality",
            ],
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        intermediate = output.with_suffix(".tmp")
        intermediate.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        intermediate.replace(output)
        return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=int, default=100)
    parser.add_argument("--output", type=Path, default=Path("results/offline.json"))
    args = parser.parse_args()
    report = run(args.sample, args.output)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
