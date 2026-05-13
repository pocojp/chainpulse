"""Per-chain stat fetcher: gas price, block number, block timestamp, tx count.

Returns a `ChainStats` dataclass per chain. Errors don't blow up the dashboard
— they're captured into the row so the user sees `-` for that field.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

from .chains import Chain
from .rpc import JsonRpcClient, RpcError, hex_to_int

# A standard ERC-20 transfer costs ~21000 gas (native send) or ~65000 gas
# (token). We default to the native send number as the cheap reference.
NATIVE_TRANSFER_GAS = 21_000
ERC20_TRANSFER_GAS = 65_000


@dataclass
class ChainStats:
    chain: Chain
    gas_wei: int | None = None  # gas price in wei
    block_number: int | None = None
    block_timestamp: int | None = None
    block_tx_count: int | None = None
    latency_ms: float | None = None
    error: str | None = None

    @property
    def gas_gwei(self) -> float | None:
        if self.gas_wei is None:
            return None
        return self.gas_wei / 1e9

    def transfer_cost_usd(self, gas_units: int = NATIVE_TRANSFER_GAS) -> float | None:
        """Estimate native-token transfer cost in USD at current gas price."""
        if self.gas_wei is None:
            return None
        cost_native = (self.gas_wei * gas_units) / 1e18
        return cost_native * self.chain.usd_price_native

    @property
    def block_age_s(self) -> float | None:
        if self.block_timestamp is None:
            return None
        return max(0.0, time.time() - self.block_timestamp)


async def fetch_chain_stats(
    chain: Chain,
    *,
    timeout: float = 6.0,
    include_block_details: bool = True,
) -> ChainStats:
    """Fetch gas price + latest block info for a single chain. Never raises."""
    stats = ChainStats(chain=chain)
    started = time.perf_counter()

    try:
        async with JsonRpcClient(chain.rpc, timeout=timeout) as client:
            calls: list[tuple[str, list | None]] = [
                ("eth_gasPrice", []),
                ("eth_blockNumber", []),
            ]
            if include_block_details:
                # passing 'latest' + false → header only, no full tx list
                calls.append(("eth_getBlockByNumber", ["latest", False]))

            results = await client.batch(calls)

            gas_res, block_num_res, *rest = results
            stats.gas_wei = hex_to_int(gas_res) if not isinstance(gas_res, Exception) else None
            stats.block_number = (
                hex_to_int(block_num_res) if not isinstance(block_num_res, Exception) else None
            )

            if include_block_details and rest:
                block = rest[0]
                if isinstance(block, dict):
                    stats.block_timestamp = hex_to_int(block.get("timestamp"))
                    txs = block.get("transactions") or []
                    stats.block_tx_count = len(txs) if isinstance(txs, list) else None

            # If everything failed, report the first error
            errors = [r for r in results if isinstance(r, Exception)]
            if errors and stats.gas_wei is None and stats.block_number is None:
                stats.error = str(errors[0])

    except RpcError as e:
        stats.error = str(e)
    except Exception as e:  # surface unexpected errors as a string in the row instead of crashing
        stats.error = f"{type(e).__name__}: {e}"
    finally:
        stats.latency_ms = (time.perf_counter() - started) * 1000

    return stats


async def fetch_all(
    chains: list[Chain],
    *,
    timeout: float = 6.0,
    include_block_details: bool = True,
) -> list[ChainStats]:
    """Fetch stats for many chains in parallel."""
    coros = [
        fetch_chain_stats(c, timeout=timeout, include_block_details=include_block_details)
        for c in chains
    ]
    return await asyncio.gather(*coros)
