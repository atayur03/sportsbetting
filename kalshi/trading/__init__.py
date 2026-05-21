"""Trading public exports."""

from __future__ import annotations

from typing import Any

__all__ = [
    "DEFAULT_FILL_HISTORY_PATH",
    "DEFAULT_TRADE_LOG_PATH",
    "FILL_COLUMNS",
    "TRADE_LOG_COLUMNS",
    "KalshiConfig",
    "KalshiTradingClient",
    "build_order_payload",
]


def __getattr__(name: str) -> Any:
    if name in __all__:
        from kalshi.trading import client

        return getattr(client, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
