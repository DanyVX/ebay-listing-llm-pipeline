"""Pydantic v2 models reject ungrounded structure and unknown output keys."""

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class InputFitment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    make: str = Field(min_length=1)
    model: str = Field(min_length=1)
    year_from: int = Field(ge=1886, le=2100)
    year_to: int = Field(ge=1886, le=2100)
    engine: str = ""


class InputRow(BaseModel):
    model_config = ConfigDict(extra="ignore")
    sku: str = Field(min_length=1)
    source_title: str = Field(min_length=1)
    brand: str = ""
    mpn: str = ""
    original_mpn: str = ""
    oem_numbers: list[str] = Field(default_factory=list)
    condition: str = "New"
    category_hint: str = ""
    price: Decimal = Field(gt=0)
    quantity: int = Field(ge=0)
    image_urls: list[HttpUrl] = Field(default_factory=list)
    fitment: list[InputFitment] = Field(default_factory=list)
    attributes: dict[str, str] = Field(default_factory=dict)
    weight: dict[str, str] | None = None
    notes: str = ""
    language_hint: str = "und"


class CategorySuggestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    confidence: float = Field(ge=0, le=1)
    alternatives: list[str] = Field(default_factory=list)


class ListingDraft(BaseModel):
    """Provider-visible structured output. HTML is not model generated."""

    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1)
    category_suggestion: CategorySuggestion
    item_specifics: dict[str, str] = Field(default_factory=dict)
    condition_note: str = ""
    bullet_points: list[str] = Field(default_factory=list)
    compatibility: list[InputFitment] = Field(default_factory=list)
    search_keywords: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    provenance: dict[str, list[str]] = Field(default_factory=dict)

    @field_validator("bullet_points", "search_keywords", "warnings")
    @classmethod
    def no_blanks(cls, values: list[str]) -> list[str]:
        if any(not value.strip() for value in values):
            raise ValueError("list elements must be nonblank")
        return values


class ListingMeta(BaseModel):
    model: str
    prompt_version: str
    rules_version: str
    run_id: str
    tokens_input: int = 0
    tokens_output: int = 0
    cost_usd: Decimal = Decimal("0")
    template_version: str = "v1"
    grounding_score: float | None = None
    prompt_hash: str = ""


class Listing(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sku: str
    title: str
    category_suggestion: CategorySuggestion
    item_specifics: dict[str, str]
    condition_note: str
    bullet_points: list[str]
    compatibility: list[InputFitment]
    search_keywords: list[str]
    warnings: list[str]
    provenance: dict[str, list[str]]
    meta: ListingMeta
    description_html: str = ""
    status: str = "ok"
    violations: list[dict[str, Any]] = Field(default_factory=list)
    ungrounded_claims: list[str] = Field(default_factory=list)
