"""Render `ChainStats` rows into a Rich table."""

from __future__ import annotations

from rich.table import Table
from rich.text import Text

from .fetch import NATIVE_TRANSFER_GAS, ChainStats


def _gas_color(gwei: float | None) -> str:
    """Bucket gas price → color. Tuned for L2-typical sub-gwei to L1 30+ gwei."""
    if gwei is None:
        return "dim"
    if gwei < 0.1:
        return "bright_green"
    if gwei < 1:
        return "green"
    if gwei < 5:
        return "yellow"
    if gwei < 20:
        return "orange1"
    return "red"


def _format_gas(gwei: float | None) -> Text:
    if gwei is None:
        return Text("-", style="dim")
    if gwei < 0.001:
        return Text(f"{gwei * 1000:.3f} mgwei", style=_gas_color(gwei))
    if gwei < 1:
        return Text(f"{gwei:.4f} gwei", style=_gas_color(gwei))
    return Text(f"{gwei:.2f} gwei", style=_gas_color(gwei))


def _format_usd(value: float | None) -> Text:
    if value is None:
        return Text("-", style="dim")
    if value < 0.0001:
        return Text(f"${value * 100:.4f}¢", style="bright_green")
    if value < 0.01:
        return Text(f"${value:.5f}", style="green")
    if value < 0.10:
        return Text(f"${value:.4f}", style="yellow")
    if value < 1.0:
        return Text(f"${value:.3f}", style="orange1")
    return Text(f"${value:.2f}", style="red")


def _format_age(seconds: float | None) -> Text:
    if seconds is None:
        return Text("-", style="dim")
    if seconds < 5:
        return Text(f"{seconds:.1f}s", style="bright_green")
    if seconds < 30:
        return Text(f"{seconds:.0f}s", style="green")
    if seconds < 120:
        return Text(f"{seconds:.0f}s", style="yellow")
    minutes = seconds / 60
    return Text(f"{minutes:.1f}m", style="red")


def _format_latency(ms: float | None) -> Text:
    if ms is None:
        return Text("-", style="dim")
    if ms < 200:
        return Text(f"{ms:.0f}ms", style="green")
    if ms < 800:
        return Text(f"{ms:.0f}ms", style="yellow")
    return Text(f"{ms:.0f}ms", style="red")


def build_table(rows: list[ChainStats], *, gas_units: int = NATIVE_TRANSFER_GAS) -> Table:
    table = Table(
        title="chainpulse — multi-chain gas & activity",
        title_style="bold cyan",
        header_style="bold",
        show_lines=False,
        expand=False,
    )
    table.add_column("Chain", style="bold")
    table.add_column("Gas", justify="right")
    table.add_column(f"Send ({gas_units // 1000}k gas)", justify="right")
    table.add_column("Block", justify="right")
    table.add_column("Age", justify="right")
    table.add_column("Txs", justify="right")
    table.add_column("RPC", justify="right")
    table.add_column("Status", justify="left")

    for s in rows:
        status = (
            Text(f"err: {s.error[:40]}", style="red")
            if s.error
            else Text("ok", style="green")
        )
        table.add_row(
            f"{s.chain.name}",
            _format_gas(s.gas_gwei),
            _format_usd(s.transfer_cost_usd(gas_units)),
            f"{s.block_number:,}" if s.block_number is not None else "-",
            _format_age(s.block_age_s),
            f"{s.block_tx_count}" if s.block_tx_count is not None else "-",
            _format_latency(s.latency_ms),
            status,
        )

    return table


def stats_to_dict(stats: ChainStats, *, gas_units: int = NATIVE_TRANSFER_GAS) -> dict:
    """Serialize a row to a dict for JSON output."""
    return {
        "chain": stats.chain.name,
        "chain_id": stats.chain.chain_id,
        "native": stats.chain.native,
        "gas_wei": stats.gas_wei,
        "gas_gwei": stats.gas_gwei,
        "transfer_cost_usd": stats.transfer_cost_usd(gas_units),
        "block_number": stats.block_number,
        "block_timestamp": stats.block_timestamp,
        "block_age_s": stats.block_age_s,
        "block_tx_count": stats.block_tx_count,
        "latency_ms": stats.latency_ms,
        "error": stats.error,
    }
