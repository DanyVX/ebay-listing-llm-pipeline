"""Opt-in HTTP adapters. No network calls without API keys and budget reservation."""

import asyncio
import json
import random
from dataclasses import dataclass
from typing import Any, Literal

import httpx

from elp.budget import BudgetLedger, estimate_max_usd
from elp.llm.protocol import LLMRequest, LLMResponse


@dataclass(frozen=True)
class ProviderConfig:
    kind: Literal["openai_compatible", "anthropic"]
    model: str
    base_url: str
    api_key: str
    input_per_million_usd: str
    output_per_million_usd: str
    max_output_tokens: int = 1024
    timeout_seconds: int = 45

    def __post_init__(self) -> None:
        if not self.api_key or not self.model:
            raise ValueError("provider key and explicit model ID required")
        if not self.base_url.startswith("https://") and not self.base_url.startswith(
            ("http://127.0.0.1:", "http://localhost:")
        ):
            raise ValueError("remote provider requires HTTPS")


class BudgetedHttpClient:
    def __init__(self, config: ProviderConfig, ledger: BudgetLedger, run_id: str) -> None:
        self.config = config
        self.ledger = ledger
        self.run_id = run_id

    async def generate(self, request: LLMRequest) -> LLMResponse:
        from decimal import Decimal
        from uuid import uuid4

        cfg = self.config
        estimated_input = len(request.payload.encode("utf-8")) + 4096
        charge = estimate_max_usd(
            estimated_input,
            cfg.max_output_tokens,
            Decimal(cfg.input_per_million_usd),
            Decimal(cfg.output_per_million_usd),
        )
        request_id = uuid4().hex
        self.ledger.reserve(request_id, self.run_id, charge)
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if cfg.kind == "anthropic":
            headers |= {"x-api-key": cfg.api_key, "anthropic-version": "2023-06-01"}
            payload: dict[str, Any] = {
                "model": cfg.model,
                "max_tokens": cfg.max_output_tokens,
                "messages": [{"role": "user", "content": request.payload}],
            }
            url = cfg.base_url.rstrip("/") + "/v1/messages"
        else:
            headers["Authorization"] = "Bearer " + cfg.api_key
            payload = {
                "model": cfg.model,
                "messages": [{"role": "user", "content": request.payload}],
                "temperature": 0,
                "max_tokens": cfg.max_output_tokens,
                "response_format": {"type": "json_object"},
            }
            url = cfg.base_url.rstrip("/") + "/chat/completions"
        try:
            async with httpx.AsyncClient(timeout=cfg.timeout_seconds) as http:
                for attempt in range(4):
                    reply = await http.post(url, json=payload, headers=headers)
                    if reply.status_code in {429, 500, 502, 503, 504} and attempt < 3:
                        await asyncio.sleep(min(8, (2**attempt) + random.random()))
                        continue
                    reply.raise_for_status()
                    break
            body = reply.json()
            if cfg.kind == "anthropic":
                content = "".join(part.get("text", "") for part in body["content"])
                tokens_in = int(body.get("usage", {}).get("input_tokens", 0))
                tokens_out = int(body.get("usage", {}).get("output_tokens", 0))
            else:
                content = body["choices"][0]["message"]["content"]
                tokens_in = int(body.get("usage", {}).get("prompt_tokens", 0))
                tokens_out = int(body.get("usage", {}).get("completion_tokens", 0))
            actual = estimate_max_usd(
                tokens_in,
                tokens_out,
                Decimal(cfg.input_per_million_usd),
                Decimal(cfg.output_per_million_usd),
            )
            self.ledger.settle(request_id, actual)
            return LLMResponse(
                model=body.get("model", cfg.model),
                text=content,
                input_tokens=tokens_in,
                output_tokens=tokens_out,
                cost_usd=actual,
            )
        except (httpx.HTTPError, KeyError, ValueError, json.JSONDecodeError):
            # Reservation remains held if a provider may have charged before failure.
            raise
