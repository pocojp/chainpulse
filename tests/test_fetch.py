"""Tests for fetcher and stats arithmetic."""

from __future__ import annotations

import time

import httpx
import pytest
import respx

from chainpulse.chains import get_chain
from chainpulse.fetch import (
    ERC20_TRANSFER_GAS,
    NATIVE_TRANSFER_GAS,
    ChainStats,
    fetch_chain_stats,
)


def _stats(gas_wei: int | None = None, ts: int | None = None) -> ChainStats:
    return ChainStats(chain=get_chain("base"), gas_wei=gas_wei, block_timestamp=ts)


def test_gas_gwei_conversion() -> None:
    s = _stats(gas_wei=1_500_000_000)  # 1.5 gwei
    assert s.gas_gwei == pytest.approx(1.5)


def test_gas_gwei_none_when_missing() -> None:
    assert _stats().gas_gwei is None


def test_transfer_cost_uses_eth_price_default() -> None:
    s = _stats(gas_wei=1_000_000_000)  # 1 gwei
    cost = s.transfer_cost_usd(NATIVE_TRANSFER_GAS)
    # 1 gwei * 21000 = 21000 gwei = 0.000021 ETH * $2500 = $0.0525
    assert cost == pytest.approx(0.0525, rel=1e-3)


def test_transfer_cost_erc20_higher() -> None:
    s = _stats(gas_wei=1_000_000_000)
    native = s.transfer_cost_usd(NATIVE_TRANSFER_GAS)
    erc20 = s.transfer_cost_usd(ERC20_TRANSFER_GAS)
    assert erc20 > native


def test_block_age_handles_future_timestamp() -> None:
    # if RPC returns a slightly future timestamp due to clock drift, age clamps to 0
    s = _stats(ts=int(time.time()) + 60)
    assert s.block_age_s == 0.0


@respx.mock
async def test_fetch_chain_stats_happy_path() -> None:
    chain = get_chain("base")
    # respond to first endpoint
    respx.post(chain.rpc[0]).mock(
        side_effect=[
            httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": "0x3b9aca00"}),  # 1 gwei
            httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": "0x100"}),
            httpx.Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "result": {
                        "timestamp": hex(int(time.time())),
                        "transactions": ["0x1", "0x2", "0x3"],
                    },
                },
            ),
        ]
    )

    stats = await fetch_chain_stats(chain, timeout=5)
    assert stats.error is None
    assert stats.gas_gwei == pytest.approx(1.0)
    assert stats.block_number == 256
    assert stats.block_tx_count == 3
    assert stats.latency_ms is not None and stats.latency_ms >= 0


@respx.mock
async def test_fetch_chain_stats_records_error_when_all_fail() -> None:
    chain = get_chain("base")
    for url in chain.rpc:
        respx.post(url).mock(return_value=httpx.Response(500))

    stats = await fetch_chain_stats(chain, timeout=2)
    # Either gas_wei is None and error is set, or partial. Verify graceful state.
    assert stats.gas_wei is None
    assert stats.block_number is None
    assert stats.error is not None
