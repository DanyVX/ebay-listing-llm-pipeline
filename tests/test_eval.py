import json
from pathlib import Path

import pytest

from eval.benchmark import run
from eval.metrics import bootstrap_rate, compare_paired, percentiles


def test_fixture_has_100_unique_synthetic_rows():
    source = Path("data/sample/eval100.jsonl")
    rows = [json.loads(x) for x in source.read_text().splitlines()]
    assert len(rows) == 100
    assert len({item["sku"] for item in rows}) == 100
    assert all(item["sku"].startswith("SYN-") for item in rows)


def test_reference_is_explicitly_machine_generated():
    rows = [json.loads(x) for x in Path("eval/reference40.jsonl").read_text().splitlines()]
    assert len(rows) == 40
    assert all("not human" in x["reference_kind"] for x in rows)


def test_bootstrap_is_reproducible():
    first = bootstrap_rate([True, False, True], seed=99)
    assert first == bootstrap_rate([True, False, True], seed=99)
    assert first.sample_size == 3
    assert first.lower <= first.value <= first.upper


def test_paired_comparisons():
    result = compare_paired([False, False, True], [True, False, True])
    assert result.value == pytest.approx(1 / 3)
    with pytest.raises(ValueError):
        compare_paired([True], [True, False])


def test_latency_percentiles():
    assert percentiles([])["p50_ms"] is None
    assert percentiles([1, 2, 3, 4, 5])["p50_ms"] == 3


def test_small_offline_benchmark_emits_measured_json(tmp_path):
    path = tmp_path / "run.json"
    metrics = run(5, path)
    assert metrics["rows"] == 5
    assert metrics["environment"]["git_commit"]
    assert path.is_file()
    assert metrics["cost_usd"] == "0"
