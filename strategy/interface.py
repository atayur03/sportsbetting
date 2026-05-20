"""Interfaces strategy implementations should satisfy."""

from __future__ import annotations

from typing import Protocol

from strategy.core.spec import MarketLine, SportsLeague, StrategyRun


class Strategy(Protocol):
    """A venue-agnostic betting strategy.

    Input shape: `list[MarketLine]`, supplied by execution, all for a supported
    `SportsLeague`.

    Return shape: `StrategyRun`, containing `sports_league` plus zero or more
    `WagerAction` rows keyed by `line_id`.
    """

    name: str
    supported_sports_leagues: set[SportsLeague]

    def evaluate(self, lines: list[MarketLine]) -> StrategyRun:
        """Return strategy recommendations for normalized market lines."""

    def metadata(self) -> dict[str, object]:
        """Return a small serializable identity row for discovery."""
        return {
            "name": self.name,
            "supported_sports_leagues": sorted(
                sports_league.value for sports_league in self.supported_sports_leagues
            ),
        }
