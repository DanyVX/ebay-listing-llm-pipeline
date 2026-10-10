"""Typed protocol and deterministic replay: no real provider access in M0."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class LLMRequest:
    prompt_version: str
    payload: str


@dataclass(frozen=True)
class LLMResponse:
    model: str
    text: str
    input_tokens: int
    output_tokens: int


class LLMClient(Protocol):
    async def generate(self, request: LLMRequest) -> LLMResponse: ...


class FixtureClient:
    """Synthetic cassette-style responses keyed by explicit request payload."""

    def __init__(self, fixtures: dict[str, LLMResponse]) -> None:
        self._fixtures = dict(fixtures)

    async def generate(self, request: LLMRequest) -> LLMResponse:
        try:
            return self._fixtures[request.payload]
        except KeyError as exc:
            raise ValueError("offline fixture missing; live fallback is forbidden") from exc
