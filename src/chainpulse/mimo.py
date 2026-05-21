"""Async client for Xiaomi MiMo API (OpenAI-compatible Chat Completions).

Usage:
    client = MiMoClient(api_key="sk-...")
    analysis = await client.analyze(system_prompt, user_message)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import httpx

MIMO_BASE_URL = "https://api.xiaomimimo.com/v1"
MIMO_DEFAULT_MODEL = "mimo-7b-rl"


class MiMoError(RuntimeError):
    """Raised on MiMo API errors."""


@dataclass
class MiMoResponse:
    """Parsed response from MiMo chat completions."""

    content: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    raw: dict[str, Any] = field(default_factory=dict)


class MiMoClient:
    """Thin async wrapper around MiMo's OpenAI-compatible API."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str | None = None,
        model: str = MIMO_DEFAULT_MODEL,
        timeout: float = 30.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.api_key = api_key or os.environ.get("MIMO_API_KEY", "")
        self.base_url = (base_url or os.environ.get("MIMO_BASE_URL", MIMO_BASE_URL)).rstrip("/")
        self.model = model
        self.timeout = timeout
        self._client = client
        self._owns_client = client is None

    async def __aenter__(self) -> MiMoClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": "chainpulse/0.1",
                },
            )
        return self

    async def __aexit__(self, *_exc: object) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 1024,
        **kwargs: Any,
    ) -> MiMoResponse:
        """Send a chat completion request and return parsed response."""
        if self._client is None:
            raise RuntimeError("MiMoClient must be used as an async context manager")

        if not self.api_key:
            raise MiMoError(
                "MIMO_API_KEY not set. Export it or pass api_key= to MiMoClient."
            )

        payload: dict[str, Any] = {
            "model": model or self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs,
        }

        resp = await self._client.post(
            f"{self.base_url}/chat/completions",
            json=payload,
        )

        if resp.status_code != 200:
            raise MiMoError(f"MiMo API returned {resp.status_code}: {resp.text[:200]}")

        data = resp.json()

        if "error" in data:
            raise MiMoError(f"MiMo error: {data['error']}")

        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        usage = data.get("usage", {})

        return MiMoResponse(
            content=message.get("content", ""),
            model=data.get("model", model or self.model),
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            raw=data,
        )

    async def analyze(
        self,
        system_prompt: str,
        user_message: str,
        *,
        model: str | None = None,
        temperature: float = 0.2,
    ) -> str:
        """Convenience: send system + user message, return content string."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]
        resp = await self.chat(messages, model=model, temperature=temperature)
        return resp.content
