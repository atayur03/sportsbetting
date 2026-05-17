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
    DailyExecutionRunner,
    DateRangeExecutionRunner,
    ExecutionConfig,
    KalshiExecutionEngine,
    KalshiMarketLineProvider,
    WeeklyExecutionRunner,
)
from strategy.mlb import UnderdogStrategy


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


def build_strategy(name: str, *, stake_cents: int) -> Any:
    if name == "underdog":
        return UnderdogStrategy(stake_cents=stake_cents)
    raise ValueError(f"unknown strategy: {name}")


def default_market_types(strategy_name: str, market_types: list[str] | None) -> set[str] | None:
    parsed = parse_market_types(market_types)
    if parsed is not None:
        return parsed
    if strategy_name == "underdog":
        return {"game_moneyline"}
    return None


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--strategy", default="underdog", choices=["underdog"])
    parser.add_argument("--timezone", default="America/New_York")
    parser.add_argument("--stake-cents", type=int, default=100)
    parser.add_argument("--max-order-stake-cents", type=int, default=100)
    parser.add_argument(
        "--market-type",
        action="append",
        dest="market_types",
        help="Market type to include. Can be repeated. Defaults to strategy-specific discovery.",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Submit real orders. Requires KALSHI_ALLOW_LIVE_TRADING=true in the environment.",
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

    strategy = build_strategy(args.strategy, stake_cents=args.stake_cents)
    market_types = default_market_types(args.strategy, args.market_types)
    provider = KalshiMarketLineProvider()
    engine = KalshiExecutionEngine(
        config=ExecutionConfig(
            mode="live" if args.live else "dry_run",
            max_order_stake_cents=args.max_order_stake_cents,
            allowed_strategies={strategy.name},
        )
    )
    return strategy, market_types, provider, engine


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

    print(json.dumps(result.to_dict(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
