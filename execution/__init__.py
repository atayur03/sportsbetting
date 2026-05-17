"""Execution-layer public interface.

Execution discovers venue markets, converts them into normalized strategy
lines, consumes strategy recommendations, and routes approved orders through
the logged Kalshi trading API.
"""

from execution.kalshi import (
    KalshiExecutionEngine,
    KalshiExecutionEngineInterface,
    KalshiMarketLineProvider,
    KalshiMarketLineProviderInterface,
)
from execution.schedules import (
    DailyExecutionResult,
    DailyExecutionRunner,
    DateRangeExecutionResult,
    DateRangeExecutionRunner,
    ScheduledExecutionRunner,
    WeeklyExecutionRunner,
    daily_utc_window,
)
from execution.spec import ExecutionConfig, ExecutionResult, ExecutionTarget

__all__ = [
    "DailyExecutionResult",
    "DailyExecutionRunner",
    "DateRangeExecutionResult",
    "DateRangeExecutionRunner",
    "ExecutionConfig",
    "ExecutionResult",
    "ExecutionTarget",
    "KalshiExecutionEngine",
    "KalshiExecutionEngineInterface",
    "KalshiMarketLineProvider",
    "KalshiMarketLineProviderInterface",
    "ScheduledExecutionRunner",
    "WeeklyExecutionRunner",
    "daily_utc_window",
]
