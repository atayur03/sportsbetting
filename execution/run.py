"""CLI for scheduled strategy execution."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
from typing import Any

from kalshi import KalshiConfig
from execution import (
    DEFAULT_SIMULATED_TRADE_LOG_PATH,
    DailyExecutionRunner,
    DateRangeExecutionRunner,
    ExecutionConfig,
    KalshiExecutionEngine,
    KalshiMarketLineProvider,
    WeeklyExecutionRunner,
)
from execution.schedules.daily import parse_run_date
from execution.schedules.date_range import iter_dates
from execution.status import refresh_trade_status_csvs_for_date
from strategy import InvertedStrategy
from strategy.mlb import GameTotalUnderStrategy, UnderdogStrategy


BASE_STRATEGY_NAMES = ["underdog", "game_total_under"]
STRATEGY_NAMES = BASE_STRATEGY_NAMES + [f"inverted_{strategy_name}" for strategy_name in BASE_STRATEGY_NAMES]
ENGINE_NAMES = ["kalshi"]


def parse_market_types(values: list[str] | None) -> set[str] | None:
    if not values:
        return None
    return set(values)


def load_env_file(path: Path = Path(".env")) -> None:
    """Load simple KEY=VALUE pairs into os.environ if they are not already set."""
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def base_strategy_name(name: str) -> str:
    return name.removeprefix("inverted_")


def inverted_strategy_name(name: str) -> str:
    return f"inverted_{base_strategy_name(name)}"


def normalize_strategy_name(name: str, *, inverted: bool = False) -> str:
    if not inverted:
        return name
    if name.startswith("inverted_"):
        return base_strategy_name(name)
    return inverted_strategy_name(name)


def build_base_strategy(name: str, *, stake_cents: int) -> Any:
    if name == "game_total_under":
        return GameTotalUnderStrategy(stake_cents=stake_cents)
    if name == "underdog":
        return UnderdogStrategy(stake_cents=stake_cents)
    raise ValueError(f"unknown strategy: {name}")


def build_strategy(name: str, *, stake_cents: int) -> Any:
    base_strategy = build_base_strategy(base_strategy_name(name), stake_cents=stake_cents)
    if name.startswith("inverted_"):
        return InvertedStrategy(base_strategy)
    return base_strategy


def default_market_types(strategy_name: str, market_types: list[str] | None) -> set[str] | None:
    parsed = parse_market_types(market_types)
    if parsed is not None:
        return parsed
    base_name = base_strategy_name(strategy_name)
    if base_name == "underdog":
        return {"game_moneyline"}
    if base_name == "game_total_under":
        return {"game_total"}
    return None


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--engine", required=True, choices=ENGINE_NAMES)
    parser.add_argument("--strategy", default="underdog", choices=STRATEGY_NAMES)
    parser.add_argument(
        "--inverted",
        action="store_true",
        help="Toggle inversion for the selected strategy. Base names become inverted_*; inverted_* names return to base.",
    )
    parser.add_argument("--timezone", default="America/New_York")
    parser.add_argument("--stake-cents", type=int, default=100)
    parser.add_argument("--max-order-stake-cents", type=int, default=100)
    parser.add_argument(
        "--market-type",
        action="append",
        dest="market_types",
        help="Market type to include. Can be repeated. Defaults to strategy-specific discovery.",
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--live",
        action="store_true",
        help="Submit real orders. Requires KALSHI_ALLOW_LIVE_TRADING=true in the environment.",
    )
    mode_group.add_argument(
        "--simulate",
        action="store_true",
        help="Assume orders fill successfully and write simulated trade/status CSVs.",
    )
    parser.add_argument(
        "--skip-status-refresh",
        action="store_true",
        help="Do not refresh date-scoped trade status CSVs after execution.",
    )
    parser.add_argument(
        "--status-market-lookup-timeout",
        type=int,
        default=8,
        help="HTTP timeout in seconds for each status market lookup.",
    )
    parser.add_argument(
        "--status-market-lookup-retries",
        type=int,
        default=1,
        help="Retries for each status market lookup.",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run scheduled strategy execution.")
    subparsers = parser.add_subparsers(dest="window", required=True)

    daily = subparsers.add_parser("daily", help="Run one local calendar day.")
    add_common_args(daily)
    daily.add_argument("--date", default=dt.date.today().isoformat(), help="Local YYYY-MM-DD date.")

    weekly = subparsers.add_parser("weekly", help="Run seven local calendar days starting at --date.")
    add_common_args(weekly)
    weekly.add_argument("--date", default=dt.date.today().isoformat(), help="Local YYYY-MM-DD start date.")

    date_range = subparsers.add_parser("date-range", help="Run [--start-date, --end-date).")
    add_common_args(date_range)
    date_range.add_argument("--start-date", required=True, help="Inclusive local YYYY-MM-DD start date.")
    date_range.add_argument("--end-date", required=True, help="Exclusive local YYYY-MM-DD end date.")

    return parser


def parse_args() -> argparse.Namespace:
    return build_parser().parse_args()


def build_execution_objects(args: argparse.Namespace):
    load_env_file()
    if args.live:
        KalshiConfig.from_env()

    strategy_name = normalize_strategy_name(args.strategy, inverted=args.inverted)
    strategy = build_strategy(strategy_name, stake_cents=args.stake_cents)
    market_types = default_market_types(strategy_name, args.market_types)
    if args.engine != "kalshi":
        raise ValueError(f"unsupported engine: {args.engine}")
    provider = KalshiMarketLineProvider()
    mode = "live" if args.live else "simulation" if args.simulate else "dry_run"
    engine = KalshiExecutionEngine(
        config=ExecutionConfig(
            mode=mode,
            max_order_stake_cents=args.max_order_stake_cents,
            allowed_strategies={strategy.name},
        ),
        simulation_trade_log_path=DEFAULT_SIMULATED_TRADE_LOG_PATH,
    )
    return strategy, market_types, provider, engine


def execution_dates(args: argparse.Namespace) -> list[dt.date]:
    if args.window == "daily":
        return [parse_run_date(args.date)]
    if args.window == "weekly":
        start_date = parse_run_date(args.date)
        return iter_dates(start_date, start_date + dt.timedelta(days=7))
    if args.window == "date-range":
        return iter_dates(args.start_date, args.end_date)
    raise ValueError(f"unknown execution window: {args.window}")


def refresh_status_for_execution_dates(args: argparse.Namespace) -> list[dict[str, Any]]:
    if args.skip_status_refresh:
        return []

    summaries: list[dict[str, Any]] = []
    for run_date in execution_dates(args):
        outputs = refresh_trade_status_csvs_for_date(
            run_date=run_date,
            timezone=args.timezone,
            refresh_only_unresolved=True,
            market_lookup_timeout=args.status_market_lookup_timeout,
            market_lookup_retries=args.status_market_lookup_retries,
        )
        for output in outputs:
            summaries.append({"date": run_date.isoformat(), **output})
    return summaries


def main() -> None:
    args = parse_args()
    strategy, market_types, provider, engine = build_execution_objects(args)

    if args.window == "daily":
        runner = DailyExecutionRunner(provider=provider, engine=engine, timezone=args.timezone)
        result = runner.run_strategy(strategy, run_date=args.date, market_types=market_types)
    elif args.window == "weekly":
        runner = WeeklyExecutionRunner(provider=provider, engine=engine, timezone=args.timezone)
        result = runner.run_strategy(strategy, run_date=args.date, market_types=market_types)
    elif args.window == "date-range":
        runner = DateRangeExecutionRunner(provider=provider, engine=engine, timezone=args.timezone)
        result = runner.run_strategy(
            strategy,
            start_date=args.start_date,
            end_date=args.end_date,
            market_types=market_types,
        )
    else:
        raise ValueError(f"unknown execution window: {args.window}")

    result.metadata["engine"] = args.engine
    result.metadata["execution_mode"] = engine.config.mode
    status_summaries = refresh_status_for_execution_dates(args)
    if status_summaries:
        result.metadata["trade_status_csvs"] = status_summaries

    print(json.dumps(result.to_dict(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
