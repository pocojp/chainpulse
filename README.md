# chainpulse

Multi-chain gas, block, and activity dashboard for EVM L2s. One CLI, public RPCs, no API key.

```
chainpulse
```

Polls 12 chains in parallel and prints gas price, latest block, block age, tx count per block, native-transfer cost in USD, and RPC latency in a colored table.

[![CI](https://github.com/rhardian/chainpulse/actions/workflows/ci.yml/badge.svg)](https://github.com/rhardian/chainpulse/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

## What it does

- Side-by-side gas price comparison across L1 + 11 L2s (Base, Arbitrum, Optimism, Scroll, Linea, zkSync, Polygon zkEVM, Mantle, Polygon PoS, Ink, Blast, Ethereum)
- Estimated USD cost of a native transfer at current gas
- Latest block number + how stale it is (catches stuck/forked RPCs)
- Tx count of the latest block (rough activity signal)
- RPC latency (catches slow endpoints)
- `--watch` mode that refreshes in place
- `--json` for piping into jq, dashboards, or shell scripts
- Public RPCs only. **Zero API keys.** Multiple endpoints per chain with automatic fallback so one flaky provider never blanks a row.

## Install

```bash
pip install chainpulse
```

Or from source:

```bash
git clone https://github.com/rhardian/chainpulse
cd chainpulse
pip install -e .
```

Requires Python 3.10+.

## Usage

```bash
# Default: 12 popular chains, one shot
chainpulse

# Watch mode, refresh every 5 seconds
chainpulse --watch 5

# Specific chains only
chainpulse -c base -c arbitrum -c optimism

# Every chain in the registry
chainpulse --all

# ERC-20 transfer cost (65k gas) instead of native send (21k gas)
chainpulse --erc20

# Override the hardcoded ETH price for cost estimates
chainpulse --eth-price 3200

# JSON for piping
chainpulse --json | jq '.[] | select(.gas_gwei < 0.5) | .chain'

# List every available chain slug
chainpulse --list
```

## Example output

```
                chainpulse — multi-chain gas & activity
┏━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━┳━━━━━┳━━━━━━━┳━━━━━━━━┓
┃ Chain          ┃           Gas ┃ Send (21k) ┃    Block ┃  Age ┃ Txs ┃   RPC ┃ Status ┃
┡━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━╇━━━━━╇━━━━━━━╇━━━━━━━━┩
│ Ethereum       │      4.21 gwei│   $0.221   │ 19,501,233│   8s │ 142 │ 187ms │ ok     │
│ Base           │     0.0042 gwei│ $0.0002   │ 12,888,012│   2s │  88 │  92ms │ ok     │
│ Arbitrum One   │     0.0100 gwei│ $0.0005   │213,400,991│   1s │  55 │ 134ms │ ok     │
│ Optimism       │     0.0011 gwei│ $0.0001   │117,222,508│   2s │  31 │ 110ms │ ok     │
│ ...                                                                                  │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

Cells are color-coded: green = cheap/fast, yellow = warming up, red = expensive/slow/down.

## Why

When farming L2 airdrops, sniping a mint, or just deciding which network to bridge through, you need a quick read on:

1. Which chain is cheapest right now?
2. Is the chain alive (block age, tx count)?
3. Is my RPC fast?

Block explorers answer #1 and #2 one chain at a time. `chainpulse` answers all three for a dozen chains in one screen.

## JSON schema

`chainpulse --json` emits a list, one entry per chain:

```json
[
  {
    "chain": "Base",
    "chain_id": 8453,
    "native": "ETH",
    "gas_wei": 4250000,
    "gas_gwei": 0.00425,
    "transfer_cost_usd": 0.000223125,
    "block_number": 12888012,
    "block_timestamp": 1715603128,
    "block_age_s": 2.4,
    "block_tx_count": 88,
    "latency_ms": 92.1,
    "error": null
  }
]
```

## Adding a chain

`src/chainpulse/chains.py` is a flat dict. PRs welcome.

```python
"my-chain": Chain(
    name="My Chain",
    chain_id=12345,
    rpc=("https://rpc1.my-chain.io", "https://rpc2.my-chain.io"),
    explorer="https://explorer.my-chain.io",
    native="ETH",  # or other symbol
),
```

The CLI auto-picks it up. Endpoints must be public, HTTPS, and accept standard JSON-RPC.

## Development

```bash
git clone https://github.com/rhardian/chainpulse
cd chainpulse
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
ruff check .
```

## Limitations

- USD cost is computed from a hardcoded native-token price (overridable via `--eth-price`, `--matic-price`, `--mnt-price`). It's a back-of-envelope estimate, not a real-time oracle.
- `eth_gasPrice` reports the legacy gas price. Chains that fully migrated to EIP-1559 may report a synthetic value; treat the number as "what a wallet would suggest right now" rather than a precise floor.
- Public RPCs rate-limit. Watch mode at sub-second intervals will get you 429s. 5–30 seconds is the sweet spot.

## License

MIT. See [LICENSE](LICENSE).
