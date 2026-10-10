"""Loss-aware normalization for untrusted supplier fields."""

import html
import json
import re
import unicodedata
from decimal import Decimal, InvalidOperation
from typing import Any

ZERO_WIDTH = dict.fromkeys(map(ord, "\u200b\u200c\u200d\ufeff"), None)
UNITS: dict[str, tuple[str, Decimal]] = {
    "mm": ("mm", Decimal("1")),
    "cm": ("mm", Decimal("10")),
    "in": ("mm", Decimal("25.4")),
    "inch": ("mm", Decimal("25.4")),
    "inches": ("mm", Decimal("25.4")),
    "g": ("g", Decimal("1")),
    "kg": ("g", Decimal("1000")),
    "lb": ("g", Decimal("453.59237")),
    "lbs": ("g", Decimal("453.59237")),
    "oz": ("g", Decimal("28.349523125")),
}


def clean_text(raw: object) -> str:
    value = unicodedata.normalize("NFKC", html.unescape(str(raw or "")))
    return " ".join(value.translate(ZERO_WIDTH).split())


def preserve_identifier(value: object) -> str:
    text = clean_text(value)
    if text.startswith('="') and text.endswith('"'):
        return text[2:-1]
    return text


def decimal_price(raw: object, locale: str = "en_US") -> Decimal:
    value = clean_text(raw).replace("$", "").replace("€", "").replace("£", "")
    value = value.replace(" ", "")
    if not value:
        raise ValueError("price_missing")
    if locale in {"de_DE", "fr_FR", "pt_BR"}:
        value = value.replace(".", "").replace(",", ".")
    elif locale == "en_US":
        value = value.replace(",", "")
    else:
        raise ValueError("locale_unsupported")
    try:
        amount = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("price_invalid") from exc
    if not amount.is_finite() or amount <= 0:
        raise ValueError("price_nonpositive")
    return amount


def normalize_unit(raw: object) -> dict[str, str]:
    text = clean_text(raw)
    match = re.fullmatch(r"([+]?(?:\d+(?:[.,]\d+)?))\s*([a-zA-Z]+)", text)
    if not match:
        raise ValueError("unit_invalid_or_missing")
    value = Decimal(match.group(1).replace(",", "."))
    symbol = match.group(2).lower()
    if symbol not in UNITS:
        raise ValueError("unit_unknown")
    target, multiplier = UNITS[symbol]
    return {
        "original": text,
        "normalized_value": str(value * multiplier),
        "normalized_unit": target,
    }


def years(raw: object) -> tuple[int, int]:
    text = clean_text(raw)
    match = re.fullmatch(r"(\d{4})\s*[-~–]\s*(\d{4})", text)
    if not match:
        raise ValueError("year_range_ambiguous_or_invalid")
    first, last = map(int, match.groups())
    if first < 1886 or last > 2100 or first > last:
        raise ValueError("year_range_invalid")
    return first, last


def language_hint(title: str) -> str:
    if re.search(r"[\u0600-\u06ff]", title):
        return "urdu_or_arabic"
    if re.search(r"[\u4e00-\u9fff]", title):
        return "chinese"
    return "und"


def list_field(raw: object) -> list[str]:
    text = clean_text(raw)
    if not text:
        return []
    if text.startswith("["):
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError("list_invalid_json") from exc
        if not isinstance(data, list) or not all(isinstance(x, str) for x in data):
            raise ValueError("list_invalid_items")
        return [preserve_identifier(x) for x in data if clean_text(x)]
    return [preserve_identifier(x) for x in text.split("|") if clean_text(x)]


def fitment_field(raw: object) -> list[dict[str, Any]]:
    text = clean_text(raw)
    if not text:
        return []
    try:
        items = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("fitment_invalid_json") from exc
    if not isinstance(items, list):
        raise ValueError("fitment_not_a_list")
    output: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("fitment_invalid_entry")
        if not item.get("make") or not item.get("model"):
            raise ValueError("fitment_make_model_missing")
        first, last = years(
            f"{item.get('year_from')}-{item.get('year_to')}"
        )
        output.append(
            {
                "make": clean_text(item["make"]),
                "model": clean_text(item["model"]),
                "year_from": first,
                "year_to": last,
                "engine": clean_text(item.get("engine")),
            }
        )
    return output


def normalize_row(row: dict[str, str], locale: str = "en_US") -> dict[str, Any]:
    sku = preserve_identifier(row.get("sku", ""))
    title = clean_text(row.get("source_title", ""))
    if not sku:
        raise ValueError("sku_missing")
    if not title:
        raise ValueError("title_missing")
    if len(title) > 100_000:
        raise ValueError("title_oversized")
    price = decimal_price(row.get("price", ""), locale)
    quantity = clean_text(row.get("quantity", ""))
    if not re.fullmatch(r"\d+", quantity):
        raise ValueError("quantity_invalid")
    identifiers = list_field(row.get("oem_numbers", ""))
    image_urls = list_field(row.get("image_urls", ""))
    if any(not x.startswith(("https://", "http://")) for x in image_urls):
        raise ValueError("image_url_invalid")
    attributes_raw = clean_text(row.get("attributes", ""))
    try:
        attributes = json.loads(attributes_raw) if attributes_raw else {}
    except json.JSONDecodeError as exc:
        raise ValueError("attributes_invalid_json") from exc
    if not isinstance(attributes, dict) or any(
        not isinstance(k, str) or not isinstance(v, (str, int, float))
        for k, v in attributes.items()
    ):
        raise ValueError("attributes_invalid")
    weight = clean_text(row.get("weight", ""))
    return {
        "sku": sku,
        "source_title": title,
        "brand": clean_text(row.get("brand", "")),
        "mpn": preserve_identifier(row.get("mpn", "")),
        "oem_numbers": identifiers,
        "condition": clean_text(row.get("condition", "New")) or "New",
        "category_hint": clean_text(row.get("category_hint", "")),
        "price": str(price),
        "quantity": int(quantity),
        "image_urls": list(dict.fromkeys(image_urls)),
        "fitment": fitment_field(row.get("fitment", "")),
        "attributes": {clean_text(k): clean_text(v) for k, v in attributes.items()},
        "weight": normalize_unit(weight) if weight else None,
        "notes": clean_text(row.get("notes", "")),
        "language_hint": language_hint(title),
        "original_mpn": row.get("mpn", ""),
    }
