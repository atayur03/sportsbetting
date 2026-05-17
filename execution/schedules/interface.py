"""Interfaces for scheduled execution runners."""

from __future__ import annotations

import datetime as dt
from typing import Protocol

from execution.schedules.daily import DailyExecutionResult
from strategy import Strategy


class ScheduledExecutionRunner(Protocol):
    """Run a strategy for a scheduled date window."""

    def run_strategy(
        self,
        strategy: Strategy,
        *,
        run_date: dt.date | str,
        market_types: set[str] | None = None,
    ) -> DailyExecutionResult:
        """Run one strategy for this runner's configured date window."""
