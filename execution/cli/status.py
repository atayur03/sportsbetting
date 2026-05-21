"""Build trade-status CSVs from the real trade log."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any

from kalshi.markets.mlb_markets import get_market_anywhere
from aws.helpers.project_files import destination as project_file_destination
from aws.helpers.project_files import exists as project_file_exists
from aws.helpers.project_files import read_csv_rows, read_csv_rows_if_exists, write_csv_rows
from aws.helpers.project_files import require_s3_for_managed_paths
from execution.schedules.daily import DEFAULT_EXECUTION_TIMEZONE, daily_utc_window, parse_run_date


class KalshiMarkets:
    def get_market_anywhere(
        self,
        ticker: str,
        *,
        prefer_historical: bool = True,
        timeout: int = 30,
        retries: int = 3,
    ) -> tuple[dict[str, Any], str]:
        return get_market_anywhere(
            ticker,
            prefer_historical=prefer_historical,
            timeout=timeout,
            retries=retries,
        )


DEFAULT_TRADE_LOG_PATH = Path("kalshi/trading/data/real_trade_log.csv")
DEFAULT_TRADE_STATUS_PATH = Path("execution/data/trade_status.csv")
DEFAULT_TRADE_STATUS_DIR = Path("execution/data")
DEFAULT_SIMULATION_DIR = Path("execution/data/simulations")
DEFAULT_SIMULATED_TRADE_LOG_PATH = DEFAULT_SIMULATION_DIR / "kalshi" / "simulated_trade_log.csv"
DEFAULT_SIMULATED_TRADE_STATUS_DIR = DEFAULT_SIMULATION_DIR / "kalshi"
DEFAULT_MARKET_LOOKUP_TIMEOUT = 8
DEFAULT_MARKET_LOOKUP_RETRIES = 1

OPEN_STATUSES = {"active", "open", "initialized", "paused"}
UNRESOLVED_TRADE_STATUSES = {"", "open", "unknown", "pending_order", "partial_order"}

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
    "order_lifecycle_status",
    "fill_status",
    "position_status",
    "market_settlement_status",
    "initial_count",
    "filled_count",
    "remaining_count",
    "avg_fill_price_dollars",
    "filled_cost_dollars",
    "order_created_time",
    "order_last_update_time",
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
    return read_csv_rows(path)


def read_trade_status_csv(path: Path) -> list[dict[str, str]]:
    return read_csv_rows_if_exists(path)


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


def parse_number(value: Any) -> float:
    if value in {None, ""}:
        return 0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0


def order_response(row: dict[str, Any]) -> dict[str, Any]:
    raw = row.get("order_response")
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        parsed = json.loads(str(raw))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def nested_order_response(row: dict[str, Any]) -> dict[str, Any]:
    response = order_response(row)
    nested = response.get("order")
    return nested if isinstance(nested, dict) else response


def order_value(row: dict[str, Any], *keys: str) -> Any:
    order = nested_order_response(row)
    for key in keys:
        if key in order and order[key] not in {None, ""}:
            return order[key]
    for key in keys:
        if row.get(key) not in {None, ""}:
            return row.get(key)
    return ""


def order_fill_metrics(row: dict[str, Any]) -> dict[str, Any]:
    initial_count = parse_number(order_value(row, "initial_count_fp", "count"))
    filled_count = parse_number(order_value(row, "fill_count_fp", "filled_count"))
    remaining_count = parse_number(order_value(row, "remaining_count_fp"))
    if initial_count and not filled_count and not remaining_count:
        status = str(order_value(row, "status", "order_status") or "").lower()
        if status in {"filled", "executed"}:
            filled_count = initial_count
        elif status in {"resting", "open"}:
            remaining_count = initial_count
    if initial_count and filled_count and not remaining_count:
        remaining_count = max(initial_count - filled_count, 0)

    maker_cost = parse_number(order_value(row, "maker_fill_cost_dollars"))
    taker_cost = parse_number(order_value(row, "taker_fill_cost_dollars"))
    filled_cost = maker_cost + taker_cost
    if filled_count and not filled_cost:
        filled_cost = filled_count * parse_number(row.get("limit_price_dollars"))
    avg_fill_price = filled_cost / filled_count if filled_count else 0

    return {
        "initial_count": initial_count,
        "filled_count": filled_count,
        "remaining_count": remaining_count,
        "filled_cost_dollars": filled_cost,
        "avg_fill_price_dollars": avg_fill_price,
    }


def order_lifecycle_status(row: dict[str, Any], metrics: dict[str, Any]) -> str:
    status = str(order_value(row, "status", "order_status") or "").lower()
    filled_count = parse_number(metrics.get("filled_count"))
    remaining_count = parse_number(metrics.get("remaining_count"))
    if status in {"rejected", "canceled", "cancelled"}:
        return "canceled" if status == "cancelled" else status
    if filled_count and remaining_count:
        return "partially_filled"
    if filled_count and not remaining_count:
        return "filled"
    if status in {"executed", "filled"}:
        return "filled"
    if status in {"resting", "open"}:
        return "resting"
    if status:
        return status
    return "submitted"


def fill_status(metrics: dict[str, Any]) -> str:
    filled_count = parse_number(metrics.get("filled_count"))
    remaining_count = parse_number(metrics.get("remaining_count"))
    if not filled_count:
        return "unfilled"
    if remaining_count:
        return "partial"
    return "filled"


def market_settlement_status(row: dict[str, Any], market: dict[str, Any] | None, lookup_error: str = "") -> str:
    if lookup_error:
        return "unknown"
    if market is None:
        return "unknown"

    market_status = str(market.get("status") or "").lower()
    result = normalize_market_result(market)
    if market_status in OPEN_STATUSES or not result:
        return "unresolved"

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


def position_status(fill_state: str, settlement_state: str) -> str:
    if fill_state == "unfilled":
        return "none"
    if settlement_state in {"won", "lost"}:
        return "settled"
    return "open"


def trade_status(
    row: dict[str, Any],
    market: dict[str, Any] | None,
    lookup_error: str = "",
    *,
    metrics: dict[str, Any] | None = None,
) -> str:
    metrics = metrics or order_fill_metrics(row)
    lifecycle = order_lifecycle_status(row, metrics)
    fill_state = fill_status(metrics)
    settlement_state = market_settlement_status(row, market, lookup_error)

    if fill_state == "unfilled":
        if lifecycle in {"canceled", "cancelled", "rejected"}:
            return "canceled"
        return "pending_order"
    if settlement_state in {"won", "lost"}:
        return settlement_state
    if fill_state == "partial":
        return "partial_order"
    if settlement_state == "unknown":
        return "unknown"
    return "open"


def build_status_row(
    row: dict[str, Any],
    *,
    market: dict[str, Any] | None,
    market_lookup_source: str,
    checked_time_utc: str,
    lookup_error: str = "",
) -> dict[str, Any]:
    market = market or {}
    metrics = order_fill_metrics(row)
    fill_state = fill_status(metrics)
    settlement_state = market_settlement_status(row, market, lookup_error)
    result = {
        "checked_time_utc": checked_time_utc,
        "engine": "kalshi",
        "trade_status": trade_status(row, market, lookup_error, metrics=metrics),
        "strategy": row.get("strategy"),
        "sports_league": infer_sports_league(row, market),
        "placed_time_utc": row.get("placed_time_utc"),
        "ticker": row.get("ticker"),
        "event_ticker": row.get("event_ticker"),
        "order_id": row.get("order_id"),
        "client_order_id": row.get("client_order_id"),
        "order_status": row.get("order_status"),
        "order_lifecycle_status": order_lifecycle_status(row, metrics),
        "fill_status": fill_state,
        "position_status": position_status(fill_state, settlement_state),
        "market_settlement_status": settlement_state,
        "initial_count": format_number(metrics["initial_count"]),
        "filled_count": format_number(metrics["filled_count"]),
        "remaining_count": format_number(metrics["remaining_count"]),
        "avg_fill_price_dollars": format_dollars(metrics["avg_fill_price_dollars"]),
        "filled_cost_dollars": format_dollars(metrics["filled_cost_dollars"]),
        "order_created_time": order_value(row, "created_time"),
        "order_last_update_time": order_value(row, "last_update_time"),
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


def format_number(value: Any) -> str:
    number = parse_number(value)
    if number.is_integer():
        return str(int(number))
    return f"{number:.4f}".rstrip("0").rstrip(".")


def format_dollars(value: Any) -> str:
    return f"{parse_number(value):.4f}"


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
    write_csv_rows(path, rows, TRADE_STATUS_COLUMNS)


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


def refresh_trade_status_csvs_for_date(
    *,
    run_date: dt.date | str,
    timezone: str = DEFAULT_EXECUTION_TIMEZONE,
    refresh_only_unresolved: bool = True,
    market_lookup_timeout: int = DEFAULT_MARKET_LOOKUP_TIMEOUT,
    market_lookup_retries: int = DEFAULT_MARKET_LOOKUP_RETRIES,
) -> list[dict[str, Any]]:
    """Refresh real and simulated date-scoped status CSVs when source logs exist."""
    outputs: list[dict[str, Any]] = []
    sources = [
        {
            "label": "real",
            "trade_log_path": DEFAULT_TRADE_LOG_PATH,
            "output_dir": DEFAULT_TRADE_STATUS_DIR,
        },
        {
            "label": "simulation",
            "trade_log_path": DEFAULT_SIMULATED_TRADE_LOG_PATH,
            "output_dir": DEFAULT_SIMULATED_TRADE_STATUS_DIR,
        },
    ]
    for source in sources:
        trade_log_path = source["trade_log_path"]
        output_dir = source["output_dir"]
        if not project_file_exists(trade_log_path):
            continue
        rows = refresh_trade_status_csv(
            trade_log_path=trade_log_path,
            output_dir=output_dir,
            run_date=run_date,
            timezone=timezone,
            refresh_only_unresolved=refresh_only_unresolved,
            market_lookup_timeout=market_lookup_timeout,
            market_lookup_retries=market_lookup_retries,
        )
        counts: dict[str, int] = {}
        for row in rows:
            status = str(row.get("trade_status") or "")
            counts[status] = counts.get(status, 0) + 1
        outputs.append(
            {
                "source": source["label"],
                "trade_log_path": project_file_destination(trade_log_path),
                "output_path": project_file_destination(trade_status_path_for_date(run_date, output_dir=output_dir)),
                "rows": len(rows),
                "counts": counts,
            }
        )
    return outputs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh real and simulated Kalshi trade status CSVs.")
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
    if args.date and args.trade_log_path == DEFAULT_TRADE_LOG_PATH and args.output_path is None:
        require_s3_for_managed_paths(
            [
                DEFAULT_TRADE_LOG_PATH,
                DEFAULT_SIMULATED_TRADE_LOG_PATH,
                trade_status_path_for_date(args.date, output_dir=DEFAULT_TRADE_STATUS_DIR),
                trade_status_path_for_date(args.date, output_dir=DEFAULT_SIMULATED_TRADE_STATUS_DIR),
            ]
        )
    if (
        args.date
        and args.trade_log_path == DEFAULT_TRADE_LOG_PATH
        and args.output_path is None
        and args.output_dir == DEFAULT_TRADE_STATUS_DIR
    ):
        summaries = refresh_trade_status_csvs_for_date(
            run_date=args.date,
            timezone=args.timezone,
            refresh_only_unresolved=not args.refresh_all,
            market_lookup_timeout=args.market_lookup_timeout,
            market_lookup_retries=args.market_lookup_retries,
        )
        print({"outputs": summaries})
        return

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
