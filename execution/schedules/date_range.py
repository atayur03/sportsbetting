"""Date-range execution orchestration."""

from __future__ import annotations

import datetime as dt
from dataclasses import asdict, dataclass, field
from typing import Any

from execution.interface import MarketLineProvider, VenueExecutionEngine
from execution.schedules.daily import DEFAULT_EXECUTION_TIMEZONE, DailyExecutionResult, DailyExecutionRunner, parse_run_date
from strategy import Strategy


def iter_dates(start_date: dt.date | str, end_date: dt.date | str) -> list[dt.date]:
    """Return dates in `[start_date, end_date)`.

    `end_date` is exclusive so weekly execution can run exactly seven days with
    `end_date = start_date + 7 days`.
    """
    start = parse_run_date(start_date)
    end = parse_run_date(end_date)
    if end <= start:
        raise ValueError("end_date must be after start_date")
    return [start + dt.timedelta(days=offset) for offset in range((end - start).days)]


@dataclass(frozen=True)
class DateRangeExecutionResult:
    """Structured result for a strategy executed across multiple daily windows."""

    start_date: str
    end_date: str
    timezone: str
    strategy_name: str
    market_types: set[str] | None
    daily_results: list[dict[str, Any]]
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        row = asdict(self)
        if self.market_types is not None:
            row["market_types"] = sorted(self.market_types)
        return row


class DateRangeExecutionRunner:
    """Run daily execution for each date in a start/end date range."""

    def __init__(
        self,
        *,
        provider: MarketLineProvider,
        engine: VenueExecutionEngine,
        timezone: str = DEFAULT_EXECUTION_TIMEZONE,
    ):
        self.daily_runner = DailyExecutionRunner(provider=provider, engine=engine, timezone=timezone)
        self.timezone = timezone

    def run_strategy(
        self,
        strategy: Strategy,
        *,
        start_date: dt.date | str,
        end_date: dt.date | str,
        market_types: set[str] | None = None,
    ) -> DateRangeExecutionResult:
        """Run `strategy` once per day for `[start_date, end_date)`."""
        daily_results: list[DailyExecutionResult] = []
        for run_date in iter_dates(start_date, end_date):
            daily_results.append(
                self.daily_runner.run_strategy(
                    strategy,
                    run_date=run_date,
                    market_types=market_types,
                )
            )

        result_rows = [result.to_dict() for result in daily_results]
        return DateRangeExecutionResult(
            start_date=parse_run_date(start_date).isoformat(),
            end_date=parse_run_date(end_date).isoformat(),
            timezone=self.timezone,
            strategy_name=strategy.name,
            market_types=market_types,
            daily_results=result_rows,
            metadata={
                "days": len(daily_results),
                "lines_seen": sum(result.lines_seen for result in daily_results),
                "actions": sum(result.metadata.get("actions", 0) for result in daily_results),
                "accepted": sum(result.metadata.get("accepted", 0) for result in daily_results),
                "skipped": sum(result.metadata.get("skipped", 0) for result in daily_results),
            },
        )
