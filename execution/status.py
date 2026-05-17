"""Build trade-status CSVs from the real trade log."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
from pathlib import Path
from typing import Any

from kalshi import KalshiMarkets
from execution.schedules.daily import DEFAULT_EXECUTION_TIMEZONE, daily_utc_window, parse_run_date


DEFAULT_TRADE_LOG_PATH = Path("kalshi/trading/data/real_trade_log.csv")
DEFAULT_TRADE_STATUS_PATH = Path("execution/data/trade_status.csv")
DEFAULT_TRADE_STATUS_DIR = Path("execution/data")
DEFAULT_MARKET_LOOKUP_TIMEOUT = 8
DEFAULT_MARKET_LOOKUP_RETRIES = 1

OPEN_STATUSES = {"active", "open", "initialized", "paused"}
UNRESOLVED_TRADE_STATUSES = {"", "open", "unknown"}

TRADE_STATUS_COLUMNS = [
    "checked_time_utc",
    "engine",
    "trade_status",
    "strategy",
    "sports_league",
    "placed_time_utc",
    "ticker",
    "event_ticker",
    "order_id",
    "client_order_id",
    "order_status",
    "action",
    "side",
    "count",
    "limit_price_cents",
    "limit_price_dollars",
    "amount_dollars",
    "price_at_placement_dollars",
    "market_lookup_source",
    "market_status",
    "market_result",
    "expiration_value",
    "settlement_value_dollars",
    "settlement_ts",
    "title",
    "subtitle",
    "yes_sub_title",
    "no_sub_title",
    "floor_strike",
    "strike_type",
    "occurrence_datetime",
    "close_time",
    "expected_expiration_time",
    "expiration_time",
    "last_price_dollars",
    "yes_bid_dollars",
    "yes_ask_dollars",
    "no_bid_dollars",
    "no_ask_dollars",
    "rules_primary",
]


def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def read_trade_log(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Trade log not found: {path}")
    with path.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def read_trade_status_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def trade_status_path_for_date(
    run_date: dt.date | str,
    *,
    output_dir: Path = DEFAULT_TRADE_STATUS_DIR,
) -> Path:
    """Return the date-scoped trade-status CSV path."""
    return output_dir / f"trade_status_{parse_run_date(run_date).isoformat()}.csv"


def filter_trade_rows_for_date(
    rows: list[dict[str, Any]],
    *,
    run_date: dt.date | str,
    timezone: str = DEFAULT_EXECUTION_TIMEZONE,
) -> list[dict[str, Any]]:
    """Return rows whose logged market/game time falls on one local date."""
    start_time_utc, end_time_utc = daily_utc_window(run_date, timezone=timezone)
    filtered_rows: list[dict[str, Any]] = []
    for row in rows:
        event_time = (
            row.get("occurrence_datetime")
            or row.get("expected_expiration_time")
            or row.get("expiration_time")
            or row.get("close_time")
            or row.get("placed_time_utc")
            or ""
        )
        if start_time_utc <= str(event_time) < end_time_utc:
            filtered_rows.append(row)
    return filtered_rows


def trade_row_key(row: dict[str, Any]) -> tuple[str, str, str, str, str]:
    """Return a stable key that links one trade-log row to one status row."""
    return (
        str(row.get("order_id") or ""),
        str(row.get("client_order_id") or ""),
        str(row.get("ticker") or ""),
        str(row.get("side") or ""),
        str(row.get("placed_time_utc") or ""),
    )


def infer_sports_league(row: dict[str, Any], market: dict[str, Any] | None = None) -> str:
    text = " ".join(
        str(value or "")
        for value in [
            row.get("ticker"),
            row.get("event_ticker"),
            row.get("title"),
            row.get("rules_primary"),
            (market or {}).get("ticker"),
            (market or {}).get("event_ticker"),
            (market or {}).get("title"),
            (market or {}).get("rules_primary"),
        ]
    ).lower()
    if "kxmlb" in text or "baseball" in text:
        return "MLB"
    return ""


def normalize_market_result(market: dict[str, Any]) -> str:
    for field in ("result", "expiration_value"):
        value = market.get(field)
        if value not in {None, ""}:
            return str(value).lower()
    return ""


def trade_status(row: dict[str, Any], market: dict[str, Any] | None, lookup_error: str = "") -> str:
    if lookup_error:
        return "unknown"
    if market is None:
        return "unknown"

    market_status = str(market.get("status") or "").lower()
    result = normalize_market_result(market)
    if market_status in OPEN_STATUSES or not result:
        return "open"

    side = str(row.get("side") or "").lower()
    action = str(row.get("action") or "").lower()
    if action != "buy" or side not in {"yes", "no"}:
        return "unknown"
    if result in {"yes", "y", "1", "true"}:
        winning_side = "yes"
    elif result in {"no", "n", "0", "false"}:
        winning_side = "no"
    else:
        return "unknown"
    return "won" if side == winning_side else "lost"


def build_status_row(
    row: dict[str, Any],
    *,
    market: dict[str, Any] | None,
    market_lookup_source: str,
    checked_time_utc: str,
    lookup_error: str = "",
) -> dict[str, Any]:
    market = market or {}
    result = {
        "checked_time_utc": checked_time_utc,
        "engine": "kalshi",
        "trade_status": trade_status(row, market, lookup_error),
        "strategy": row.get("strategy"),
        "sports_league": infer_sports_league(row, market),
        "placed_time_utc": row.get("placed_time_utc"),
        "ticker": row.get("ticker"),
        "event_ticker": row.get("event_ticker"),
        "order_id": row.get("order_id"),
        "client_order_id": row.get("client_order_id"),
        "order_status": row.get("order_status"),
        "action": row.get("action"),
        "side": row.get("side"),
        "count": row.get("count"),
        "limit_price_cents": row.get("limit_price_cents"),
        "limit_price_dollars": row.get("limit_price_dollars"),
        "amount_dollars": row.get("amount_dollars"),
        "price_at_placement_dollars": row.get("price_at_placement_dollars"),
        "market_lookup_source": market_lookup_source,
        "market_status": market.get("status") or row.get("status"),
        "market_result": normalize_market_result(market),
        "expiration_value": market.get("expiration_value") or row.get("expiration_value"),
        "settlement_value_dollars": market.get("settlement_value_dollars") or row.get("settlement_value_dollars"),
        "settlement_ts": market.get("settlement_ts") or row.get("settlement_ts"),
        "title": market.get("title") or row.get("title"),
        "subtitle": market.get("subtitle") or row.get("subtitle"),
        "yes_sub_title": market.get("yes_sub_title") or row.get("yes_sub_title"),
        "no_sub_title": market.get("no_sub_title") or row.get("no_sub_title"),
        "floor_strike": market.get("floor_strike") or row.get("floor_strike"),
        "strike_type": market.get("strike_type") or row.get("strike_type"),
        "occurrence_datetime": market.get("occurrence_datetime") or row.get("occurrence_datetime"),
        "close_time": market.get("close_time") or row.get("close_time"),
        "expected_expiration_time": market.get("expected_expiration_time") or row.get("expected_expiration_time"),
        "expiration_time": market.get("expiration_time") or row.get("expiration_time"),
        "last_price_dollars": market.get("last_price_dollars") or row.get("last_price_dollars"),
        "yes_bid_dollars": market.get("yes_bid_dollars") or row.get("yes_bid_dollars"),
        "yes_ask_dollars": market.get("yes_ask_dollars") or row.get("yes_ask_dollars"),
        "no_bid_dollars": market.get("no_bid_dollars") or row.get("no_bid_dollars"),
        "no_ask_dollars": market.get("no_ask_dollars") or row.get("no_ask_dollars"),
        "rules_primary": market.get("rules_primary") or row.get("rules_primary"),
    }
    if lookup_error:
        result["market_result"] = lookup_error
    return {column: result.get(column, "") for column in TRADE_STATUS_COLUMNS}


def build_trade_status_rows(
    trade_rows: list[dict[str, Any]],
    *,
    markets: KalshiMarkets | None = None,
    checked_time_utc: str | None = None,
    prefer_historical: bool = False,
    existing_status_rows: list[dict[str, Any]] | None = None,
    refresh_only_unresolved: bool = True,
    market_lookup_timeout: int = DEFAULT_MARKET_LOOKUP_TIMEOUT,
    market_lookup_retries: int = DEFAULT_MARKET_LOOKUP_RETRIES,
) -> list[dict[str, Any]]:
    markets = markets or KalshiMarkets()
    checked_time_utc = checked_time_utc or utc_now_iso()
    market_cache: dict[str, tuple[dict[str, Any] | None, str, str]] = {}
    existing_rows_by_key = {trade_row_key(row): row for row in existing_status_rows or []}
    status_rows: list[dict[str, Any]] = []

    for row in trade_rows:
        existing_row = existing_rows_by_key.get(trade_row_key(row))
        existing_trade_status = str((existing_row or {}).get("trade_status") or "").lower()
        if refresh_only_unresolved and existing_row and existing_trade_status not in UNRESOLVED_TRADE_STATUSES:
            status_rows.append({column: existing_row.get(column, "") for column in TRADE_STATUS_COLUMNS})
            continue

        ticker = str(row.get("ticker") or "")
        if ticker not in market_cache:
            try:
                market, source = markets.get_market_anywhere(
                    ticker,
                    prefer_historical=prefer_historical,
                    timeout=market_lookup_timeout,
                    retries=market_lookup_retries,
                )
                market_cache[ticker] = (market, source, "")
            except Exception as exc:
                market_cache[ticker] = (None, "", f"lookup_error: {exc}")
        market, source, error = market_cache[ticker]
        status_rows.append(
            build_status_row(
                row,
                market=market,
                market_lookup_source=source,
                checked_time_utc=checked_time_utc,
                lookup_error=error,
            )
        )

    return status_rows


def write_trade_status_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=TRADE_STATUS_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def refresh_trade_status_csv(
    *,
    trade_log_path: Path = DEFAULT_TRADE_LOG_PATH,
    output_path: Path | None = None,
    output_dir: Path = DEFAULT_TRADE_STATUS_DIR,
    run_date: dt.date | str | None = None,
    timezone: str = DEFAULT_EXECUTION_TIMEZONE,
    prefer_historical: bool = False,
    refresh_only_unresolved: bool = True,
    market_lookup_timeout: int = DEFAULT_MARKET_LOOKUP_TIMEOUT,
    market_lookup_retries: int = DEFAULT_MARKET_LOOKUP_RETRIES,
) -> list[dict[str, Any]]:
    trade_rows = read_trade_log(trade_log_path)
    if run_date is not None:
        trade_rows = filter_trade_rows_for_date(trade_rows, run_date=run_date, timezone=timezone)
        output_path = output_path or trade_status_path_for_date(run_date, output_dir=output_dir)
    else:
        output_path = output_path or DEFAULT_TRADE_STATUS_PATH

    existing_status_rows = read_trade_status_csv(output_path)
    rows = build_trade_status_rows(
        trade_rows,
        prefer_historical=prefer_historical,
        existing_status_rows=existing_status_rows,
        refresh_only_unresolved=refresh_only_unresolved,
        market_lookup_timeout=market_lookup_timeout,
        market_lookup_retries=market_lookup_retries,
    )
    write_trade_status_csv(output_path, rows)
    return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh Kalshi trade status CSV.")
    parser.add_argument("--trade-log-path", type=Path, default=DEFAULT_TRADE_LOG_PATH)
    parser.add_argument("--output-path", type=Path)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_TRADE_STATUS_DIR)
    parser.add_argument("--date", help="Local YYYY-MM-DD date to refresh into a date-scoped CSV.")
    parser.add_argument("--timezone", default=DEFAULT_EXECUTION_TIMEZONE)
    parser.add_argument("--market-lookup-timeout", type=int, default=DEFAULT_MARKET_LOOKUP_TIMEOUT)
    parser.add_argument("--market-lookup-retries", type=int, default=DEFAULT_MARKET_LOOKUP_RETRIES)
    parser.add_argument(
        "--prefer-historical",
        action="store_true",
        help="Check Kalshi historical markets before live markets. Defaults to live first.",
    )
    parser.add_argument(
        "--refresh-all",
        action="store_true",
        help="Refresh every row, including already won/lost rows. Defaults to unresolved rows only.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = refresh_trade_status_csv(
        trade_log_path=args.trade_log_path,
        output_path=args.output_path,
        output_dir=args.output_dir,
        run_date=args.date,
        timezone=args.timezone,
        prefer_historical=args.prefer_historical,
        refresh_only_unresolved=not args.refresh_all,
        market_lookup_timeout=args.market_lookup_timeout,
        market_lookup_retries=args.market_lookup_retries,
    )
    output_path = args.output_path
    if output_path is None:
        if args.date:
            output_path = trade_status_path_for_date(args.date, output_dir=args.output_dir)
        else:
            output_path = DEFAULT_TRADE_STATUS_PATH
    counts: dict[str, int] = {}
    for row in rows:
        counts[str(row["trade_status"])] = counts.get(str(row["trade_status"]), 0) + 1
    print({"output_path": str(output_path), "rows": len(rows), "counts": counts})


if __name__ == "__main__":
    main()
