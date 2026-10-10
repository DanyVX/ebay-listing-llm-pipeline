import asyncio
import csv
from pathlib import Path

from elp.export import export_listings
from elp.generate.batch import run_batch
from elp.ingest import ingest
from elp.policy import load_policy


def test_csv_to_validated_listing_to_safe_export(tmp_path):
    supplier = tmp_path / "synthetic.csv"
    with supplier.open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["sku", "title", "price", "quantity", "brand", "mpn"])
        writer.writerow(["SYN-900", "Fictional clamp", "9.99", "2", "Imaginary", "TEST-900"])
    normalized = tmp_path / "normalized.jsonl"
    result = ingest(supplier, normalized, tmp_path / "rejects.csv")
    assert (result.accepted, result.rejected) == (1, 0)
    out = tmp_path / "generated.jsonl"
    summary = asyncio.run(
        run_batch(
            normalized,
            tmp_path / "state.sqlite3",
            out,
            tmp_path / "failed.jsonl",
            load_policy(Path("configs/rules.yaml")),
        )
    )
    assert summary.failed == 0
    assert summary.success + summary.warning == 1
    assert export_listings(out, tmp_path / "out.csv", "csv") == 1
