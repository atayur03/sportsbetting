"""Order payload and trade-log helpers that do not require auth dependencies."""

from __future__ import annotations

import datetime
import json
import uuid
from pathlib import Path
from typing import Any

from aws.helpers.project_files import append_csv_row
from kalshi.markets.mlb_markets import SUMMARY_COLUMNS, market_summary_row


TRADE_LOG_COLUMNS = [
    "placed_time_utc",
    "strategy",
    "market_source",
    "client_order_id",
    "order_id",
    "order_status",
    "action",
    "side",
    "count",
    "order_type",
    "limit_price_cents",
    "limit_price_dollars",
    "amount_dollars",
    "price_at_placement_dollars",
    "order_response",
] + SUMMARY_COLUMNS


def build_order_payload(
    *,
    ticker: str,
    action: str,
    side: str,
    count: int,
    order_type: str,
    yes_price: int | None = None,
    no_price: int | None = None,
    client_order_id: str | None = None,
) -> dict[str, Any]:
    action = action.lower()
    side = side.lower()
    order_type = order_type.lower()

    if action not in {"buy", "sell"}:
        raise ValueError("action must be 'buy' or 'sell'")
    if side not in {"yes", "no"}:
        raise ValueError("side must be 'yes' or 'no'")
    if count <= 0:
        raise ValueError("count must be positive")
    if order_type != "limit":
        raise ValueError("only limit orders are supported for now")
    if yes_price is None and no_price is None:
        raise ValueError("provide yes_price or no_price in cents")
    if yes_price is not None and no_price is not None:
        raise ValueError("provide only one of yes_price or no_price")

    price = yes_price if yes_price is not None else no_price
    if price is None or not 1 <= price <= 99:
        raise ValueError("price must be an integer from 1 to 99 cents")

    order: dict[str, Any] = {
        "ticker": ticker,
        "action": action,
        "side": side,
        "count": count,
        "type": order_type,
        "client_order_id": client_order_id or str(uuid.uuid4()),
    }
    if yes_price is not None:
        order["yes_price"] = yes_price
    else:
        order["no_price"] = no_price

    return order


def utc_now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def order_limit_price_cents(order: dict[str, Any]) -> int:
    price = order.get("yes_price") if "yes_price" in order else order.get("no_price")
    if not isinstance(price, int):
        raise ValueError("order is missing integer yes_price or no_price")
    return price


def price_at_placement(market: dict[str, Any], *, action: str, side: str) -> Any:
    action = action.lower()
    side = side.lower()
    field_by_order = {
        ("buy", "yes"): "yes_ask_dollars",
        ("sell", "yes"): "yes_bid_dollars",
        ("buy", "no"): "no_ask_dollars",
        ("sell", "no"): "no_bid_dollars",
    }
    return market.get(field_by_order[(action, side)])


def order_response_value(order_response: dict[str, Any] | None, *keys: str) -> Any:
    if not order_response:
        return None
    nested_order = order_response.get("order") if isinstance(order_response.get("order"), dict) else {}
    for key in keys:
        if key in nested_order:
            return nested_order[key]
        if key in order_response:
            return order_response[key]
    return None


def build_trade_log_row(
    *,
    placed_time_utc: str,
    market: dict[str, Any],
    market_source: str,
    order: dict[str, Any],
    order_response: dict[str, Any] | None,
    strategy: str = "manual",
) -> dict[str, Any]:
    limit_price_cents = order_limit_price_cents(order)
    count = int(order["count"])
    market_row = market_summary_row(market)
    row: dict[str, Any] = {
        "placed_time_utc": placed_time_utc,
        "strategy": strategy,
        "market_source": market_source,
        "client_order_id": order.get("client_order_id"),
        "order_id": order_response_value(order_response, "order_id", "id"),
        "order_status": order_response_value(order_response, "status"),
        "action": order.get("action"),
        "side": order.get("side"),
        "count": count,
        "order_type": order.get("type"),
        "limit_price_cents": limit_price_cents,
        "limit_price_dollars": f"{limit_price_cents / 100:.4f}",
        "amount_dollars": f"{count * limit_price_cents / 100:.4f}",
        "price_at_placement_dollars": price_at_placement(
            market,
            action=str(order.get("action")),
            side=str(order.get("side")),
        ),
        "order_response": json.dumps(order_response, sort_keys=True) if order_response else "",
    }
    row.update(market_row)
    return {column: row.get(column) for column in TRADE_LOG_COLUMNS}


def append_trade_log(path: Path, row: dict[str, Any]) -> str:
    return append_csv_row(path, row, TRADE_LOG_COLUMNS)
