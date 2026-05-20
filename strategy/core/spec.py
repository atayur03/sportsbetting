"""Venue-agnostic specs for strategy inputs and outputs.

Execution owns market discovery and venue-specific identifiers. A strategy sees
normalized `MarketLine` rows and returns `WagerAction` rows keyed by `line_id`.
That means the same strategy can run against Kalshi today and another venue
later, as long as execution can map `line_id` to a tradable venue target.
"""

from __future__ import annotations

import datetime as dt
import math
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Literal


Action = Literal["buy", "sell"]
Side = Literal["yes", "no"]


class SportsLeague(str, Enum):
    """Supported strategy sports-league identifiers.

    Only MLB is wired through execution today. NBA, WNBA, NFL, and NHL are
    reserved for future providers and strategies.
    """

    MLB = "MLB"
    NBA = "NBA"
    WNBA = "WNBA"
    NFL = "NFL"
    NHL = "NHL"


def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class MarketLine:
    """One normalized, venue-agnostic market line passed to a strategy.

    The `line_id` is the stable join key. Strategies should return this ID in
    `WagerAction.line_id`; they should not know Kalshi tickers or event tickers.

    Example line IDs:
    - `mlb:2026-05-17:nyy-bos:total_runs:8.5`
    - `mlb:2026-05-17:nyy-bos:moneyline:nyy`
    """

    line_id: str
    sports_league: SportsLeague
    league: str
    event_id: str
    market_type: str
    selection: str
    participant: str | None = None
    line_value: float | None = None
    event_name: str = ""
    start_time_utc: str | None = None
    close_time_utc: str | None = None
    yes_bid_cents: int | None = None
    yes_ask_cents: int | None = None
    no_bid_cents: int | None = None
    no_ask_cents: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.line_id:
            raise ValueError("line_id is required")
        if not isinstance(self.sports_league, SportsLeague):
            object.__setattr__(self, "sports_league", SportsLeague(self.sports_league))
        if not self.league:
            raise ValueError("league is required")
        if not self.event_id:
            raise ValueError("event_id is required")
        if not self.market_type:
            raise ValueError("market_type is required")
        if not self.selection:
            raise ValueError("selection is required")

    def to_dict(self) -> dict[str, Any]:
        row = asdict(self)
        row["sports_league"] = self.sports_league.value
        return row


@dataclass(frozen=True)
class WagerAction:
    """One strategy recommendation for one normalized market line.

    Required fields are the minimum execution needs after resolving `line_id`
    to a venue target: action, side, limit price, and either count or stake.

    Returned shape: serializable dict via `to_dict()`.
    """

    line_id: str
    action: Action
    side: Side
    limit_price_cents: int
    strategy: str
    stake_cents: int | None = None
    count: int | None = None
    confidence: float | None = None
    edge_cents: float | None = None
    fair_price_cents: float | None = None
    reason: str = ""
    generated_at_utc: str = field(default_factory=utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.line_id:
            raise ValueError("line_id is required")
        if self.action not in {"buy", "sell"}:
            raise ValueError("action must be 'buy' or 'sell'")
        if self.side not in {"yes", "no"}:
            raise ValueError("side must be 'yes' or 'no'")
        if not 1 <= self.limit_price_cents <= 99:
            raise ValueError("limit_price_cents must be between 1 and 99")
        if not self.strategy:
            raise ValueError("strategy is required")
        if self.count is None and self.stake_cents is None:
            raise ValueError("provide count or stake_cents")
        if self.count is not None and self.count <= 0:
            raise ValueError("count must be positive")
        if self.stake_cents is not None and self.stake_cents <= 0:
            raise ValueError("stake_cents must be positive")
        if self.confidence is not None and not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")

    @property
    def resolved_count(self) -> int:
        """Return the contract count execution should submit."""
        if self.count is not None:
            return self.count
        assert self.stake_cents is not None
        return max(1, math.floor(self.stake_cents / self.limit_price_cents))

    @property
    def estimated_cost_cents(self) -> int:
        """Return estimated cents at the limit price."""
        return self.resolved_count * self.limit_price_cents

    def to_order_kwargs(self, *, ticker: str) -> dict[str, Any]:
        """Return kwargs compatible with `KalshiTrading.place_order`.

        Execution supplies `ticker` after resolving `line_id` through its venue
        registry. Strategy code should not call this directly.
        """
        order_kwargs: dict[str, Any] = {
            "ticker": ticker,
            "action": self.action,
            "side": self.side,
            "count": self.resolved_count,
            "strategy": self.strategy,
        }
        if self.side == "yes":
            order_kwargs["yes_price"] = self.limit_price_cents
        else:
            order_kwargs["no_price"] = self.limit_price_cents
        return order_kwargs

    def to_dict(self) -> dict[str, Any]:
        row = asdict(self)
        row["resolved_count"] = self.resolved_count
        row["estimated_cost_cents"] = self.estimated_cost_cents
        return row


@dataclass(frozen=True)
class StrategyRun:
    """Batch of recommendations from one strategy run.

    Returned shape: serializable dict via `to_dict()`, with `actions` as a list
    of `WagerAction.to_dict()` rows.
    """

    strategy_name: str
    sports_league: SportsLeague
    actions: list[WagerAction]
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    generated_at_utc: str = field(default_factory=utc_now_iso)
    data_as_of_utc: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.strategy_name:
            raise ValueError("strategy_name is required")
        if not isinstance(self.sports_league, SportsLeague):
            object.__setattr__(self, "sports_league", SportsLeague(self.sports_league))

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "strategy_name": self.strategy_name,
            "sports_league": self.sports_league.value,
            "generated_at_utc": self.generated_at_utc,
            "data_as_of_utc": self.data_as_of_utc,
            "metadata": self.metadata,
            "actions": [action.to_dict() for action in self.actions],
        }
