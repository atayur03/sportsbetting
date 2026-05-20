"""Execution-layer public interface.

Execution discovers venue markets, converts them into normalized strategy
lines, consumes strategy recommendations, and routes approved orders through
the logged Kalshi trading API.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "DailyExecutionResult",
    "DailyExecutionRunner",
    "DateRangeExecutionResult",
    "DateRangeExecutionRunner",
    "ExecutionConfig",
    "ExecutionResult",
    "ExecutionTarget",
    "DEFAULT_SIMULATED_TRADE_LOG_PATH",
    "KalshiExecutionEngine",
    "KalshiExecutionEngineInterface",
    "KalshiMarketLineProvider",
    "KalshiMarketLineProviderInterface",
    "ScheduledExecutionRunner",
    "WeeklyExecutionRunner",
    "daily_utc_window",
]


def __getattr__(name: str) -> Any:
    if name in {
        "ExecutionConfig",
        "ExecutionResult",
        "ExecutionTarget",
    }:
        from execution.core import spec

        return getattr(spec, name)
    if name in {
        "DailyExecutionResult",
        "DailyExecutionRunner",
        "DateRangeExecutionResult",
        "DateRangeExecutionRunner",
        "ScheduledExecutionRunner",
        "WeeklyExecutionRunner",
        "daily_utc_window",
    }:
        import execution.schedules as schedules

        return getattr(schedules, name)
    if name in {
        "DEFAULT_SIMULATED_TRADE_LOG_PATH",
        "KalshiExecutionEngine",
        "KalshiExecutionEngineInterface",
        "KalshiMarketLineProvider",
        "KalshiMarketLineProviderInterface",
    }:
        import execution.kalshi as kalshi_execution

        return getattr(kalshi_execution, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
