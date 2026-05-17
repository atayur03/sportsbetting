"""Public interface for the local Kalshi integration.

Import from this module, or from `kalshi`, when building strategy code. The
lower-level modules remain available, but these classes define the intended
surface area for market discovery and trading.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from kalshi.markets.mlb_markets import (
    SUMMARY_COLUMNS,
    get_historical_market,
    get_market,
    get_market_anywhere,
    list_active_mlb_markets,
    market_resolution_dataframe,
    market_resolution_row,
    market_summary_row,
    market_summary_rows,
    markets_to_dataframe,
    write_csv,
    write_json,
)
from kalshi.trading.client import (
    DEFAULT_FILL_HISTORY_PATH,
    DEFAULT_TRADE_LOG_PATH,
    FILL_COLUMNS,
    TRADE_LOG_COLUMNS,
    KalshiConfig,
    KalshiTradingClient,
    build_order_payload,
)


class KalshiMarkets:
    """Public market-data interface.

    Return-shape conventions:
    - "market" means Kalshi's raw market dict from the REST API.
    - "summary row" means one normalized dict with `summary_columns`.
    - dataframe methods contain one row per normalized market.
    """

    summary_columns = SUMMARY_COLUMNS

    def list_active_mlb_markets(
        self,
        *,
        limit: int = 1000,
        max_pages: int | None = None,
        timeout: int = 30,
        retries: int = 3,
        exclude_multivariate: bool = True,
    ) -> list[dict[str, Any]]:
        """Return raw Kalshi market dicts for all active MLB/baseball markets.

        Shape: `list[market]`, one raw market object per tradable ticker.
        """
        return list_active_mlb_markets(
            limit=limit,
            max_pages=max_pages,
            timeout=timeout,
            retries=retries,
            exclude_multivariate=exclude_multivariate,
        )

    def active_mlb_markets_dataframe(self, **kwargs) -> pd.DataFrame:
        """Return active MLB markets as normalized rows.

        Shape: dataframe with one row per market ticker and columns from
        `KalshiMarkets.summary_columns`.
        """
        return markets_to_dataframe(self.list_active_mlb_markets(**kwargs))

    def get_market(self, ticker: str, *, timeout: int = 30, retries: int = 3) -> dict[str, Any]:
        """Return one raw live/recent Kalshi market dict for `ticker`."""
        return get_market(ticker, timeout=timeout, retries=retries)

    def get_historical_market(self, ticker: str, *, timeout: int = 30, retries: int = 3) -> dict[str, Any]:
        """Return one raw historical Kalshi market dict for `ticker`.

        This is intended for settled markets old enough to live in Kalshi's
        historical partition.
        """
        return get_historical_market(ticker, timeout=timeout, retries=retries)

    def get_market_anywhere(
        self,
        ticker: str,
        *,
        prefer_historical: bool = True,
        timeout: int = 30,
        retries: int = 3,
    ) -> tuple[dict[str, Any], str]:
        """Return one raw market dict plus source label.

        Shape: `(market, source)`, where `source` is `"historical"` or `"live"`.
        """
        return get_market_anywhere(
            ticker,
            prefer_historical=prefer_historical,
            timeout=timeout,
            retries=retries,
        )

    def market_summary_row(self, market: dict[str, Any]) -> dict[str, Any]:
        """Return one normalized market row.

        Shape: dict with keys from `KalshiMarkets.summary_columns`.
        """
        return market_summary_row(market)

    def market_summary_rows(self, markets: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Return normalized market rows.

        Shape: `list[summary row]`, preserving input order.
        """
        return market_summary_rows(markets)

    def market_resolution_row(self, market: dict[str, Any]) -> dict[str, Any]:
        """Return settlement/resolution fields for one market.

        Shape: dict containing status, result, expiration value, settlement
        value/time, and rule text. Some values may be blank/null for active
        markets.
        """
        return market_resolution_row(market)

    def market_resolution_dataframe(self, market: dict[str, Any]) -> pd.DataFrame:
        """Return one-row dataframe of settlement/resolution fields."""
        return market_resolution_dataframe(market)

    def write_markets_json(self, path: Path, markets: Any) -> None:
        """Write raw market object(s) to JSON. Returns nothing."""
        write_json(path, markets)

    def write_markets_csv(self, path: Path, markets: list[dict[str, Any]]) -> None:
        """Write normalized market rows to CSV. Returns nothing."""
        write_csv(path, market_summary_rows(markets))


