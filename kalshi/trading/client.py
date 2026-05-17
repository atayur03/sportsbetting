#!/usr/bin/env python3
"""Authenticated Kalshi trading client.

Live order placement is intentionally opt-in. Use dry-run while wiring model
signals, then set both the env flag and CLI flag when you mean to send orders.
"""

from __future__ import annotations

import argparse
import base64
import csv
import datetime
import json
import os
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from kalshi.markets.mlb_markets import (  # noqa: E402
    SUMMARY_COLUMNS,
    get_market_anywhere,
    market_summary_row,
)


DEFAULT_BASE_URL = "https://external-api.kalshi.com/trade-api/v2"
DEMO_BASE_URL = "https://external-api.demo.kalshi.co/trade-api/v2"
DEFAULT_TRADE_LOG_PATH = PROJECT_ROOT / "kalshi" / "trading" / "data" / "real_trade_log.csv"
DEFAULT_FILL_HISTORY_PATH = PROJECT_ROOT / "kalshi" / "trading" / "data" / "fill_history.csv"

FILL_COLUMNS = [
    "source",
    "fill_id",
    "trade_id",
    "order_id",
    "ticker",
    "market_ticker",
    "side",
    "action",
    "outcome_side",
    "book_side",
    "count_fp",
    "yes_price_dollars",
    "no_price_dollars",
    "is_taker",
    "fee_cost",
    "created_time",
    "subaccount_number",
    "ts",
    "raw_fill",
]

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


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def load_private_key(path: Path):
    with path.open("rb") as file:
        return serialization.load_pem_private_key(
            file.read(),
            password=None,
            backend=default_backend(),
        )


def create_signature(private_key, timestamp: str, method: str, path: str) -> str:
    path_without_query = path.split("?", 1)[0]
    message = f"{timestamp}{method.upper()}{path_without_query}".encode("utf-8")
    hash_algorithm = hashes.SHA256()
    signature = private_key.sign(
        message,
        padding.PSS(
            mgf=padding.MGF1(hash_algorithm),
            salt_length=hash_algorithm.digest_size,
        ),
        hash_algorithm,
    )
    return base64.b64encode(signature).decode("utf-8")


@dataclass(frozen=True)
class KalshiConfig:
    api_key_id: str
    private_key_path: Path
    base_url: str = DEFAULT_BASE_URL
    allow_live_trading: bool = False

    @classmethod
    def from_env(cls) -> "KalshiConfig":
        api_key_id = os.getenv("KALSHI_API_KEY_ID", "")
        private_key_path = os.getenv("KALSHI_PRIVATE_KEY_PATH", "")
        base_url = os.getenv("KALSHI_BASE_URL", DEFAULT_BASE_URL)

        missing = [
            name
            for name, value in (
                ("KALSHI_API_KEY_ID", api_key_id),
                ("KALSHI_PRIVATE_KEY_PATH", private_key_path),
            )
            if not value
        ]
        if missing:
            raise ValueError(f"Missing required env values: {', '.join(missing)}")

        return cls(
            api_key_id=api_key_id,
            private_key_path=Path(private_key_path).expanduser(),
            base_url=base_url.rstrip("/"),
            allow_live_trading=env_bool("KALSHI_ALLOW_LIVE_TRADING"),
        )


