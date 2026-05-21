"""Analyze multi-chain stats using Xiaomi MiMo models.

Takes ChainStats rows (from fetch.py), formats a structured prompt,
and sends it to MiMo for anomaly detection, summary, and recommendations.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from .fetch import NATIVE_TRANSFER_GAS, ChainStats

if TYPE_CHECKING:
    from .mimo import MiMoClient

SYSTEM_PROMPT = """\
You are a blockchain analyst specializing in EVM L2 networks. You receive raw
on-chain data (gas prices, block info, RPC latency) for multiple Ethereum L2
chains fetched in real time.

Your job:
1. **Anomaly Detection** — flag any chain with suspicious readings:
   - Gas price spike (>5x median of other L2s)
   - Stale block (age > 60s) or zero tx count
   - High RPC latency (>2000ms) indicating endpoint issues
   - Chain returning errors

2. **Summary** — one paragraph on overall L2 landscape right now:
   - Which chains are cheapest?
   - Which are most active (tx count)?
   - Any notable gas events?

3. **Recommendation** — if a user wants to bridge, swap, or mint right now,
   which chain(s) would you recommend and why?

Be concise. Use bullet points for anomalies. Keep total response under 300 words.
"""

USER_TEMPLATE = """\
Here is the latest multi-chain snapshot (fetched at block time):

{data_json}

Analyze this data. Flag anomalies, summarize the landscape, and recommend
the best chain(s) for a low-cost transaction right now.
"""


def build_analysis_payload(
    rows: list[ChainStats],
    *,
    gas_units: int = NATIVE_TRANSFER_GAS,
) -> str:
    """Format ChainStats rows into a JSON string for the MiMo prompt."""
    data = []
    for s in rows:
            cost = s.transfer_cost_usd(gas_units)
            data.append(
                {
                    "chain": s.chain.name,
                    "chain_id": s.chain.chain_id,
                    "native_token": s.chain.native,
                    "gas_gwei": round(s.gas_gwei, 6) if s.gas_gwei is not None else None,
                    "transfer_cost_usd": round(cost, 8) if cost is not None else None,
                    "block_number": s.block_number,
                    "block_age_s": round(s.block_age_s, 1) if s.block_age_s is not None else None,
                    "block_tx_count": s.block_tx_count,
                    "latency_ms": round(s.latency_ms, 1) if s.latency_ms is not None else None,
                    "error": s.error,
                }
            )
    return json.dumps(data, indent=2)


async def analyze_chains(
    client: MiMoClient,
    rows: list[ChainStats],
    *,
    gas_units: int = NATIVE_TRANSFER_GAS,
) -> str:
    """Send chain stats to MiMo for AI-powered analysis. Returns markdown text."""
    payload = build_analysis_payload(rows, gas_units=gas_units)
    user_msg = USER_TEMPLATE.format(data_json=payload)
    return await client.analyze(SYSTEM_PROMPT, user_msg)
