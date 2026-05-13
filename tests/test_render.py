"""Smoke tests for the rendering layer.

We don't snapshot the full Rich output (terminal-dependent). We just verify
the table builds, has the right column count, and serialization is JSON-safe.
"""

from __future__ import annotations

import json

from chainpulse.chains import get_chain
from chainpulse.fetch import ChainStats
from chainpulse.render import build_table, stats_to_dict


def _row(error: str | None = None) -> ChainStats:
    return ChainStats(
        chain=get_chain("base"),
        gas_wei=1_500_000_000,
        block_number=12345678,
        block_timestamp=1_700_000_000,
        block_tx_count=42,
        latency_ms=123.4,
        error=error,
    )


def test_build_table_has_eight_columns() -> None:
    table = build_table([_row(), _row(error="boom")])
    assert len(table.columns) == 8


def test_build_table_handles_empty_rows() -> None:
    table = build_table([])
    assert len(table.columns) == 8
    assert table.row_count == 0


def test_stats_to_dict_is_json_serializable() -> None:
    payload = stats_to_dict(_row())
    encoded = json.dumps(payload, default=str)
    decoded = json.loads(encoded)
    assert decoded["chain"] == "Base"
    assert decoded["chain_id"] == 8453
    assert decoded["gas_gwei"] == 1.5
    assert decoded["block_tx_count"] == 42


def test_stats_to_dict_preserves_error() -> None:
    payload = stats_to_dict(_row(error="connection refused"))
    assert payload["error"] == "connection refused"
