"""Tests for the chain registry."""

from __future__ import annotations

import pytest

from chainpulse.chains import CHAINS, DEFAULT_CHAINS, get_chain


def test_default_chains_are_in_registry() -> None:
    for slug in DEFAULT_CHAINS:
        assert slug in CHAINS, f"{slug} not registered"


def test_every_chain_has_endpoints() -> None:
    for slug, chain in CHAINS.items():
        assert chain.rpc, f"{slug} has no RPC endpoints"
        for url in chain.rpc:
            assert url.startswith("https://"), f"{slug}: {url} is not https"


def test_chain_ids_are_unique_and_positive() -> None:
    seen: dict[int, str] = {}
    for slug, chain in CHAINS.items():
        assert chain.chain_id > 0, f"{slug}: chain_id must be positive"
        assert chain.chain_id not in seen, (
            f"chain_id collision: {slug} and {seen[chain.chain_id]} both = {chain.chain_id}"
        )
        seen[chain.chain_id] = slug


def test_get_chain_lookup() -> None:
    chain = get_chain("base")
    assert chain.chain_id == 8453
    assert chain.name == "Base"


def test_get_chain_is_case_insensitive() -> None:
    assert get_chain("BASE").chain_id == 8453
    assert get_chain("  Arbitrum  ").chain_id == 42161


def test_get_chain_unknown_raises_with_help() -> None:
    with pytest.raises(KeyError) as exc_info:
        get_chain("not-a-chain")
    msg = str(exc_info.value)
    assert "not-a-chain" in msg
    assert "Available" in msg
