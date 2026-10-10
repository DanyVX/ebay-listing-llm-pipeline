"""Render measured cost-vs-compliance points from existing result JSON files."""

import argparse
import json
from pathlib import Path


def plot(paths: list[Path], output: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    records = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    fig, ax = plt.subplots(figsize=(7, 4))
    for record in records:
        sample = int(record["rows"])
        if sample == 0:
            continue
        quality = (int(record["success"]) + int(record["warn"])) / sample
        cost = float(record["cost_usd"])
        ax.scatter([cost], [quality], label=str(record["kind"]))
    ax.set_xlabel("Measured total cost (USD)")
    ax.set_ylabel("Pass fraction")
    ax.set_ylim(0, 1.05)
    ax.legend()
    fig.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output)
    plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("results", type=Path, nargs="+")
    parser.add_argument("--output", type=Path, default=Path("results/quality_cost.png"))
    args = parser.parse_args()
    plot(args.results, args.output)
