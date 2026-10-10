"""JSONL and CSV exports. Never publishes to eBay."""

import csv
import json
from pathlib import Path

from elp.schema import Listing


def _safe_cell(raw: str) -> str:
    """Prefix spreadsheet formulas to prevent CSV formula injection."""
    stripped = raw.lstrip(" \t\r\n")
    if stripped.startswith(("=", "+", "-", "@")) or raw.startswith(("\t", "\r", "\n")):
        return "'" + raw
    return raw


def export_listings(source: Path, destination: Path, fmt: str) -> int:
    if fmt not in {"jsonl", "csv"}:
        raise ValueError("format must be jsonl or csv")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    exported = 0
    try:
        with (
            source.open(encoding="utf-8") as raw,
            temporary.open("w", encoding="utf-8", newline="") as target,
        ):
            if fmt == "csv":
                names = [
                    "sku",
                    "title",
                    "category_suggestion",
                    "item_specifics",
                    "condition_note",
                    "description_html",
                    "bullet_points",
                    "compatibility",
                    "search_keywords",
                    "warnings",
                    "status",
                ]
                writer = csv.DictWriter(target, fieldnames=names)
                writer.writeheader()
            for line in raw:
                if not line.strip():
                    continue
                listing = Listing.model_validate_json(line)
                if listing.status not in {"ok", "warn"}:
                    continue
                document = listing.model_dump(mode="json")
                if fmt == "jsonl":
                    target.write(json.dumps(document, ensure_ascii=False) + "\n")
                else:
                    flat = {}
                    for name in names:
                        value = document[name]
                        text = (
                            json.dumps(value, ensure_ascii=False, separators=(",", ":"))
                            if isinstance(value, (dict, list))
                            else str(value)
                        )
                        flat[name] = _safe_cell(text)
                    writer.writerow(flat)
                exported += 1
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return exported
