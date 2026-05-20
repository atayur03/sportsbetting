"""Lambda wrapper for `python -m execution.cli.run` behavior."""

from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from execution.cli.run import (
    build_execution_objects,
    normalize_strategy_name,
    preflight_managed_storage,
    refresh_status_for_execution_dates,
)
from execution import DailyExecutionRunner, DateRangeExecutionRunner, WeeklyExecutionRunner


def lambda_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    args = _args(event)
    if args.live:
        load_kalshi_secret()
    preflight_managed_storage(args)
    strategy, market_types, provider, engine = build_execution_objects(args)

    if args.window == "daily":
        result = DailyExecutionRunner(provider=provider, engine=engine, timezone=args.timezone).run_strategy(
            strategy,
            run_date=args.date,
            market_types=market_types,
        )
    elif args.window == "weekly":
        result = WeeklyExecutionRunner(provider=provider, engine=engine, timezone=args.timezone).run_strategy(
            strategy,
            run_date=args.date,
            market_types=market_types,
        )
    elif args.window == "date-range":
        result = DateRangeExecutionRunner(provider=provider, engine=engine, timezone=args.timezone).run_strategy(
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
    return result.to_dict()


def _args(event: dict[str, Any]) -> SimpleNamespace:
    window = event.get("window", "daily")
    engine = event.get("engine")
    if not engine:
        raise ValueError("engine is required")
    strategy = event.get("strategy", "underdog")
    inverted = bool(event.get("inverted", False))
    strategy_name = normalize_strategy_name(strategy, inverted=inverted)
    today = dt.date.today().isoformat()
    return SimpleNamespace(
        window=window,
        engine=engine,
        strategy=strategy,
        inverted=inverted,
        timezone=event.get("timezone", "America/New_York"),
        stake_cents=int(event.get("stake_cents", 100)),
        max_order_stake_cents=int(event.get("max_order_stake_cents", 100)),
        market_types=event.get("market_types"),
        live=bool(event.get("live", False)),
        simulate=bool(event.get("simulate", False)),
        skip_status_refresh=bool(event.get("skip_status_refresh", False)),
        status_market_lookup_timeout=int(event.get("status_market_lookup_timeout", 8)),
        status_market_lookup_retries=int(event.get("status_market_lookup_retries", 1)),
        date=event.get("date", today),
        start_date=event.get("start_date", today),
        end_date=event.get("end_date", (dt.date.today() + dt.timedelta(days=1)).isoformat()),
        strategy_name=strategy_name,
    )


def load_kalshi_secret() -> None:
    """Load Kalshi live-trading credentials from Secrets Manager when configured."""
    secret_name = os.getenv("KALSHI_SECRET_NAME")
    if not secret_name:
        return

    import boto3

    response = boto3.client("secretsmanager").get_secret_value(SecretId=secret_name)
    secret_string = response.get("SecretString")
    if not secret_string:
        raise ValueError(f"Secret {secret_name} does not contain SecretString")

    secret = json.loads(secret_string)
    for key in ("KALSHI_API_KEY_ID", "KALSHI_BASE_URL", "KALSHI_ALLOW_LIVE_TRADING"):
        if secret.get(key) and key not in os.environ:
            os.environ[key] = str(secret[key])

    private_key_pem = secret.get("KALSHI_PRIVATE_KEY_PEM")
    if private_key_pem and "KALSHI_PRIVATE_KEY_PATH" not in os.environ:
        private_key_path = Path("/tmp/kalshi_private_key.pem")
        private_key_path.write_text(private_key_pem, encoding="utf-8")
        os.chmod(private_key_path, 0o600)
        os.environ["KALSHI_PRIVATE_KEY_PATH"] = str(private_key_path)

    if secret.get("KALSHI_PRIVATE_KEY_PATH") and "KALSHI_PRIVATE_KEY_PATH" not in os.environ:
        os.environ["KALSHI_PRIVATE_KEY_PATH"] = str(secret["KALSHI_PRIVATE_KEY_PATH"])
