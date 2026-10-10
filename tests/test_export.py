import csv
import json

import pytest

from elp.export import export_listings
from elp.export.formats import _safe_cell
from elp.schema import Listing
from elp.schema.models import CategorySuggestion, ListingMeta


def build_listing(title: str) -> Listing:
    return Listing(
        sku="SYN-EXPORT",
        title=title,
        category_suggestion=CategorySuggestion(name="Fictional", confidence=0),
        item_specifics={},
        condition_note="",
        bullet_points=[],
        compatibility=[],
        search_keywords=[],
        warnings=[],
        provenance={},
        meta=ListingMeta(
            model="deterministic-baseline", prompt_version="v1", rules_version="m0", run_id="test"
        ),
    )


@pytest.mark.parametrize("attack", ["=1+1", "+SUM(A1)", "-1+2", "@HYPERLINK()", "\t=7"])
def test_csv_formula_escape(attack):
    assert _safe_cell(attack).startswith("'")


def test_jsonl_and_csv_exports_are_valid(tmp_path):
    source = tmp_path / "input.jsonl"
    listing = build_listing("Synthetic part")
    source.write_text(listing.model_dump_json() + "\n", encoding="utf-8")
    assert export_listings(source, tmp_path / "output.jsonl", "jsonl") == 1
    assert export_listings(source, tmp_path / "output.csv", "csv") == 1
    assert json.loads((tmp_path / "output.jsonl").read_text())["sku"] == "SYN-EXPORT"
    with (tmp_path / "output.csv").open(newline="") as stream:
        data = next(csv.DictReader(stream))
    assert data["sku"] == "SYN-EXPORT"


def test_failed_validation_never_overwrites_destination(tmp_path):
    source = tmp_path / "bad.jsonl"
    output = tmp_path / "export.csv"
    output.write_text("already good")
    source.write_text('{"invalid":true}\n')
    with pytest.raises(ValueError):
        export_listings(source, output, "csv")
    assert output.read_text() == "already good"


def test_unsupported_format_rejected(tmp_path):
    with pytest.raises(ValueError):
        export_listings(tmp_path / "input", tmp_path / "out", "xlsx")
