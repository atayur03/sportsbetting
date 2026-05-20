"""Public API for this repo's Kalshi integration."""

from __future__ import annotations

from typing import Any


__all__ = [
    "KalshiConfig",
    "KalshiMarkets",
    "KalshiTrading",
    "KalshiTradingClient",
]


def __getattr__(name: str) -> Any:
    if name in __all__:
        from kalshi import interface

        return getattr(interface, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