class KalshiTrading:
    """Public trading and account-history interface.

    Return-shape conventions:
    - order history returns Kalshi's raw paginated orders response.
    - fill history returns normalized fill rows with `fill_columns`.
    - place_order returns a dry-run preview or Kalshi order response plus log path.
    """

    fill_columns = FILL_COLUMNS
    trade_log_columns = TRADE_LOG_COLUMNS

    def __init__(
        self,
        config: KalshiConfig | None = None,
        *,
        client: KalshiTradingClient | None = None,
    ):
        self.client = client or KalshiTradingClient(config or KalshiConfig.from_env())

    @classmethod
    def from_env(cls) -> "KalshiTrading":
        """Create a trading interface from `os.getenv` credentials."""
        return cls(KalshiConfig.from_env())

    def get_balance(self) -> dict[str, Any]:
        """Return Kalshi's raw balance response dict."""
        return self.client.get_balance()

    def get_order_history(self, *, limit: int = 100, status: str | None = None) -> dict[str, Any]:
        """Return Kalshi's raw recent order-history response.

        Shape: paginated response dict from `/portfolio/orders`.
        """
        return self.client.list_orders(limit=limit, status=status)

    def get_fill_history(
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
        """Return normalized matched trade/fill rows.

        Shape: `list[fill row]`, with keys from `KalshiTrading.fill_columns`.
        By default this combines recent `/portfolio/fills` and older
        `/historical/fills`.
        """
        return self.client.fetch_fill_history(
            include_live=include_live,
            include_historical=include_historical,
            ticker=ticker,
            order_id=order_id,
            min_ts=min_ts,
            max_ts=max_ts,
            limit=limit,
            max_pages=max_pages,
            subaccount=subaccount,
        )

    def export_fill_history_csv(
        self,
        path: Path = DEFAULT_FILL_HISTORY_PATH,
        **kwargs,
    ) -> list[dict[str, Any]]:
        """Write fill history CSV and return the normalized fill rows written."""
        return self.client.export_fill_history_csv(path, **kwargs)

    def build_order(
        self,
        *,
        ticker: str,
        action: str,
        side: str,
        count: int,
        order_type: str = "limit",
        yes_price: int | None = None,
        no_price: int | None = None,
        client_order_id: str | None = None,
    ) -> dict[str, Any]:
        """Return an order payload dict without submitting it.

        Shape: dict suitable for Kalshi's create-order endpoint.
        """
        return build_order_payload(
            ticker=ticker,
            action=action,
            side=side,
            count=count,
            order_type=order_type,
            yes_price=yes_price,
            no_price=no_price,
            client_order_id=client_order_id,
        )

    def place_order(
        self,
        *,
        ticker: str,
        action: str,
        side: str,
        count: int,
        order_type: str = "limit",
        yes_price: int | None = None,
        no_price: int | None = None,
        client_order_id: str | None = None,
        log_path: Path = DEFAULT_TRADE_LOG_PATH,
        strategy: str = "manual",
        dry_run: bool = True,
    ) -> dict[str, Any]:
        """Dry-run or submit an order through the logged execution path.

        Dry-run shape:
        `{"dry_run": True, "order": order payload, "market_source": str,
        "log_preview": trade log row}`.

        Live shape:
        `{"dry_run": False, "order": order payload, "response": Kalshi response,
        "log_path": str}`. Live orders append one row to the trade log CSV.
        `strategy` is written to the trade log so multiple strategies can share
        the same execution path.
        """
        return self.client.place_logged_order(
            ticker=ticker,
            action=action,
            side=side,
            count=count,
            order_type=order_type,
            yes_price=yes_price,
            no_price=no_price,
            client_order_id=client_order_id,
            log_path=log_path,
            strategy=strategy,
            dry_run=dry_run,
        )


__all__ = [
    "KalshiConfig",
    "KalshiMarkets",
    "KalshiTrading",
    "KalshiTradingClient",
]
