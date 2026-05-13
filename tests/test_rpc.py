"""Tests for the JSON-RPC client and hex helper."""

from __future__ import annotations

import httpx
import pytest
import respx

from chainpulse.rpc import JsonRpcClient, RpcError, hex_to_int


def test_hex_to_int_handles_strings_ints_none() -> None:
    assert hex_to_int("0x10") == 16
    assert hex_to_int("0x0") == 0
    assert hex_to_int(42) == 42
    assert hex_to_int(None) is None
    assert hex_to_int("garbage") is None
    assert hex_to_int({"x": 1}) is None  # type: ignore[arg-type]


def test_client_requires_endpoints() -> None:
    with pytest.raises(ValueError):
        JsonRpcClient([])


def test_call_outside_context_raises() -> None:
    client = JsonRpcClient(["https://example.com"])
    with pytest.raises(RuntimeError):
        # not in async context — but call is async, so we trigger via asyncio.run
        import asyncio

        asyncio.run(client.call("eth_blockNumber"))


@respx.mock
async def test_call_returns_result() -> None:
    respx.post("https://rpc.test/").mock(
        return_value=httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": "0x10"})
    )
    async with JsonRpcClient(["https://rpc.test/"]) as c:
        result = await c.call("eth_blockNumber")
    assert result == "0x10"


@respx.mock
async def test_call_falls_back_to_second_endpoint_on_5xx() -> None:
    respx.post("https://a.test/").mock(return_value=httpx.Response(503))
    respx.post("https://b.test/").mock(
        return_value=httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": "0xff"})
    )
    async with JsonRpcClient(["https://a.test/", "https://b.test/"]) as c:
        result = await c.call("eth_blockNumber")
    assert result == "0xff"


@respx.mock
async def test_call_falls_back_on_connect_error() -> None:
    respx.post("https://a.test/").mock(side_effect=httpx.ConnectError("boom"))
    respx.post("https://b.test/").mock(
        return_value=httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": "0x1"})
    )
    async with JsonRpcClient(["https://a.test/", "https://b.test/"]) as c:
        assert await c.call("eth_blockNumber") == "0x1"


@respx.mock
async def test_call_raises_when_all_endpoints_fail() -> None:
    respx.post("https://a.test/").mock(return_value=httpx.Response(500))
    respx.post("https://b.test/").mock(return_value=httpx.Response(429))
    async with JsonRpcClient(["https://a.test/", "https://b.test/"]) as c:
        with pytest.raises(RpcError):
            await c.call("eth_blockNumber")


@respx.mock
async def test_jsonrpc_error_does_not_fall_back() -> None:
    """A semantic JSON-RPC error means the request itself is wrong; trying the
    next endpoint won't help. We surface it immediately."""
    respx.post("https://a.test/").mock(
        return_value=httpx.Response(
            200,
            json={"jsonrpc": "2.0", "id": 1, "error": {"code": -32601, "message": "method not found"}},
        )
    )
    async with JsonRpcClient(["https://a.test/", "https://b.test/"]) as c:
        with pytest.raises(RpcError, match="method not found"):
            await c.call("nonsense_method")


@respx.mock
async def test_batch_runs_in_parallel_and_captures_errors() -> None:
    respx.post("https://a.test/").mock(
        side_effect=[
            httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": "0x1"}),
            httpx.Response(500),
            httpx.Response(500),
        ]
    )
    async with JsonRpcClient(["https://a.test/"]) as c:
        results = await c.batch([("eth_blockNumber", []), ("eth_gasPrice", [])])
    # first should be the value, second should be an exception object
    assert results[0] == "0x1"
    assert isinstance(results[1], RpcError)
