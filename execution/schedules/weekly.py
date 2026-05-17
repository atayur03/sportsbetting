"""Weekly execution orchestration."""

from __future__ import annotations

import datetime as dt

from execution.interface import MarketLineProvider, VenueExecutionEngine
from execution.schedules.daily import DEFAULT_EXECUTION_TIMEZONE, parse_run_date
from execution.schedules.date_range import DateRangeExecutionResult, DateRangeExecutionRunner
from strategy import Strategy


class WeeklyExecutionRunner:
    """Run a strategy once per day for seven calendar days."""

    def __init__(
        self,
        *,
        provider: MarketLineProvider,
        engine: VenueExecutionEngine,
        timezone: str = DEFAULT_EXECUTION_TIMEZONE,
    ):
        self.date_range_runner = DateRangeExecutionRunner(provider=provider, engine=engine, timezone=timezone)

    def run_strategy(
        self,
        strategy: Strategy,
        *,
        run_date: dt.date | str,
        market_types: set[str] | None = None,
    ) -> DateRangeExecutionResult:
        """Run `strategy` for `run_date` and the next six dates."""
        start_date = parse_run_date(run_date)
        end_date = start_date + dt.timedelta(days=7)
        return self.date_range_runner.run_strategy(
            strategy,
            start_date=start_date,
            end_date=end_date,
            market_types=market_types,
        )
