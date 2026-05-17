"""Interfaces for execution-side adapters."""

from __future__ import annotations

from typing import Protocol

from execution.spec import ExecutionResult, ExecutionTarget
from strategy import MarketLine, StrategyRun


class MarketLineProvider(Protocol):
    """Find venue markets and expose normalized strategy lines.

    Implementations own the private mapping from `MarketLine.line_id` to
    venue-specific identifiers such as Kalshi tickers.
    """

    def list_lines(
        self,
        *,
        market_types: set[str] | None = None,
        start_time_utc: str | None = None,
        end_time_utc: str | None = None,
    ) -> list[MarketLine]:
        """Return normalized market lines for strategies."""

    def execution_targets(self) -> list[ExecutionTarget]:
        """Return venue targets for the most recently listed lines."""


class VenueExecutionEngine(Protocol):
    """Execute a strategy run against one venue."""

    def execute_run(self, run: StrategyRun) -> list[ExecutionResult]:
        """Return one execution result per strategy action."""
