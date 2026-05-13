"""chainpulse CLI."""

from __future__ import annotations

import asyncio
import json
import sys

import typer
from rich.console import Console
from rich.live import Live

from . import __version__
from .chains import CHAINS, DEFAULT_CHAINS, get_chain
from .fetch import ERC20_TRANSFER_GAS, NATIVE_TRANSFER_GAS, fetch_all
from .render import build_table, stats_to_dict

app = typer.Typer(
    add_completion=False,
    help="Multi-chain gas & activity dashboard for EVM L2s.",
    no_args_is_help=False,
)
console = Console()
err_console = Console(stderr=True)


def _resolve_chains(slugs: list[str] | None, all_chains: bool):
    if all_chains:
        return [CHAINS[s] for s in CHAINS]
    if not slugs:
        return [CHAINS[s] for s in DEFAULT_CHAINS]
    out = []
    for s in slugs:
        try:
            out.append(get_chain(s))
        except KeyError as e:
            err_console.print(f"[red]{e}[/red]")
            raise typer.Exit(2) from e
    return out


def _override_prices(eth: float | None, matic: float | None, mnt: float | None) -> None:
    """Mutate USD prices on chain entries. Chains are frozen dataclasses, so we
    rewrite the field via object.__setattr__."""
    overrides = (("ETH", eth), ("POL", matic), ("MNT", mnt))
    for symbol, price in overrides:
        if price is None:
            continue
        for chain in CHAINS.values():
            if chain.native == symbol:
                object.__setattr__(chain, "usd_price_native", price)


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"chainpulse {__version__}")
        raise typer.Exit()


# Module-level singletons for default Option objects (ruff B008).
_OPT_CHAINS = typer.Option(
    None, "--chain", "-c", help="Chain slug. Repeatable. Default: 12 popular L2s."
)
_OPT_ALL = typer.Option(False, "--all", help="Use every chain in the registry.")
_OPT_WATCH = typer.Option(0.0, "--watch", "-w", help="Refresh every N seconds (0 = once).")
_OPT_JSON = typer.Option(False, "--json", help="Emit JSON to stdout (one shot only).")
_OPT_ERC20 = typer.Option(False, "--erc20", help="Estimate ERC20 transfer cost (65k gas).")
_OPT_TIMEOUT = typer.Option(6.0, "--timeout", help="Per-chain RPC timeout (seconds).")
_OPT_ETH = typer.Option(None, "--eth-price", help="Override ETH USD price.")
_OPT_MATIC = typer.Option(None, "--matic-price", help="Override POL USD price.")
_OPT_MNT = typer.Option(None, "--mnt-price", help="Override MNT USD price.")
_OPT_LIST = typer.Option(False, "--list", help="List available chain slugs and exit.")
_OPT_VERSION = typer.Option(
    None, "--version", "-V", callback=_version_callback, is_eager=True, help="Show version and exit."
)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    chains: list[str] | None = _OPT_CHAINS,
    all_chains: bool = _OPT_ALL,
    watch: float = _OPT_WATCH,
    json_out: bool = _OPT_JSON,
    erc20: bool = _OPT_ERC20,
    timeout: float = _OPT_TIMEOUT,
    eth_price: float | None = _OPT_ETH,
    matic_price: float | None = _OPT_MATIC,
    mnt_price: float | None = _OPT_MNT,
    list_chains: bool = _OPT_LIST,
    version: bool | None = _OPT_VERSION,
) -> None:
    """Show gas, latest block, and transfer cost for many EVM chains side by side."""
    if list_chains:
        for slug, chain in sorted(CHAINS.items()):
            console.print(f"  [cyan]{slug:18s}[/cyan] {chain.name}  (chainId {chain.chain_id})")
        raise typer.Exit()

    _override_prices(eth_price, matic_price, mnt_price)
    selected = _resolve_chains(chains, all_chains)
    gas_units = ERC20_TRANSFER_GAS if erc20 else NATIVE_TRANSFER_GAS

    try:
        asyncio.run(_run(selected, watch, json_out, gas_units, timeout))
    except KeyboardInterrupt:
        err_console.print("[dim]stopped.[/dim]")


async def _run(selected, watch: float, json_out: bool, gas_units: int, timeout: float) -> None:
    if json_out:
        rows = await fetch_all(selected, timeout=timeout)
        payload = [stats_to_dict(r, gas_units=gas_units) for r in rows]
        sys.stdout.write(json.dumps(payload, indent=2, default=str) + "\n")
        return

    if watch <= 0:
        rows = await fetch_all(selected, timeout=timeout)
        console.print(build_table(rows, gas_units=gas_units))
        return

    with Live(
        build_table([], gas_units=gas_units),
        console=console,
        refresh_per_second=4,
        screen=False,
    ) as live:
        while True:
            rows = await fetch_all(selected, timeout=timeout)
            live.update(build_table(rows, gas_units=gas_units))
            try:
                await asyncio.sleep(watch)
            except asyncio.CancelledError:
                break


if __name__ == "__main__":
    app()