class KalshiTradingClient:
    def __init__(self, config: KalshiConfig):
        self.config = config
        self.private_key = load_private_key(config.private_key_path)

    def _headers(self, method: str, path: str) -> dict[str, str]:
        timestamp = str(int(datetime.datetime.now().timestamp() * 1000))
        sign_path = urlparse(self.config.base_url + path).path
        signature = create_signature(self.private_key, timestamp, method, sign_path)
        return {
            "KALSHI-ACCESS-KEY": self.config.api_key_id,
            "KALSHI-ACCESS-SIGNATURE": signature,
            "KALSHI-ACCESS-TIMESTAMP": timestamp,
            "Content-Type": "application/json",
        }

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        timeout: int = 30,
    ) -> dict[str, Any]:
        response = requests.request(
            method=method.upper(),
            url=self.config.base_url + path,
            headers=self._headers(method, path),
            params=params,
            json=data,
            timeout=timeout,
        )
        response.raise_for_status()
        return response.json()

    def get_balance(self) -> dict[str, Any]:
        return self.request("GET", "/portfolio/balance")

    def list_orders(self, *, limit: int = 100, status: str | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": limit}
        if status:
            params["status"] = status
        return self.request("GET", "/portfolio/orders", params=params)

    def list_fills_page(
        self,
        *,
        historical: bool = False,
        ticker: str | None = None,
        order_id: str | None = None,
        min_ts: int | None = None,
        max_ts: int | None = None,
        limit: int = 1000,
        cursor: str | None = None,
        subaccount: int | None = None,
    ) -> dict[str, Any]:
        params = fill_query_params(
            ticker=ticker,
            order_id=order_id,
            min_ts=min_ts,
            max_ts=max_ts,
            limit=limit,
            cursor=cursor,
            subaccount=subaccount,
        )
        path = "/historical/fills" if historical else "/portfolio/fills"
        return self.request("GET", path, params=params)

    def iter_fills(
        self,
        *,
        historical: bool = False,
        ticker: str | None = None,
        order_id: str | None = None,
        min_ts: int | None = None,
        max_ts: int | None = None,
        limit: int = 1000,
        max_pages: int | None = None,
        subaccount: int | None = None,
    ):
        cursor = ""
        page = 0
        source = "historical" if historical else "live"

        while True:
            page += 1
            payload = self.list_fills_page(
                historical=historical,
                ticker=ticker,
                order_id=order_id,
                min_ts=min_ts,
                max_ts=max_ts,
                limit=limit,
                cursor=cursor or None,
                subaccount=subaccount,
            )

            for fill in payload.get("fills") or []:
                yield normalize_fill(fill, source=source)

            cursor = str(payload.get("cursor") or "")
            if not cursor:
                break
            if max_pages is not None and page >= max_pages:
                break

    def fetch_fill_history(
        self,
        *,
        include_live: bool = True,
        include_historical: bool = True,
        ticker: str | None = None,
        order_id: str | None = None,
        min_ts: int | None = None,
        max_ts: int | None = None,
        limit: int = 1000,
        max_pages: int | None = None,
        subaccount: int | None = None,
    ) -> list[dict[str, Any]]:
        fills: list[dict[str, Any]] = []
        if include_live:
            fills.extend(
                self.iter_fills(
                    historical=False,
                    ticker=ticker,
                    order_id=order_id,
                    min_ts=min_ts,
                    max_ts=max_ts,
                    limit=limit,
                    max_pages=max_pages,
                    subaccount=subaccount,
                )
            )
        if include_historical:
            fills.extend(
                self.iter_fills(
                    historical=True,
                    ticker=ticker,
                    order_id=order_id,
                    min_ts=min_ts,
                    max_ts=max_ts,
                    limit=limit,
                    max_pages=max_pages,
                    subaccount=subaccount,
                )
            )

        return sorted(fills, key=lambda row: (row.get("ts") is None, row.get("ts") or 0, row.get("fill_id") or ""))

    def export_fill_history_csv(
        self,
        path: Path = DEFAULT_FILL_HISTORY_PATH,
        **kwargs,
    ) -> list[dict[str, Any]]:
        fills = self.fetch_fill_history(**kwargs)
        write_fills_csv(path, fills)
        return fills

    def place_order(
        self,
        *,
        ticker: str,
        action: str,
        side: str,
        count: int,
        order_type: str,
        yes_price: int | None = None,
        no_price: int | None = None,
        client_order_id: str | None = None,
        dry_run: bool = True,
    ) -> dict[str, Any]:
        order = build_order_payload(
            ticker=ticker,
            action=action,
            side=side,
            count=count,
            order_type=order_type,
            yes_price=yes_price,
            no_price=no_price,
            client_order_id=client_order_id,
        )

        if dry_run:
            return {"dry_run": True, "order": order}

        return self.place_logged_order(
            ticker=ticker,
            action=action,
            side=side,
            count=count,
            order_type=order_type,
            yes_price=yes_price,
            no_price=no_price,
            client_order_id=order["client_order_id"],
            dry_run=False,
        )

    def place_logged_order(
        self,
        *,
        ticker: str,
        action: str,
        side: str,
        count: int,
        order_type: str,
        yes_price: int | None = None,
        no_price: int | None = None,
        client_order_id: str | None = None,
        log_path: Path = DEFAULT_TRADE_LOG_PATH,
        strategy: str = "manual",
        dry_run: bool = True,
    ) -> dict[str, Any]:
        """Place an order through the project-owned execution path.

        Dry runs return the order and market snapshot but do not write the CSV.
        Real orders are logged only after Kalshi accepts the order request.
        """
        placed_time_utc = utc_now_iso()
        market, market_source = get_market_anywhere(ticker, prefer_historical=False)
        order = build_order_payload(
            ticker=ticker,
            action=action,
            side=side,
            count=count,
            order_type=order_type,
            yes_price=yes_price,
            no_price=no_price,
            client_order_id=client_order_id,
        )
        log_row = build_trade_log_row(
            placed_time_utc=placed_time_utc,
            market=market,
            market_source=market_source,
            order=order,
            order_response=None,
            strategy=strategy,
        )

        if dry_run:
            return {"dry_run": True, "order": order, "market_source": market_source, "log_preview": log_row}

        if not self.config.allow_live_trading:
            raise RuntimeError("Set KALSHI_ALLOW_LIVE_TRADING=true in .env before live orders.")

        response = self.request("POST", "/portfolio/orders", data=order)
        log_row = build_trade_log_row(
            placed_time_utc=placed_time_utc,
            market=market,
            market_source=market_source,
            order=order,
            order_response=response,
            strategy=strategy,
        )
        append_trade_log(log_path, log_row)
        return {"dry_run": False, "order": order, "response": response, "log_path": str(log_path)}


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


def fill_query_params(
    *,
    ticker: str | None = None,
    order_id: str | None = None,
    min_ts: int | None = None,
    max_ts: int | None = None,
    limit: int = 1000,
    cursor: str | None = None,
    subaccount: int | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {"limit": limit}
    optional = {
        "ticker": ticker,
        "order_id": order_id,
        "min_ts": min_ts,
        "max_ts": max_ts,
        "cursor": cursor,
        "subaccount": subaccount,
    }
    for key, value in optional.items():
        if value is not None and value != "":
            params[key] = value
    return params


def normalize_fill(fill: dict[str, Any], *, source: str) -> dict[str, Any]:
    row = {"source": source, **{column: fill.get(column) for column in FILL_COLUMNS if column not in {"source", "raw_fill"}}}
    row["raw_fill"] = json.dumps(fill, sort_keys=True)
    return {column: row.get(column) for column in FILL_COLUMNS}


def write_fills_csv(path: Path, fills: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=FILL_COLUMNS)
        writer.writeheader()
        writer.writerows(fills)


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


def append_trade_log(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = path.exists()
    with path.open("a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=TRADE_LOG_COLUMNS)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


def print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Authenticated Kalshi trading helpers.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("balance", help="Fetch account balance.")

    orders = subparsers.add_parser("orders", help="List recent orders.")
    orders.add_argument("--limit", type=int, default=100)
    orders.add_argument("--status")

    fills = subparsers.add_parser("fills", help="Export Kalshi fill/trade history.")
    fills.add_argument("--csv-path", type=Path, default=DEFAULT_FILL_HISTORY_PATH)
    fills.add_argument("--ticker")
    fills.add_argument("--order-id")
    fills.add_argument("--min-ts", type=int)
    fills.add_argument("--max-ts", type=int)
    fills.add_argument("--limit", type=int, default=1000)
    fills.add_argument("--max-pages", type=int)
    fills.add_argument("--subaccount", type=int)
    fills.add_argument("--live-only", action="store_true")
    fills.add_argument("--historical-only", action="store_true")

    place = subparsers.add_parser("place-order", help="Build or submit a Kalshi order.")
    place.add_argument("--ticker", required=True)
    place.add_argument("--action", choices=["buy", "sell"], required=True)
    place.add_argument("--side", choices=["yes", "no"], required=True)
    place.add_argument("--count", type=int, required=True)
    place.add_argument("--type", default="limit", choices=["limit"])
    place.add_argument("--yes-price", type=int)
    place.add_argument("--no-price", type=int)
    place.add_argument("--client-order-id")
    place.add_argument("--strategy", default="manual", help="Strategy tag written to the real trade log.")
    place.add_argument(
        "--log-path",
        type=Path,
        default=DEFAULT_TRADE_LOG_PATH,
        help=f"CSV path for real trade logs. Defaults to {DEFAULT_TRADE_LOG_PATH}.",
    )
    place.add_argument(
        "--live",
        action="store_true",
        help="Actually submit the order. Without this flag, prints a dry-run payload.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.command == "place-order" and not args.live:
        print_json(
            {
                "dry_run": True,
                "order": build_order_payload(
                    ticker=args.ticker,
                    action=args.action,
                    side=args.side,
                    count=args.count,
                    order_type=args.type,
                    yes_price=args.yes_price,
                    no_price=args.no_price,
                    client_order_id=args.client_order_id,
                ),
            }
        )
        return

    config = KalshiConfig.from_env()
    client = KalshiTradingClient(config)

    if args.command == "balance":
        print_json(client.get_balance())
    elif args.command == "orders":
        print_json(client.list_orders(limit=args.limit, status=args.status))
    elif args.command == "fills":
        if args.live_only and args.historical_only:
            raise ValueError("Use at most one of --live-only or --historical-only")
        fills = client.export_fill_history_csv(
            args.csv_path,
            include_live=not args.historical_only,
            include_historical=not args.live_only,
            ticker=args.ticker,
            order_id=args.order_id,
            min_ts=args.min_ts,
            max_ts=args.max_ts,
            limit=args.limit,
            max_pages=args.max_pages,
            subaccount=args.subaccount,
        )
        print_json({"fills": len(fills), "csv_path": str(args.csv_path)})
    elif args.command == "place-order":
        print_json(
            client.place_logged_order(
                ticker=args.ticker,
                action=args.action,
                side=args.side,
                count=args.count,
                order_type=args.type,
                yes_price=args.yes_price,
                no_price=args.no_price,
                client_order_id=args.client_order_id,
                log_path=args.log_path,
                strategy=args.strategy,
                dry_run=not args.live,
            )
        )


if __name__ == "__main__":
    main()
