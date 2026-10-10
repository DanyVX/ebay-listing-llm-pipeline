"""Incremental CSV/XLSX reading with row-level rejection and disk-backed deduplication."""

import csv
import json
import sqlite3
import tempfile
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from elp.ingest.normalize import normalize_row

AliasMap = dict[str, str]
DuplicatePolicy = Literal["error", "first", "last", "merge"]
DEFAULT_ALIASES: AliasMap = {
    "sku": "sku",
    "part number": "sku",
    "product code": "sku",
    "title": "source_title",
    "product title": "source_title",
    "source_title": "source_title",
    "brand": "brand",
    "mpn": "mpn",
    "oem": "oem_numbers",
    "oem_numbers": "oem_numbers",
    "price": "price",
    "cost": "price",
    "quantity": "quantity",
    "qty": "quantity",
}


@dataclass
class IngestResult:
    accepted: int
    rejected: int
    output: Path
    rejects: Path


def _csv_rows(path: Path) -> Iterator[dict[str, str]]:
    raw = path.read_bytes()[:65536]
    if not raw:
        return
    encoding = "utf-8-sig"
    try:
        raw.decode(encoding)
    except UnicodeDecodeError:
        encoding = "cp1252"
    with path.open("r", encoding=encoding, newline="") as handle:
        preview = raw.decode(encoding, errors="replace")
        try:
            dialect = csv.Sniffer().sniff(preview, delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        reader = csv.reader(handle, dialect)
        header = next(reader, None)
        if header is None:
            return
        yield from _rows_from_cells(header, reader)


def _xlsx_rows(path: Path) -> Iterator[dict[str, str]]:
    try:
        from openpyxl import load_workbook
    except ImportError as exc:
        raise RuntimeError("XLSX requires optional openpyxl dependency") from exc
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        sheet = workbook.active
        if sheet is None:
            return
        cells = sheet.iter_rows(values_only=True)
        header = next(cells, None)
        if header is None:
            return
        yield from _rows_from_cells(header, cells)
    finally:
        workbook.close()


def _rows_from_cells(
    header: tuple[Any, ...] | list[Any],
    rows: Iterator[tuple[Any, ...]] | Iterator[list[str]],
) -> Iterator[dict[str, str]]:
    names = [str(x or "").strip() for x in header]
    nonempty = [x.casefold() for x in names if x]
    if not nonempty:
        raise ValueError("headers_missing")
    if len(nonempty) != len(set(nonempty)):
        raise ValueError("duplicate_headers")
    for values in rows:
        if not any(str(x or "").strip() for x in values):
            continue
        if len(values) > len(names) and any(
            str(x or "").strip() for x in values[len(names):]
        ):
            raise ValueError("unexpected_extra_columns")
        out: dict[str, str] = {}
        for index, header_name in enumerate(names):
            if not header_name:
                continue
            cell = values[index] if index < len(values) else ""
            text = "" if cell is None else str(cell)
            if isinstance(cell, float) and abs(cell) >= 1e14:
                text = ""
            out[header_name] = text
        yield out


def _mapped(row: dict[str, str], aliases: AliasMap) -> dict[str, str]:
    mapped: dict[str, str] = {}
    for header, value in row.items():
        destination = aliases.get(header.casefold().strip(), header.casefold().strip())
        if destination in mapped and value:
            raise ValueError("duplicate_mapped_columns")
        mapped[destination] = value
    return mapped


def _merge(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    merged = dict(old)
    for key, value in new.items():
        if value not in (None, "", [], {}):
            merged[key] = value
    return merged


def ingest(
    path: Path,
    output: Path,
    rejects: Path,
    *,
    duplicate_policy: DuplicatePolicy = "error",
    locale: str = "en_US",
    aliases: AliasMap | None = None,
    sku_case_sensitive: bool = False,
) -> IngestResult:
    """Stream input and write JSONL with rejects CSV. Uses temporary SQLite for dedupe."""
    if duplicate_policy not in {"error", "first", "last", "merge"}:
        raise ValueError("duplicate_policy_invalid")
    mapping = DEFAULT_ALIASES | (aliases or {})
    reader = _xlsx_rows(path) if path.suffix.lower() == ".xlsx" else _csv_rows(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    rejects.parent.mkdir(parents=True, exist_ok=True)
    count = rejected = 0
    with tempfile.TemporaryDirectory() as tempdir:
        db = sqlite3.connect(Path(tempdir) / "rows.sqlite3")
        try:
            db.execute(
                "CREATE TABLE rows (sku TEXT PRIMARY KEY, idx INTEGER, payload TEXT NOT NULL)"
            )
            with rejects.open("w", encoding="utf-8", newline="") as reject_file:
                writer = csv.writer(reject_file)
                writer.writerow(["row_number", "reason_code"])
                for row_number, raw_row in enumerate(reader, start=2):
                    try:
                        row = normalize_row(_mapped(raw_row, mapping), locale=locale)
                        sku = row["sku"] if sku_case_sensitive else row["sku"].casefold()
                        prev = db.execute(
                            "SELECT idx, payload FROM rows WHERE sku=?", (sku,)
                        ).fetchone()
                        if prev is not None and duplicate_policy == "error":
                            raise ValueError("sku_duplicate")
                        if prev is not None and duplicate_policy == "first":
                            continue
                        if prev is not None and duplicate_policy == "merge":
                            row = _merge(json.loads(prev[1]), row)
                        if prev is None:
                            db.execute(
                                "INSERT INTO rows(sku,idx,payload) VALUES(?,?,?)",
                                (sku, row_number, json.dumps(row, ensure_ascii=False)),
                            )
                        else:
                            db.execute(
                                "UPDATE rows SET payload=? WHERE sku=?",
                                (json.dumps(row, ensure_ascii=False), sku),
                            )
                    except (ValueError, TypeError, OverflowError) as exc:
                        writer.writerow([row_number, str(exc)])
                        rejected += 1
            temp_output = output.with_suffix(output.suffix + ".tmp")
            try:
                with temp_output.open("w", encoding="utf-8", newline="\n") as destination:
                    for (payload,) in db.execute(
                        "SELECT payload FROM rows ORDER BY idx"
                    ):
                        destination.write(payload + "\n")
                        count += 1
                temp_output.replace(output)
            finally:
                temp_output.unlink(missing_ok=True)
        finally:
            db.close()
    return IngestResult(count, rejected, output, rejects)
