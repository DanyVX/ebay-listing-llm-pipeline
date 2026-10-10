"""Deterministic paired evaluation statistics with bootstrap uncertainty."""

import random
import statistics
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class RateWithCI:
    value: float
    lower: float
    upper: float
    sample_size: int


def bootstrap_rate(
    successes: Sequence[bool], *, samples: int = 1000, seed: int = 42
) -> RateWithCI:
    if not successes:
        return RateWithCI(0.0, 0.0, 0.0, 0)
    if samples < 10:
        raise ValueError("bootstrap samples must be >=10")
    rng = random.Random(seed)
    size = len(successes)
    observed = sum(successes) / size
    draws = sorted(
        sum(successes[rng.randrange(size)] for _ in range(size)) / size
        for _ in range(samples)
    )
    return RateWithCI(
        observed,
        draws[int(0.025 * (samples - 1))],
        draws[int(0.975 * (samples - 1))],
        size,
    )


def percentiles(latencies_ms: Sequence[float]) -> dict[str, float | None]:
    if not latencies_ms:
        return {"p50_ms": None, "p95_ms": None}
    ordered = sorted(latencies_ms)
    p95_index = min(len(ordered) - 1, int(0.95 * (len(ordered) - 1)))
    return {"p50_ms": statistics.median(ordered), "p95_ms": ordered[p95_index]}


def compare_paired(
    first: Sequence[bool], second: Sequence[bool], *, samples: int = 1000
) -> RateWithCI:
    if len(first) != len(second):
        raise ValueError("paired observations must use the same rows")
    if not first:
        return RateWithCI(0.0, 0.0, 0.0, 0)
    diffs = [int(b) - int(a) for a, b in zip(first, second)]
    rng = random.Random(42)
    n = len(diffs)
    draws = sorted(
        sum(diffs[rng.randrange(n)] for _ in range(n)) / n
        for _ in range(samples)
    )
    return RateWithCI(
        value=sum(diffs) / n,
        lower=draws[int(0.025 * (samples - 1))],
        upper=draws[int(0.975 * (samples - 1))],
        sample_size=n,
    )
