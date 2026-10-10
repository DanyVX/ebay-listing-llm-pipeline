"""Cross-platform task entrypoint. No bash-only helper scripts."""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def execute(*args: str) -> None:
    subprocess.run(list(args), cwd=ROOT, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="ELP project tasks")
    parser.add_argument(
        "task",
        choices=[
            "setup",
            "lint",
            "format",
            "typecheck",
            "test",
            "test-fast",
            "bench",
            "run",
            "docker-build",
            "clean",
            "privacy-scan",
        ],
    )
    task = parser.parse_args().task
    if task == "setup":
        if shutil.which("uv"):
            execute("uv", "sync", "--extra", "dev")
        else:
            execute(PYTHON, "-m", "pip", "install", "-e", ".[dev]")
    elif task == "lint":
        execute(PYTHON, "-m", "ruff", "check", "src", "tests", "scripts")
        execute(PYTHON, "-m", "ruff", "format", "--check", "src", "tests", "scripts")
    elif task == "format":
        execute(PYTHON, "-m", "ruff", "format", "src", "tests", "scripts")
    elif task == "typecheck":
        execute(PYTHON, "-m", "mypy", "src/elp")
    elif task == "test":
        execute(
            PYTHON,
            "-m",
            "pytest",
            "--cov=elp",
            "--cov-report=term-missing",
            "--cov-fail-under=70",
            "-m",
            "not slow and not gpu and not live",
        )
    elif task == "test-fast":
        execute(PYTHON, "-m", "pytest", "-q", "-m", "not slow and not gpu and not live")
    elif task == "run":
        execute(PYTHON, "-m", "elp", "environment")
    elif task == "privacy-scan":
        execute(PYTHON, "scripts/privacy_scan.py")
    elif task == "clean":
        for folder in (".pytest_cache", ".mypy_cache", ".ruff_cache", "htmlcov", "build", "dist"):
            shutil.rmtree(ROOT / folder, ignore_errors=True)
    elif task == "bench":
        execute(
            PYTHON, "-m", "eval.benchmark", "--sample", "100", "--output", "results/offline.json"
        )
    elif task == "docker-build":
        parser.error(f"{task} is not available in M0; no benchmark/Dockerfile implemented")


if __name__ == "__main__":
    main()
