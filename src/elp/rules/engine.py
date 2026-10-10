"""Pure rule checks; errors block export, warnings demand review."""

import re
import unicodedata
from dataclasses import asdict, dataclass

from elp.policy import PolicyConfig
from elp.schema import InputRow, ListingDraft

ZERO = dict.fromkeys(map(ord, "\u200b\u200c\u200d\ufeff"), None)
HOMOGLYPHS = str.maketrans({"о": "o", "а": "a", "е": "e", "і": "i", "р": "p"})
EMAIL = re.compile(r"(?i)\b[\w.+-]+@[\w.-]+\.[a-z]{2,}\b")
URL = re.compile(r"(?i)(?:https?://|www\.|\b[a-z0-9-]+\.(?:com|net|org|io)\b)")
PHONE = re.compile(r"(?<!\d)(?:\+?\d[\d ()-]{7,}\d)(?!\d)")
EMOJI = re.compile("[\U0001f300-\U0001faff]")
UNSUPPORTED = ("guaranteed", "best price", "limited time", "100 fit", "100 percent fit")
OEM = ("genuine oem", "original equipment manufacturer", "authentic oem")
ALLOWED_TAGS = {"p", "ul", "li", "strong", "table", "thead", "tbody", "tr", "th", "td"}


@dataclass(frozen=True)
class Violation:
    code: str
    severity: str
    field: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def canonical(value: str) -> str:
    text = unicodedata.normalize("NFKC", value).translate(ZERO).translate(HOMOGLYPHS)
    text = re.sub(r"[^\w]+", " ", text.casefold())
    return re.sub(r"\s+", " ", text).strip()


def trim_title(title: str, maximum: int) -> tuple[str, bool]:
    if len(title) <= maximum:
        return title, False
    if maximum <= 0:
        raise ValueError("title maximum must be positive")
    truncated = title[:maximum].rsplit(" ", 1)[0].strip()
    if not truncated:
        truncated = title[:maximum].strip()
    return truncated, True


def _limit(config: PolicyConfig, name: str, default: int) -> int:
    for rule in config.rules:
        if rule.id == name and isinstance(rule.value, int):
            return rule.value
    return default


def check_listing(
    draft: ListingDraft,
    source: InputRow,
    config: PolicyConfig,
) -> list[Violation]:
    """No LLM judgment; all checks have machine-readable reason codes."""
    violations: list[Violation] = []

    def add(code: str, field: str, detail: str, severity: str = "error") -> None:
        violations.append(Violation(code, severity, field, detail))

    title = draft.title
    norm_title = canonical(title)
    maximum = _limit(config, "title_max_chars", 80)
    if len(title) > maximum:
        add("title_over_limit", "title", f"{len(title)} > {maximum}")
    if EMOJI.search(title):
        add("title_emoji", "title", "Emoji is not permitted by local safeguard")
    if "<" in title or ">" in title:
        add("title_markup", "title", "Markup in title is forbidden")
    letters = [x for x in title if x.isalpha()]
    if len(letters) >= 8 and sum(x.isupper() for x in letters) / len(letters) > 0.8:
        add("title_all_caps", "title", "Excessive upper-case shouting", "warn")
    words = norm_title.split()
    if len(words) > 4 and max(words.count(x) for x in set(words)) >= 4:
        add("keyword_stuffing", "title", "Repeated title keywords", "warn")

    all_fields = [("title", draft.title), ("condition_note", draft.condition_note)]
    all_fields += [("bullet_points", x) for x in draft.bullet_points]
    all_fields += [("search_keywords", x) for x in draft.search_keywords]
    all_fields += [("item_specifics." + key, val) for key, val in draft.item_specifics.items()]
    for field, value in all_fields:
        norm = canonical(value)
        if EMAIL.search(value) or URL.search(value):
            add("off_platform_contact", field, "Email or external URL present")
        if PHONE.search(value):
            add("phone_in_listing", field, "Possible contact number")
        if any(phrase in norm for phrase in UNSUPPORTED):
            add("unsupported_promotion", field, "Unverified marketing statement")
        if any(phrase in norm for phrase in OEM):
            supplied = " ".join([source.source_title, source.notes, source.brand, source.mpn])
            if "genuine" not in canonical(supplied) and "oem" not in canonical(supplied):
                add("unsupported_oem", field, "OEM or authenticity claim not supported")
    claimed_brand = draft.item_specifics.get("Brand", "")
    if claimed_brand and canonical(claimed_brand) != canonical(source.brand):
        add("brand_mismatch", "item_specifics.Brand", "Brand must match input brand")
    claimed_mpn = draft.item_specifics.get("MPN", "")
    if claimed_mpn and canonical(claimed_mpn) != canonical(source.mpn):
        add("mpn_mismatch", "item_specifics.MPN", "MPN must match supplier input")
    if len(draft.search_keywords) != len({canonical(k) for k in draft.search_keywords}):
        add("duplicate_keywords", "search_keywords", "Repeated search keywords", "warn")
    if draft.category_suggestion.name.isdigit():
        add("category_unverified_id", "category_suggestion", "Numeric category ID not supplied")
    if len(source.image_urls) > 24:
        add("image_count_review", "image_urls", "High image count needs marketplace review", "warn")
    if source.quantity < 0 or source.price <= 0:
        add("invalid_inventory", "source", "Price and quantity must be valid")
    if (
        not source.fitment
        and any("universal fit" in canonical(value) for _, value in all_fields)
        and "universal" not in canonical(source.source_title)
    ):
        add("unverified_universal_fit", "compatibility", "Universal claim not grounded")
    if config.marketplace != "EBAY_US":
        add("marketplace_review", "config", "Local safeguard limits may differ", "warn")
    return violations
