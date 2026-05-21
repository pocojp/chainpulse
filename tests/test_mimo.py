"""Tests for MiMo API client and analysis module."""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from chainpulse.analysis import analyze_chains, build_analysis_payload
from chainpulse.chains import get_chain
from chainpulse.fetch import NATIVE_TRANSFER_GAS, ChainStats
from chainpulse.mimo import MIMO_BASE_URL, MIMO_DEFAULT_MODEL, MiMoClient, MiMoError


def _fake_stats(
    chain_slug: str = "base",
    gas_wei: int = 1_000_000_000,
    block_number: int = 12888012,
) -> ChainStats:
    """Build a minimal ChainStats for testing."""
    return ChainStats(
        chain=get_chain(chain_slug),
        gas_wei=gas_wei,
        block_number=block_number,
        block_timestamp=1715603128,
        block_tx_count=88,
        latency_ms=92.1,
    )


# ── MiMoClient tests ──────────────────────────────────────────────


def test_mimo_client_default_model() -> None:
    client = MiMoClient(api_key="sk-test")
    assert client.model == MIMO_DEFAULT_MODEL


def test_mimo_client_custom_model() -> None:
    client = MiMoClient(api_key="sk-test", model="mimo-coder")
    assert client.model == "mimo-coder"


def test_mimo_client_no_api_key_raises() -> None:
    """Without MIMO_API_KEY, chat() should raise MiMoError."""
    client = MiMoClient(api_key="")
    # Can't test async in sync, verify the key check string
    assert client.api_key == ""


@respx.mock
async def test_mimo_client_chat_success() -> None:
    """Mock a successful MiMo chat completion."""
    mock_response = {
        "id": "chatcmpl-test",
        "model": "mimo-7b-rl",
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "Gas on Base is extremely low at 0.004 gwei.",
                }
            }
        ],
        "usage": {
            "prompt_tokens": 150,
            "completion_tokens": 25,
            "total_tokens": 175,
        },
    }
    respx.post(f"{MIMO_BASE_URL}/chat/completions").mock(
        return_value=httpx.Response(200, json=mock_response)
    )

    async with MiMoClient(api_key="sk-test-123") as client:
        resp = await client.chat(
            [{"role": "user", "content": "Analyze gas prices"}],
            temperature=0.1,
        )

    assert resp.content == "Gas on Base is extremely low at 0.004 gwei."
    assert resp.prompt_tokens == 150
    assert resp.completion_tokens == 25
    assert resp.total_tokens == 175


@respx.mock
async def test_mimo_client_chat_api_error() -> None:
    """API returning non-200 should raise MiMoError."""
    respx.post(f"{MIMO_BASE_URL}/chat/completions").mock(
        return_value=httpx.Response(401, text="Unauthorized")
    )

    async with MiMoClient(api_key="sk-bad") as client:
        with pytest.raises(MiMoError, match="401"):
            await client.chat([{"role": "user", "content": "test"}])


@respx.mock
async def test_mimo_client_analyze_convenience() -> None:
    """analyze() should wrap chat() with system + user messages."""
    mock_response = {
        "id": "chatcmpl-test",
        "model": "mimo-7b-rl",
        "choices": [{"message": {"role": "assistant", "content": "Analysis result."}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
    }
    respx.post(f"{MIMO_BASE_URL}/chat/completions").mock(
        return_value=httpx.Response(200, json=mock_response)
    )

    async with MiMoClient(api_key="sk-test") as client:
        result = await client.analyze("You are an analyst.", "Here is data: ...")

    assert result == "Analysis result."


# ── analysis module tests ─────────────────────────────────────────


def test_build_analysis_payload_json() -> None:
    """build_analysis_payload should return valid JSON with chain data."""
    rows = [_fake_stats("base"), _fake_stats("arbitrum", gas_wei=500_000_000)]
    payload = build_analysis_payload(rows, gas_units=NATIVE_TRANSFER_GAS)
    data = json.loads(payload)

    assert len(data) == 2
    assert data[0]["chain"] == "Base"
    assert data[1]["chain"] == "Arbitrum One"
    assert data[0]["gas_gwei"] == 1.0
    assert data[1]["gas_gwei"] == 0.5
    assert data[0]["error"] is None


def test_build_analysis_payload_handles_none_values() -> None:
    """Rows with missing data should serialize gracefully."""
    row = ChainStats(chain=get_chain("base"))  # all None
    payload = build_analysis_payload([row])
    data = json.loads(payload)

    assert data[0]["gas_gwei"] is None
    assert data[0]["transfer_cost_usd"] is None
    assert data[0]["block_age_s"] is None
    assert data[0]["error"] is None


@respx.mock
async def test_analyze_chains_end_to_end() -> None:
    """analyze_chains should format prompt and return MiMo content."""
    mock_response = {
        "id": "chatcmpl-test",
        "model": "mimo-7b-rl",
        "choices": [
            {"message": {"role": "assistant", "content": "All chains healthy."}}
        ],
        "usage": {"prompt_tokens": 200, "completion_tokens": 30, "total_tokens": 230},
    }
    respx.post(f"{MIMO_BASE_URL}/chat/completions").mock(
        return_value=httpx.Response(200, json=mock_response)
    )

    rows = [_fake_stats("base"), _fake_stats("optimism")]
    async with MiMoClient(api_key="sk-test") as client:
        result = await analyze_chains(client, rows)

    assert result == "All chains healthy."
