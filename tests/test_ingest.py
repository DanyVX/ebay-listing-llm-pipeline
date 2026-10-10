import csv
import json
from pathlib import Path

import pytest

from elp.ingest import ingest
from elp.ingest.normalize import clean_text, decimal_price, normalize_unit, years


def write_csv(path: Path, rows: list[list[str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, delimiter=";")
        writer.writerows(rows)


def test_normalization_units_and_locale():
    assert clean_text("  A\u200b   &amp;  B ") == "A & B"
    assert decimal_price("1.299,00", "de_DE") == 1299
    assert decimal_price("1,299.00", "en_US") == 1299
    assert normalize_unit("2 kg")["normalized_value"] == "2000"
    assert years("2005~2010") == (2005, 2010)
    with pytest.raises(ValueError):
        years("05-10")


def test_streaming_csv_bom_aliases_and_rejects(tmp_path):
    source = tmp_path / "supplier.csv"
    write_csv(
        source,
        [
            ["SKU", "Title", "PRICE", "Qty"],
            ["A-01", "One &amp; Two", "12.50", "2"],
            ["A-02", "Second", "-1", "4"],
            ["A-03", "Third", "5", "2"],
        ],
    )
    output = tmp_path / "records.jsonl"
    rejected = tmp_path / "rejects.csv"
    result = ingest(source, output, rejected)
    assert (result.accepted, result.rejected) == (2, 1)
    records = [json.loads(x) for x in output.read_text().splitlines()]
    assert records[0]["source_title"] == "One & Two"
    assert records[0]["sku"] == "A-01"
    assert "price_nonpositive" in rejected.read_text()


@pytest.mark.parametrize(
    ("mode", "expected", "reject_count"),
    [
        ("error", "First", 1),
        ("first", "First", 0),
        ("last", "Second", 0),
        ("merge", "Second", 0),
    ],
)
def test_duplicate_policy(tmp_path, mode, expected, reject_count):
    source = tmp_path / "source.csv"
    write_csv(
        source,
        [
            ["sku", "title", "price", "quantity"],
            ["A", "First", "10", "1"],
            ["a", "Second", "11", "2"],
        ],
    )
    result = ingest(
        source, tmp_path / "output.jsonl", tmp_path / "reject.csv",
        duplicate_policy=mode,
    )
    assert result.accepted == 1
    assert result.rejected == reject_count
    data = json.loads(result.output.read_text().strip())
    assert data["source_title"] == expected


def test_empty_file(tmp_path):
    source = tmp_path / "empty.csv"
    source.write_text("")
    result = ingest(source, tmp_path / "out", tmp_path / "rej")
    assert result.accepted == 0


def test_duplicate_header_is_rejected(tmp_path):
    source = tmp_path / "dupe.csv"
    source.write_text("SKU,sku,price,title,quantity\na,b,1,x,1\n")
    with pytest.raises(ValueError, match="duplicate_headers"):
        ingest(source, tmp_path / "out", tmp_path / "rej")


def test_formula_style_identifier(tmp_path):
    source = tmp_path / "formulas.csv"
    source.write_text('sku,title,price,quantity\n"=""00123""",Demo,2,1\n')
    result = ingest(source, tmp_path / "out", tmp_path / "rej")
    assert result.accepted == 1
    assert json.loads(result.output.read_text())["sku"] == "00123"


def test_xlsx_input(tmp_path):
    from openpyxl import Workbook

    book = Workbook()
    sheet = book.active
    sheet.append(["SKU", "Title", "price", "quantity"])
    sheet.append(["demo", "Synthetic sample", "12", "3"])
    path = tmp_path / "rows.xlsx"
    book.save(path)
    result = ingest(path, tmp_path / "out.jsonl", tmp_path / "rej.csv")
    assert result.accepted == 1
