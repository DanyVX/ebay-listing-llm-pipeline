import asyncio

import pytest

from elp.llm.protocol import FixtureClient, LLMRequest, LLMResponse


def test_offline_fixture_response():
    reply = LLMResponse(
        model="fixture-local", text='{"title":"Synthetic"}', input_tokens=5, output_tokens=8
    )
    client = FixtureClient({"row-a": reply})
    received = asyncio.run(client.generate(LLMRequest("v1", "row-a")))
    assert received == reply


def test_fixture_missing_fails_closed():
    client = FixtureClient({})
    with pytest.raises(ValueError, match="live fallback is forbidden"):
        asyncio.run(client.generate(LLMRequest("v1", "missing")))
