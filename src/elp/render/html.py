"""The LLM never writes HTML; only escaped values enter a fixed versioned template."""

from pathlib import Path

import nh3
from jinja2 import Environment, FileSystemLoader, select_autoescape

from elp.schema import InputRow, ListingDraft

TEMPLATE_VERSION = "v1"
ALLOWED = {"div", "p", "h2", "strong", "ul", "li", "table", "thead", "tbody", "tr", "th", "td"}
ATTRIBUTES: dict[str, set[str]] = {"div": {"dir"}, "p": {"dir"}, "td": {"dir"}}


def render_description(draft: ListingDraft, source: InputRow, *, fitment_limit: int = 100) -> str:
    if fitment_limit < 0 or fitment_limit > 1000:
        raise ValueError("fitment limit must be 0..1000")
    env = Environment(
        loader=FileSystemLoader(str(Path(__file__).parent / "templates")),
        autoescape=select_autoescape(default=True),
    )
    template = env.get_template("v1.html.j2")
    fitment = draft.compatibility[:fitment_limit]
    rendered = template.render(
        title=draft.title,
        bullets=draft.bullet_points,
        specifics=sorted(draft.item_specifics.items()),
        condition_note=draft.condition_note,
        compatibility=fitment,
        omitted=max(0, len(draft.compatibility) - len(fitment)),
    )
    return nh3.clean(rendered, tags=ALLOWED, attributes=ATTRIBUTES, url_schemes=set())
