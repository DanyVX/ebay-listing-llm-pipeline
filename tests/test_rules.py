from pathlib import Path

import pytest

from elp.policy import load_policy
from elp.rules import check_listing, trim_title
from elp.schema import InputRow, ListingDraft
from elp.schema.models import CategorySuggestion


@pytest.fixture
def source():
    return InputRow(
        sku="SYN-1",
        source_title="Synthetic cable housing",
        brand="FakeBrand",
        mpn="TEST-10",
        price="11.00",
        quantity=2,
    )


@pytest.fixture
def draft():
    return ListingDraft(
        title="Synthetic cable housing",
        category_suggestion=CategorySuggestion(name="Synthetic parts", confidence=0),
        item_specifics={"Brand": "FakeBrand", "MPN": "TEST-10"},
        search_keywords=["cable", "housing"],
    )


@pytest.fixture
def config():
    return load_policy(Path("configs/rules.yaml"))


def codes(draft, source, config):
    return [v.code for v in check_listing(draft, source, config)]


@pytest.mark.parametrize(
    ("new_title", "reason"),
    [
        ("A " * 50, "title_over_limit"),
        ("Synthetic part 🚀", "title_emoji"),
        ("Synthetic <script> part", "title_markup"),
        ("housing housing housing housing cable", "keyword_stuffing"),
        ("VISIBLY ALL CAPS SYNTHETIC PRODUCT", "title_all_caps"),
        ("guaranteed best price", "unsupported_promotion"),
        ("www.example.com cable", "off_platform_contact"),
        ("contact me at someone@example.com", "off_platform_contact"),
        ("call +1 (555) 123 4567", "phone_in_listing"),
        ("genuine OEM synthetic headlamp", "unsupported_oem"),
    ],
)
def test_violations_by_title(draft, source, config, new_title, reason):
    assert reason in codes(draft.model_copy(update={"title": new_title}), source, config)


def test_genuine_grounded_title_does_not_raise_oem(source, draft, config):
    trusted = source.model_copy(update={"source_title": "Genuine OEM synthetic cable housing"})
    modified = draft.model_copy(update={"title": "Genuine OEM synthetic cable housing"})
    assert "unsupported_oem" not in codes(modified, trusted, config)


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("Brand", "OtherBrand", "brand_mismatch"),
        ("MPN", "INVENTED-1", "mpn_mismatch"),
    ],
)
def test_mismatched_item_specifics(draft, source, config, field, value, reason):
    changed = draft.model_copy(update={"item_specifics": draft.item_specifics | {field: value}})
    assert reason in codes(changed, source, config)


def test_keyword_duplicate_detection(draft, source, config):
    new = draft.model_copy(update={"search_keywords": ["cable", "CABLE"]})
    assert "duplicate_keywords" in codes(new, source, config)


def test_valid_synthetic_draft_passes(source, draft, config):
    assert not [v for v in check_listing(draft, source, config) if v.severity == "error"]


def test_deterministic_word_boundary_title_trim():
    assert trim_title("A long structured title", 12) == ("A long", True)
    assert trim_title("Short", 80) == ("Short", False)


def test_unverified_category_id_is_rejected(source, draft, config):
    new = draft.model_copy(
        update={"category_suggestion": CategorySuggestion(name="123456", confidence=0)}
    )
    assert "category_unverified_id" in codes(new, source, config)


def test_universal_fit_requires_source_evidence(source, draft, config):
    new = draft.model_copy(update={"title": "Universal fit cable housing"})
    assert "unverified_universal_fit" in codes(new, source, config)
