"""Chain registry. Public RPC endpoints, no API key needed.

Each chain entry pins:
- name: human label
- chain_id: EIP-155 chain id (used to verify the RPC matches)
- rpc: comma-separated fallback list (first one wins, fallback on failure)
- explorer: block explorer base URL
- native: native token symbol (for gas display)
- gas_unit: 'gwei' (default) or 'mwei' for chains with sub-gwei gas (Arbitrum, etc.)
- usd_price_native: USD price of the native token. Hardcoded as a coarse default;
  override at runtime via --eth-price / --matic-price flags. Not a price oracle.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Chain:
    name: str
    chain_id: int
    rpc: tuple[str, ...]
    explorer: str
    native: str = "ETH"
    gas_unit: str = "gwei"
    # rough hardcoded USD reference. user can override via CLI flag.
    usd_price_native: float = 2500.0


# Public RPCs. Sourced from chainlist.org / official docs. No API key required.
# Multiple endpoints per chain so we can fall back if one is down or rate-limits us.
CHAINS: dict[str, Chain] = {
    "ethereum": Chain(
        name="Ethereum",
        chain_id=1,
        rpc=(
            "https://eth.llamarpc.com",
            "https://ethereum-rpc.publicnode.com",
            "https://rpc.ankr.com/eth",
        ),
        explorer="https://etherscan.io",
    ),
    "base": Chain(
        name="Base",
        chain_id=8453,
        rpc=(
            "https://mainnet.base.org",
            "https://base.llamarpc.com",
            "https://base-rpc.publicnode.com",
        ),
        explorer="https://basescan.org",
    ),
    "arbitrum": Chain(
        name="Arbitrum One",
        chain_id=42161,
        rpc=(
            "https://arb1.arbitrum.io/rpc",
            "https://arbitrum.llamarpc.com",
            "https://arbitrum-one-rpc.publicnode.com",
        ),
        explorer="https://arbiscan.io",
    ),
    "optimism": Chain(
        name="Optimism",
        chain_id=10,
        rpc=(
            "https://mainnet.optimism.io",
            "https://optimism.llamarpc.com",
            "https://optimism-rpc.publicnode.com",
        ),
        explorer="https://optimistic.etherscan.io",
    ),
    "scroll": Chain(
        name="Scroll",
        chain_id=534352,
        rpc=(
            "https://rpc.scroll.io",
            "https://scroll.drpc.org",
        ),
        explorer="https://scrollscan.com",
    ),
    "linea": Chain(
        name="Linea",
        chain_id=59144,
        rpc=(
            "https://rpc.linea.build",
            "https://linea-rpc.publicnode.com",
        ),
        explorer="https://lineascan.build",
    ),
    "zksync": Chain(
        name="zkSync Era",
        chain_id=324,
        rpc=(
            "https://mainnet.era.zksync.io",
            "https://zksync.drpc.org",
        ),
        explorer="https://explorer.zksync.io",
    ),
    "polygon-zkevm": Chain(
        name="Polygon zkEVM",
        chain_id=1101,
        rpc=(
            "https://zkevm-rpc.com",
            "https://polygon-zkevm.drpc.org",
        ),
        explorer="https://zkevm.polygonscan.com",
    ),
    "mantle": Chain(
        name="Mantle",
        chain_id=5000,
        rpc=(
            "https://rpc.mantle.xyz",
            "https://mantle-rpc.publicnode.com",
        ),
        explorer="https://explorer.mantle.xyz",
        native="MNT",
        usd_price_native=0.7,
    ),
    "polygon": Chain(
        name="Polygon PoS",
        chain_id=137,
        rpc=(
            "https://polygon-rpc.com",
            "https://polygon.llamarpc.com",
            "https://polygon-bor-rpc.publicnode.com",
        ),
        explorer="https://polygonscan.com",
        native="POL",
        usd_price_native=0.5,
    ),
    "ink": Chain(
        name="Ink",
        chain_id=57073,
        rpc=(
            "https://rpc-gel.inkonchain.com",
            "https://rpc-qnd.inkonchain.com",
        ),
        explorer="https://explorer.inkonchain.com",
    ),
    "blast": Chain(
        name="Blast",
        chain_id=81457,
        rpc=(
            "https://rpc.blast.io",
            "https://blast-rpc.publicnode.com",
        ),
        explorer="https://blastscan.io",
    ),
}


DEFAULT_CHAINS: tuple[str, ...] = (
    "ethereum",
    "base",
    "arbitrum",
    "optimism",
    "scroll",
    "linea",
    "zksync",
    "polygon-zkevm",
    "mantle",
    "polygon",
    "ink",
    "blast",
)


def get_chain(slug: str) -> Chain:
    """Look up a chain by slug. Raises KeyError with a helpful list on miss."""
    slug = slug.lower().strip()
    if slug not in CHAINS:
        available = ", ".join(sorted(CHAINS))
        raise KeyError(f"Unknown chain '{slug}'. Available: {available}")
    return CHAINS[slug]
