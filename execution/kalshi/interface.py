"""Interfaces for Kalshi-specific execution implementations."""

from __future__ import annotations

from typing import Protocol

from execution.spec import ExecutionResult, ExecutionTarget
from strategy import MarketLine, StrategyRun, WagerAction


class KalshiMarketLineProviderInterface(Protocol):
    """Normalize Kalshi markets into strategy-facing lines."""

    def list_lines(
        self,
        *,
        market_types: set[str] | None = None,
        start_time_utc: str | None = None,
        end_time_utc: str | None = None,
    ) -> list[MarketLine]:
        """Return normalized strategy lines backed by Kalshi markets."""

    def execution_targets(self) -> list[ExecutionTarget]:
        """Return Kalshi targets for the most recently listed lines."""


class KalshiExecutionEngineInterface(Protocol):
    """Resolve strategy actions to Kalshi tickers and execute them."""

    def add_targets(self, targets: list[ExecutionTarget]) -> None:
        """Add or replace Kalshi execution targets."""

    def resolve_target(self, line_id: str) -> ExecutionTarget:
        """Return the Kalshi target for a strategy-facing line ID."""

    def execute_action(
        self,
        action: WagerAction,
        *,
        run_id: str,
        strategy_name: str,
    ) -> ExecutionResult:
        """Execute one action against Kalshi."""

    def execute_run(self, run: StrategyRun) -> list[ExecutionResult]:
        """Execute one strategy run against Kalshi."""
