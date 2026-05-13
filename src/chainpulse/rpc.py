"""Async JSON-RPC client with multi-endpoint fallback.

Each chain has 1+ public RPC URLs. We try them in order on connection / 5xx /
rate-limit errors so a single flaky endpoint doesn't blank out a row.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

log = logging.getLogger(__name__)


class RpcError(RuntimeError):
    """Raised when every endpoint for a chain failed."""


class JsonRpcClient:
    """Tiny JSON-RPC 2.0 client with fallback across endpoints.

    Usage:
        async with JsonRpcClient(["https://a", "https://b"], timeout=5) as c:
            block = await c.call("eth_blockNumber")
    """

    def __init__(
        self,
        endpoints: list[str] | tuple[str, ...],
        *,
        timeout: float = 6.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not endpoints:
            raise ValueError("at least one endpoint is required")
        self.endpoints = list(endpoints)
        self.timeout = timeout
        self._client = client
        self._owns_client = client is None

    async def __aenter__(self) -> JsonRpcClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                headers={"User-Agent": "chainpulse/0.1"},
            )
        return self

    async def __aexit__(self, *_exc: object) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    async def call(self, method: str, params: list[Any] | None = None) -> Any:
        """Single JSON-RPC call, fall back across endpoints on transient errors."""
        if self._client is None:
            raise RuntimeError("JsonRpcClient must be used as an async context manager")

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params or [],
        }
        last_err: Exception | None = None
        for url in self.endpoints:
            try:
                resp = await self._client.post(url, json=payload)
            except (httpx.ConnectError, httpx.ReadTimeout, httpx.RemoteProtocolError) as e:
                last_err = e
                log.debug("transport error on %s: %s", url, e)
                continue

            if resp.status_code >= 500 or resp.status_code == 429:
                last_err = RpcError(f"{url} returned {resp.status_code}")
                log.debug("retryable status %s on %s", resp.status_code, url)
                continue

            try:
                data = resp.json()
            except ValueError as e:
                last_err = e
                continue

            if "error" in data and data["error"] is not None:
                # JSON-RPC error: don't bother trying other endpoints, the request
                # itself is wrong (bad method, missing param, etc.). Surface it.
                err = data["error"]
                raise RpcError(f"{method} -> {err.get('message', err)}")

            return data.get("result")

        raise RpcError(f"all endpoints failed for {method}: {last_err}")

    async def batch(self, calls: list[tuple[str, list[Any] | None]]) -> list[Any]:
        """Run several calls concurrently against the same chain.

        Each call independently falls back across endpoints. Returns results in
        the same order as input. If a call fails on every endpoint its slot is
        the RpcError instead of a value (so one bad call doesn't sink the row).
        """
        coros = [self._safe_call(m, p) for m, p in calls]
        return await asyncio.gather(*coros)

    async def _safe_call(self, method: str, params: list[Any] | None) -> Any:
        try:
            return await self.call(method, params)
        except RpcError as e:
            return e


def hex_to_int(value: str | int | None) -> int | None:
    """Parse a 0x-prefixed hex string from JSON-RPC results."""
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if not isinstance(value, str):
        return None
    try:
        return int(value, 16)
    except (ValueError, TypeError):
        return None
