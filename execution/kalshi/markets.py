"""Normalize Kalshi MLB submarkets into strategy market lines."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from kalshi.markets.mlb_markets import list_active_mlb_markets
from execution.core.spec import ExecutionTarget
from strategy import MarketLine, SportsLeague


TOTAL_MARKET_PREFIXES = {
    "game_moneyline": "KXMLBGAME-",
    "game_total": "KXMLBTOTAL-",
    "first5_total": "KXMLBF5TOTAL-",
    "team_total": "KXMLBTEAMTOTAL-",
}


class DefaultKalshiMarketsClient:
    def list_active_mlb_markets(self) -> list[dict[str, Any]]:
        return list_active_mlb_markets()


def dollars_to_cents(value: Any) -> int | None:
    if value in {None, ""}:
        return None
    return round(float(value) * 100)


def parse_float(value: Any) -> float | None:
    if value in {None, ""}:
        return None
    return float(value)


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def market_type_from_ticker(ticker: str) -> str | None:
    for market_type, prefix in TOTAL_MARKET_PREFIXES.items():
        if ticker.startswith(prefix):
            return market_type
    return None


def event_key_from_event_ticker(event_ticker: str) -> str:
    """Return the event-ish portion of a Kalshi event ticker.

    This is a first-pass standard ID. Later, this can be replaced with an ESPN
    game ID matcher while keeping strategy code unchanged.
    """
    if "-" not in event_ticker:
        return slug(event_ticker)
    return slug(event_ticker.split("-", 1)[1])


def participant_from_market(market: dict[str, Any], market_type: str) -> str | None:
    if market_type == "game_moneyline":
        yes_sub_title = str(market.get("yes_sub_title") or "").strip()
        return yes_sub_title or None
    if market_type != "team_total":
        return None
    yes_sub_title = str(market.get("yes_sub_title") or "")
    if " over " in yes_sub_title.lower():
        return yes_sub_title.split(" over ", 1)[0].strip()
    title = str(market.get("title") or "")
    match = re.search(r"Will (.+?) score over", title, flags=re.IGNORECASE)
    return match.group(1).strip() if match else None


def line_id_for_market(market: dict[str, Any], market_type: str) -> str:
    event_key = event_key_from_event_ticker(str(market.get("event_ticker") or ""))
    participant = participant_from_market(market, market_type)
    parts = ["mlb", event_key, market_type]
    if participant:
        parts.append(slug(participant))
    if market_type == "game_moneyline":
        return ":".join(parts)
    line_value = parse_float(market.get("floor_strike"))
    parts.extend(["over", str(line_value)])
    return ":".join(parts)


def kalshi_market_to_line_and_target(market: dict[str, Any]) -> tuple[MarketLine, ExecutionTarget] | None:
    """Return a normalized line and private execution target for one market."""
    ticker = str(market.get("ticker") or "")
    event_ticker = str(market.get("event_ticker") or "")
    market_type = market_type_from_ticker(ticker)
    if not market_type:
        return None
    strike_type = str(market.get("strike_type") or "").lower()
    if market_type == "game_moneyline":
        if strike_type != "structured":
            return None
        line_value = None
        selection = "winner"
    else:
        if strike_type != "greater":
            return None
        line_value = parse_float(market.get("floor_strike"))
        if line_value is None:
            return None
        selection = "over"

    if market_type != "game_moneyline" and line_value is None:
        return None

    participant = participant_from_market(market, market_type)
    line_id = line_id_for_market(market, market_type)
    line = MarketLine(
        line_id=line_id,
        sports_league=SportsLeague.MLB,
        league="mlb",
        event_id=f"mlb:{event_key_from_event_ticker(event_ticker)}",
        market_type=market_type,
        selection=selection,
        participant=participant,
        line_value=line_value,
        event_name=str(market.get("title") or ""),
        start_time_utc=market.get("occurrence_datetime"),
        close_time_utc=market.get("close_time"),
        yes_bid_cents=dollars_to_cents(market.get("yes_bid_dollars")),
        yes_ask_cents=dollars_to_cents(market.get("yes_ask_dollars")),
        no_bid_cents=dollars_to_cents(market.get("no_bid_dollars")),
        no_ask_cents=dollars_to_cents(market.get("no_ask_dollars")),
        metadata={
            "source": "kalshi",
            "kalshi_event_ticker": event_ticker,
            "kalshi_ticker": ticker,
            "yes_sub_title": market.get("yes_sub_title"),
            "no_sub_title": market.get("no_sub_title"),
        },
    )
    target = ExecutionTarget(
        line_id=line_id,
        venue="kalshi",
        venue_ticker=ticker,
        event_ticker=event_ticker,
        metadata={"market_type": market_type},
    )
    return line, target


def within_time_window(
    line: MarketLine,
    *,
    start_time_utc: str | None = None,
    end_time_utc: str | None = None,
) -> bool:
    if not line.start_time_utc:
        return True
    if start_time_utc is not None and line.start_time_utc < start_time_utc:
        return False
    if end_time_utc is not None and line.start_time_utc >= end_time_utc:
        return False
    return True


@dataclass
class KalshiMarketLineProvider:
    """Find Kalshi MLB submarkets and expose strategy-facing lines."""

    markets_client: Any = field(default_factory=DefaultKalshiMarketsClient)
    _targets_by_line_id: dict[str, ExecutionTarget] = field(default_factory=dict, init=False)

    def list_lines(
        self,
        *,
        market_types: set[str] | None = None,
        start_time_utc: str | None = None,
        end_time_utc: str | None = None,
    ) -> list[MarketLine]:
        """Return normalized active MLB lines.

        `market_types` examples: `{"game_moneyline"}`, `{"team_total"}`,
        `{"game_moneyline", "game_total", "first5_total", "team_total"}`.
        """
        lines: list[MarketLine] = []
        targets_by_line_id: dict[str, ExecutionTarget] = {}

        for market in self.markets_client.list_active_mlb_markets():
            converted = kalshi_market_to_line_and_target(market)
            if converted is None:
                continue
            line, target = converted
            if market_types is not None and line.market_type not in market_types:
                continue
            if not within_time_window(line, start_time_utc=start_time_utc, end_time_utc=end_time_utc):
                continue
            lines.append(line)
            targets_by_line_id[line.line_id] = target

        self._targets_by_line_id = targets_by_line_id
        return lines

    def execution_targets(self) -> list[ExecutionTarget]:
        """Return Kalshi targets for the most recent `list_lines` call."""
        return list(self._targets_by_line_id.values())
