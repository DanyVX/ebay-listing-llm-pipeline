"""Conservative prompt-injection triage for untrusted supplier text."""

import re
import unicodedata
from dataclasses import dataclass

from elp.schema import InputRow

DIRECTIVES = [
    r"ignore\s+(?:all\s+)?(?:previous\s+)?(?:instructions|rules|prompts)",
    r"disregard\s+(?:the\s+)?(?:system|instructions|rules)",
    r"(?:system|developer)\s*prompt\s*:",
    r"you\s+are\s+now\b",
    r"act\s+as\s+(?:an?\s+)?(?:assistant|system|developer)",
    r"new\s+(?:instruction|directive|role)\s*:",
    r"print\s+(?:my|the)\s+(?:api\s*)?(?:key|secret|token)",
    r"(?:output|respond|write|say|append|include|add)\s+(?:exactly|only|this|the|my)",
    r"always\s+(?:write|state|include|output|add)",
    r"\[\s*(?:system|developer|assistant)\s*\]",
    r"<\s*(?:system|developer|assistant)[ >]",
    r"忘记.{0,15}(?:指令|规则)",
    r"忽略.{0,15}(?:指令|规则)",
    r"(?:تمام|سابقہ)\s+ہدایات\s+(?:نظرانداز|بھول)",
    r"(?:instrucciones|reglas)\s+anteriores",
    r"www\.evil\.example",
    r"evil\.example",
]
PATTERN = re.compile("|".join(f"(?:{x})" for x in DIRECTIVES), re.IGNORECASE | re.DOTALL)
ZERO_WIDTH = dict.fromkeys(map(ord, "\u200b\u200c\u200d\ufeff"), None)
CONFUSABLES = str.maketrans({"і": "i", "о": "o", "а": "a", "е": "e", "р": "p"})


@dataclass(frozen=True)
class InjectionReport:
    flagged_fields: tuple[str, ...]
    sanitized: InputRow
    blocked: bool


def _canonical(value: str) -> str:
    return unicodedata.normalize("NFKC", value).translate(ZERO_WIDTH).translate(
        CONFUSABLES
    )


def _sanitize(value: str) -> tuple[str, bool]:
    canonical = _canonical(value)
    match = PATTERN.search(canonical)
    if not match:
        return value, False
    safe_prefix = value[: match.start()].strip(" \t\n\r-:;.,")
    return safe_prefix, True


def screen_input(row: InputRow) -> InjectionReport:
    """Strip obvious role directives and fail closed on unusable identity/title."""
    flagged: list[str] = []
    replacement: dict[str, object] = {}
    for key in ("source_title", "notes", "brand", "mpn"):
        value = getattr(row, key)
        sanitized, suspicious = _sanitize(value)
        if suspicious:
            replacement[key] = sanitized
            flagged.append(key)
    attributes = dict(row.attributes)
    for name, value in attributes.items():
        sanitized, suspicious = _sanitize(value)
        if suspicious:
            attributes[name] = sanitized
            flagged.append("attributes." + name)
    replacement["attributes"] = attributes
    cleaned = row.model_copy(update=replacement)
    blocked = not cleaned.source_title.strip() or (
        "brand" in flagged or "mpn" in flagged
    )
    return InjectionReport(tuple(flagged), cleaned, blocked)
