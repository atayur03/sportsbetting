#!/usr/bin/env python3
"""List active MLB markets from Kalshi's public REST API."""

from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote

import requests
import pandas as pd


API_BASE = "https://external-api.kalshi.com/trade-api/v2"
MARKETS_URL = f"{API_BASE}/markets"
HISTORICAL_MARKETS_URL = f"{API_BASE}/historical/markets"

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "kalshi-sports-research/0.1",
}

MLB_TERMS = ("mlb", "baseball", "kxmlb")

SUMMARY_COLUMNS = [
    "ticker",
    "event_ticker",
    "status",
    "market_type",
    "title",
    "subtitle",
    "yes_sub_title",
    "no_sub_title",
    "floor_strike",
    "strike_type",
    "primary_participant_key",
    "custom_strike",
    "open_time",
    "close_time",
    "occurrence_datetime",
    "expected_expiration_time",
    "expiration_time",
    "expiration_value",
    "result",
    "settlement_value_dollars",
    "settlement_ts",
    "last_price_dollars",
    "yes_bid_dollars",
    "yes_ask_dollars",
    "yes_bid_size_fp",
    "yes_ask_size_fp",
    "no_bid_dollars",
    "no_ask_dollars",
    "volume_fp",
    "volume_24h_fp",
    "open_interest_fp",
    "liquidity_dollars",
    "rules_primary",
]

RESOLUTION_COLUMNS = [
    "ticker",
    "event_ticker",
    "status",
    "title",
    "subtitle",
    "yes_sub_title",
    "no_sub_title",
    "result",
    "expiration_value",
    "settlement_value_dollars",
    "settlement_ts",
    "open_time",
    "close_time",
    "expected_expiration_time",
    "expiration_time",
    "rules_primary",
    "rules_secondary",
]


def request_json(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    timeout: int = 30,
    retries: int = 3,
) -> dict[str, Any]:
    last_error: Exception | None = None

    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, headers=HEADERS, params=params, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            last_error = exc
            if attempt == retries:
                break
            time.sleep(min(2 ** (attempt - 1), 10))

    assert last_error is not None
    raise last_error


def iter_markets(
    *,
    status: str = "open",
    limit: int = 1000,
    max_pages: int | None = None,
    timeout: int = 30,
    retries: int = 3,
    exclude_multivariate: bool = True,
    extra_params: dict[str, Any] | None = None,
) -> Iterable[dict[str, Any]]:
    """Yield Kalshi markets across cursor-paginated REST responses."""
    cursor = ""
    page = 0

    while True:
        page += 1
        params: dict[str, Any] = {"status": status, "limit": limit}
        if exclude_multivariate:
            params["mve_filter"] = "exclude"
        if cursor:
            params["cursor"] = cursor
        if extra_params:
            params.update(extra_params)

        payload = request_json(MARKETS_URL, params=params, timeout=timeout, retries=retries)
        for market in payload.get("markets") or []:
            yield market

        cursor = str(payload.get("cursor") or "")
        if not cursor:
            break
        if max_pages is not None and page >= max_pages:
            break


def market_search_text(market: dict[str, Any]) -> str:
    fields = [
        "ticker",
        "event_ticker",
        "series_ticker",
        "title",
        "subtitle",
        "yes_sub_title",
        "no_sub_title",
        "rules_primary",
        "rules_secondary",
        "category",
    ]
    return " ".join(str(market.get(field) or "") for field in fields).lower()


def is_mlb_market(market: dict[str, Any], terms: tuple[str, ...] = MLB_TERMS) -> bool:
    haystack = market_search_text(market)
    return any(term.lower() in haystack for term in terms)


def list_active_mlb_markets(
    *,
    limit: int = 1000,
    max_pages: int | None = None,
    timeout: int = 30,
    retries: int = 3,
    exclude_multivariate: bool = True,
) -> list[dict[str, Any]]:
    markets = iter_markets(
        status="open",
        limit=limit,
        max_pages=max_pages,
        timeout=timeout,
        retries=retries,
        exclude_multivariate=exclude_multivariate,
    )
    return [market for market in markets if is_mlb_market(market)]


def unwrap_market(payload: dict[str, Any]) -> dict[str, Any]:
    market = payload.get("market")
    if not isinstance(market, dict):
        raise ValueError(f"Expected response payload with market object, got keys: {list(payload.keys())}")
    return market


def get_market(ticker: str, *, timeout: int = 30, retries: int = 3) -> dict[str, Any]:
    """Fetch a market from Kalshi's live/recent market endpoint."""
    url = f"{MARKETS_URL}/{quote(ticker, safe='')}"
    return unwrap_market(request_json(url, timeout=timeout, retries=retries))


