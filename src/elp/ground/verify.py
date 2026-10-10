"""Conservative deterministic source-to-draft fact verification."""

import re
from dataclasses import dataclass
from typing import Any

from elp.rules.engine import canonical
from elp.schema import InputRow, ListingDraft

_PART = re.compile(r"(?<!\w)(?:[A-Za-z0-9]+[-./])*[A-Za-z]*\d[A-Za-z0-9./-]*(?!\w)")
_MARKETING = {"durable", "premium", "unbreakable", "world class", "high performance"}
_ALLOWED_PROVENANCE = {
    "sku",
    "source_title",
    "brand",
    "mpn",
    "original_mpn",
    "oem_numbers",
    "condition",
    "category_hint",
    "price",
    "quantity",
    "fitment",
    "attributes",
    "weight",
    "notes",
    "image_urls",
}


@dataclass(frozen=True)
class GroundingReport:
    score: float
    ungrounded_claims: tuple[str, ...]
    provenance: dict[str, list[str]]
    checked_claims: int


def _tokenize(value: str) -> set[str]:
    return {canonical(x) for x in _PART.findall(value) if canonical(x)}


def _fitment_identity(item: Any) -> tuple[str, str, int, int, str]:
    return (
        canonical(item.make),
        canonical(item.model),
        int(item.year_from),
        int(item.year_to),
        canonical(item.engine),
    )


def verify_draft(row: InputRow, draft: ListingDraft) -> GroundingReport:
    violations: list[str] = []
    supported = 0
    checked = 0

    source_strings = [
        row.source_title,
        row.brand,
        row.mpn,
        *row.oem_numbers,
        row.condition,
        row.category_hint,
        row.notes,
        *row.attributes.keys(),
        *row.attributes.values(),
    ]
    if row.weight:
        source_strings.extend(str(x) for x in row.weight.values())
    allowed_tokens = set()
    for value in source_strings:
        allowed_tokens |= _tokenize(value)
    for fitment in row.fitment:
        allowed_tokens |= _tokenize(" ".join([fitment.make, fitment.model, fitment.engine]))
        allowed_tokens |= {str(year) for year in range(fitment.year_from, fitment.year_to + 1)}
    # Year-range expansion is a documented, source-grounded transformation.
    output_fitments = {_fitment_identity(x) for x in row.fitment}
    for index, fitment in enumerate(draft.compatibility):
        checked += 1
        if _fitment_identity(fitment) not in output_fitments:
            violations.append(f"compatibility[{index}]: not in supplied fitment")
        else:
            supported += 1

    output_fields: list[tuple[str, str]] = [("title", draft.title)]
    output_fields += [(f"item_specifics.{k}", v) for k, v in draft.item_specifics.items()]
    output_fields += [(f"bullet_points[{i}]", x) for i, x in enumerate(draft.bullet_points)]
    output_fields += [(f"search_keywords[{i}]", x) for i, x in enumerate(draft.search_keywords)]
    output_fields.append(("condition_note", draft.condition_note))
    for field, value in output_fields:
        candidates = _tokenize(value)
        for token in sorted(candidates):
            checked += 1
            if token in allowed_tokens:
                supported += 1
            else:
                violations.append(f"{field}: unsupported part/spec token {token!r}")
        norm = canonical(value)
        for adjective in sorted(_MARKETING):
            if adjective in norm and adjective not in canonical(" ".join(source_strings)):
                checked += 1
                violations.append(f"{field}: unsupported marketing claim {adjective!r}")
    if draft.item_specifics.get("Brand"):
        checked += 1
        if canonical(draft.item_specifics["Brand"]) == canonical(row.brand):
            supported += 1
        else:
            violations.append("item_specifics.Brand: unsupported brand")
    if draft.item_specifics.get("MPN"):
        checked += 1
        if canonical(draft.item_specifics["MPN"]) == canonical(row.mpn):
            supported += 1
        else:
            violations.append("item_specifics.MPN: unsupported part number")

    # The provider's provenance annotation is not proof; validate declared keys.
    validated_provenance: dict[str, list[str]] = {}
    for field, input_fields in draft.provenance.items():
        valid = [x for x in input_fields if x.split(".", 1)[0] in _ALLOWED_PROVENANCE]
        if len(valid) != len(input_fields):
            violations.append(f"provenance.{field}: unknown source field")
            checked += 1
        validated_provenance[field] = valid
    return GroundingReport(
        score=supported / checked if checked else 1.0,
        ungrounded_claims=tuple(violations),
        provenance=validated_provenance,
        checked_claims=checked,
    )
