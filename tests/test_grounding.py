from elp.ground.verify import verify_draft
from elp.schema import InputRow, ListingDraft
from elp.schema.models import CategorySuggestion, InputFitment


def case():
    source = InputRow(
        sku="SYN-101",
        source_title="Synthetic 12V headlamp",
        brand="DemoBrand",
        mpn="DEMO-101",
        price="10",
        quantity=1,
        attributes={"Voltage": "12 V", "Thread": "M8"},
        fitment=[InputFitment(make="ExampleMake", model="Sample", year_from=2005, year_to=2010)],
    )
    draft = ListingDraft(
        title="Synthetic 12V headlamp",
        category_suggestion=CategorySuggestion(name="Sample parts", confidence=0.5),
        item_specifics={"Brand": "DemoBrand", "MPN": "DEMO-101", "Voltage": "12V"},
        compatibility=source.fitment,
        provenance={"title": ["source_title"], "compatibility": ["fitment"]},
    )
    return source, draft


def test_grounded_draft_has_no_unattributed_tokens():
    source, draft = case()
    report = verify_draft(source, draft)
    assert not report.ungrounded_claims
    assert report.score == 1


def test_planted_part_number_is_flagged():
    source, draft = case()
    bad = draft.model_copy(update={"title": "Synthetic DEMO-999 12V headlamp"})
    assert any("demo 999" in x for x in verify_draft(source, bad).ungrounded_claims)


def test_planted_year_is_flagged():
    source, draft = case()
    bad = draft.model_copy(update={"title": "2023 Synthetic 12V headlamp"})
    assert any("2023" in x for x in verify_draft(source, bad).ungrounded_claims)


def test_fitment_injection_rejected():
    source, draft = case()
    extra = InputFitment(make="OtherMake", model="Other", year_from=2019, year_to=2019)
    bad = draft.model_copy(update={"compatibility": [extra]})
    assert any("compatibility" in x for x in verify_draft(source, bad).ungrounded_claims)


def test_brand_and_mpn_mismatch_rejected():
    source, draft = case()
    bad = draft.model_copy(update={"item_specifics": {"Brand": "Unknown", "MPN": "FAKE-999"}})
    issues = verify_draft(source, bad).ungrounded_claims
    assert any("unsupported brand" in x for x in issues)
    assert any("unsupported part number" in x for x in issues)


def test_unverified_provenance_is_stripped_and_reported():
    source, draft = case()
    bad = draft.model_copy(update={"provenance": {"title": ["invented_field"]}})
    result = verify_draft(source, bad)
    assert result.provenance["title"] == []
    assert any("unknown source field" in x for x in result.ungrounded_claims)


def test_generic_claim_without_source_support_flagged():
    source, draft = case()
    bad = draft.model_copy(update={"bullet_points": ["Premium durable construction"]})
    issues = verify_draft(source, bad).ungrounded_claims
    assert any("marketing" in x for x in issues)


def test_year_inside_supplied_fitment_range_is_grounded():
    source, draft = case()
    good = draft.model_copy(update={"title": "Synthetic 2008 12V headlamp"})
    assert not verify_draft(source, good).ungrounded_claims
