"""Daily execution orchestration."""

from __future__ import annotations

import datetime as dt
from dataclasses import asdict, dataclass, field
from typing import Any
from zoneinfo import ZoneInfo

from execution.interface import MarketLineProvider, VenueExecutionEngine
from execution.spec import ExecutionResult
from strategy import SportsLeague, Strategy, normalize_supported_sports_leagues


DEFAULT_EXECUTION_TIMEZONE = "America/New_York"


def parse_run_date(run_date: dt.date | str) -> dt.date:
    """Return a date from a date object or YYYY-MM-DD string."""
    if isinstance(run_date, dt.date):
        return run_date
    return dt.date.fromisoformat(run_date)


def daily_utc_window(
    run_date: dt.date | str,
    *,
    timezone: str = DEFAULT_EXECUTION_TIMEZONE,
) -> tuple[str, str]:
    """Return `[start, end)` UTC ISO timestamps for one local calendar day."""
    parsed_date = parse_run_date(run_date)
    tz = ZoneInfo(timezone)
    start_local = dt.datetime.combine(parsed_date, dt.time.min, tzinfo=tz)
    end_local = start_local + dt.timedelta(days=1)
    start_utc = start_local.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")
    end_utc = end_local.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")
    return start_utc, end_utc


@dataclass(frozen=True)
class DailyExecutionResult:
    """Structured result for one strategy's daily execution."""

    run_date: str
    timezone: str
    start_time_utc: str
    end_time_utc: str
    strategy_name: str
    sports_league: SportsLeague
    market_types: set[str] | None
    lines_seen: int
    targets_seen: int
    strategy_run: dict[str, Any]
    execution_results: list[dict[str, Any]]
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        row = asdict(self)
        row["sports_league"] = self.sports_league.value
        if self.market_types is not None:
            row["market_types"] = sorted(self.market_types)
        return row


class DailyExecutionRunner:
    """Find one day's lines, run one strategy, and execute its actions."""

    def __init__(
        self,
        *,
        provider: MarketLineProvider,
        engine: VenueExecutionEngine,
        timezone: str = DEFAULT_EXECUTION_TIMEZONE,
    ):
        self.provider = provider
        self.engine = engine
        self.timezone = timezone

    def run_strategy(
        self,
        strategy: Strategy,
        *,
        run_date: dt.date | str,
        market_types: set[str] | None = None,
    ) -> DailyExecutionResult:
        """Execute `strategy` for one local calendar day.

        The provider receives a UTC `[start, end)` window. The strategy receives
        only normalized lines for its declared sports league.
        """
        start_time_utc, end_time_utc = daily_utc_window(run_date, timezone=self.timezone)
        lines = self.provider.list_lines(
            market_types=market_types,
            start_time_utc=start_time_utc,
            end_time_utc=end_time_utc,
        )
        targets = self.provider.execution_targets()
        if hasattr(self.engine, "add_targets"):
            self.engine.add_targets(targets)

        supported_sports_leagues = normalize_supported_sports_leagues(strategy)
        strategy_lines = [line for line in lines if line.sports_league in supported_sports_leagues]
        run = strategy.evaluate(strategy_lines)
        results = self.engine.execute_run(run)

        return DailyExecutionResult(
            run_date=parse_run_date(run_date).isoformat(),
            timezone=self.timezone,
            start_time_utc=start_time_utc,
            end_time_utc=end_time_utc,
            strategy_name=strategy.name,
            sports_league=run.sports_league,
            market_types=market_types,
            lines_seen=len(strategy_lines),
            targets_seen=len(targets),
            strategy_run=run.to_dict(),
            execution_results=[result.to_dict() for result in results],
            metadata={
                "actions": len(run.actions),
                "accepted": sum(1 for result in results if result.accepted),
                "skipped": sum(1 for result in results if result.skipped),
            },
        )
