from elp.render import render_description
from elp.schema import InputRow, ListingDraft
from elp.schema.models import CategorySuggestion, InputFitment


def sample():
    source = InputRow(sku="SYN-88", source_title="Synthetic kit", price="10", quantity=3)
    draft = ListingDraft(
        title="Synthetic kit",
        category_suggestion=CategorySuggestion(name="Sample parts", confidence=0),
        item_specifics={"Brand": "FictionalBrand"},
        bullet_points=["Lightweight plastic"],
        condition_note="New",
    )
    return draft, source


def test_html_is_locked_and_has_expected_sections():
    draft, source = sample()
    html = render_description(draft, source)
    assert "<h2>Overview</h2>" in html
    assert "Specifications" in html
    assert "Shipping and returns" in html
    assert "<script" not in html.lower()


def test_injected_markup_in_all_structured_values_is_escaped():
    draft, source = sample()
    attack = '<script>alert("x")</script><img src=x onerror=alert(1)>'
    poisoned = draft.model_copy(
        update={
            "title": attack,
            "condition_note": attack,
            "item_specifics": {attack: attack},
            "bullet_points": [attack],
        }
    )
    result = render_description(poisoned, source)
    assert "<script" not in result.lower()
    assert "<img" not in result.lower()
    assert "&lt;img" in result.lower()


def test_long_fitment_table_is_bounded():
    draft, source = sample()
    entries = [
        InputFitment(make="Fictional", model=f"Variant-{i}", year_from=2001, year_to=2002)
        for i in range(500)
    ]
    result = render_description(draft.model_copy(update={"compatibility": entries}), source)
    assert "Additional 400 supplied compatibility entries omitted" in result
    assert "Variant-499" not in result


def test_rtl_title_and_missing_sections():
    draft, source = sample()
    clean = draft.model_copy(
        update={
            "title": "اردو نمونہ",
            "bullet_points": [],
            "item_specifics": {},
            "condition_note": "",
        }
    )
    rendered = render_description(clean, source)
    assert 'dir="auto"' in rendered
    assert "Specifications" not in rendered


def test_invalid_fitment_limit_fails():
    draft, source = sample()
    import pytest

    with pytest.raises(ValueError):
        render_description(draft, source, fitment_limit=-1)
