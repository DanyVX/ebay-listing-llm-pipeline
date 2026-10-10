"""Deterministic grounded baseline. A baseline, NOT a pretrained LLM."""

import json

from elp.llm.protocol import LLMRequest, LLMResponse
from elp.schema import InputRow, ListingDraft
from elp.schema.models import CategorySuggestion


class DeterministicClient:
    """Reads only structured input fields; ignores supplier notes as instructions."""

    async def generate(self, request: LLMRequest) -> LLMResponse:
        document = json.loads(request.payload)
        row = InputRow.model_validate(document["input_is_untrusted_data"])
        title = " ".join(row.source_title.split())
        specifics = dict(row.attributes)
        if row.brand:
            specifics["Brand"] = row.brand
        if row.mpn:
            specifics["MPN"] = row.mpn
        draft = ListingDraft(
            title=title,
            category_suggestion=CategorySuggestion(
                name=row.category_hint or "Uncategorized",
                confidence=0.5 if row.category_hint else 0.0,
                alternatives=[],
            ),
            item_specifics=specifics,
            condition_note=row.condition,
            bullet_points=[f"{key}: {value}" for key, value in row.attributes.items()],
            compatibility=row.fitment,
            search_keywords=[x for x in dict.fromkeys([row.brand, row.mpn]) if x],
            provenance={
                "title": ["source_title"],
                "brand": ["brand"] if row.brand else [],
                "mpn": ["mpn"] if row.mpn else [],
                "compatibility": ["fitment"],
                "item_specifics": ["attributes", "brand", "mpn"],
                "condition_note": ["condition"],
            },
        )
        return LLMResponse(
            model="deterministic-baseline",
            text=draft.model_dump_json(),
            input_tokens=0,
            output_tokens=0,
        )