def get_historical_market(ticker: str, *, timeout: int = 30, retries: int = 3) -> dict[str, Any]:
    """Fetch a settled market from Kalshi's historical market endpoint."""
    url = f"{HISTORICAL_MARKETS_URL}/{quote(ticker, safe='')}"
    return unwrap_market(request_json(url, timeout=timeout, retries=retries))


def get_market_anywhere(
    ticker: str,
    *,
    prefer_historical: bool = True,
    timeout: int = 30,
    retries: int = 3,
) -> tuple[dict[str, Any], str]:
    """Fetch a market by ticker from historical or live endpoints.

    Returns the market plus the source endpoint label: "historical" or "live".
    """
    lookups = (
        (get_historical_market, "historical"),
        (get_market, "live"),
    )
    if not prefer_historical:
        lookups = tuple(reversed(lookups))

    last_error: Exception | None = None
    for lookup, source in lookups:
        try:
            return lookup(ticker, timeout=timeout, retries=retries), source
        except requests.HTTPError as exc:
            last_error = exc
            if exc.response is None or exc.response.status_code != 404:
                raise

    assert last_error is not None
    raise last_error


def market_summary_row(market: dict[str, Any]) -> dict[str, Any]:
    row = {column: market.get(column) for column in SUMMARY_COLUMNS}
    if isinstance(row.get("custom_strike"), dict):
        row["custom_strike"] = json.dumps(row["custom_strike"], sort_keys=True)
    return row


def market_summary_rows(markets: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [market_summary_row(market) for market in markets]


def market_resolution_row(market: dict[str, Any]) -> dict[str, Any]:
    return {column: market.get(column) for column in RESOLUTION_COLUMNS}


def markets_to_dataframe(markets: Iterable[dict[str, Any]]):
    return pd.DataFrame(market_summary_rows(markets))


def market_resolution_dataframe(market: dict[str, Any]):
    return pd.DataFrame([market_resolution_row(market)])


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=SUMMARY_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="List active Kalshi MLB markets.")
    parser.add_argument("--ticker", help="Fetch a single market ticker instead of listing active MLB markets.")
    parser.add_argument(
        "--historical",
        action="store_true",
        help="Use only the historical market endpoint with --ticker.",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Use only the live/recent market endpoint with --ticker.",
    )
    parser.add_argument(
        "--prefer-live",
        action="store_true",
        help="With --ticker, try the live endpoint before historical.",
    )
    parser.add_argument("--limit", type=int, default=1000, help="Markets per API page.")
    parser.add_argument("--max-pages", type=int, help="Stop after this many API pages.")
    parser.add_argument("--timeout", type=int, default=30, help="HTTP timeout in seconds.")
    parser.add_argument("--retries", type=int, default=3, help="Retries per API request.")
    parser.add_argument(
        "--include-multivariate",
        action="store_true",
        help="Include multivariate/combo markets in the scan.",
    )
    parser.add_argument("--json-path", type=Path, help="Optional raw JSON output path.")
    parser.add_argument("--csv-path", type=Path, help="Optional summary CSV output path.")
    parser.add_argument(
        "--from-json",
        type=Path,
        help="Read existing raw market JSON instead of calling the Kalshi API.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.historical and args.live:
        raise ValueError("Use at most one of --historical or --live")

    if args.ticker:
        if args.historical:
            market = get_historical_market(args.ticker, timeout=args.timeout, retries=args.retries)
            source = "historical"
        elif args.live:
            market = get_market(args.ticker, timeout=args.timeout, retries=args.retries)
            source = "live"
        else:
            market, source = get_market_anywhere(
                args.ticker,
                prefer_historical=not args.prefer_live,
                timeout=args.timeout,
                retries=args.retries,
            )

        print(f"Fetched {args.ticker} from {source} endpoint")
        print(json.dumps(market_resolution_row(market), indent=2, sort_keys=True))
        if args.json_path:
            write_json(args.json_path, market)
            print(f"Wrote market JSON: {args.json_path}")
        if args.csv_path:
            write_csv(args.csv_path, [market_summary_row(market)])
            print(f"Wrote market CSV: {args.csv_path}")
        return

    if args.from_json:
        markets = json.loads(args.from_json.read_text(encoding="utf-8"))
    else:
        markets = list_active_mlb_markets(
            limit=args.limit,
            max_pages=args.max_pages,
            timeout=args.timeout,
            retries=args.retries,
            exclude_multivariate=not args.include_multivariate,
        )

    rows = market_summary_rows(markets)
    print(f"Found {len(markets)} active MLB markets")
    for row in rows:
        print(f"{row.get('ticker')} | {row.get('title')}")

    if args.json_path:
        write_json(args.json_path, markets)
        print(f"Wrote raw markets: {args.json_path}")
    if args.csv_path:
        write_csv(args.csv_path, rows)
        print(f"Wrote market summary: {args.csv_path}")


if __name__ == "__main__":
    main()
