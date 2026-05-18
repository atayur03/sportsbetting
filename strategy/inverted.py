"""Strategy wrapper that inverts YES/NO recommendations."""

from __future__ import annotations

from dataclasses import replace

from strategy.interface import Strategy
from strategy.spec import MarketLine, Side, StrategyRun, WagerAction


def inverted_side(side: Side) -> Side:
    """Return the opposite Kalshi side."""
    if side == "yes":
        return "no"
    if side == "no":
        return "yes"
    raise ValueError(f"unsupported side: {side}")


def inverted_limit_price_cents(limit_price_cents: int) -> int:
    """Return the inverse contract limit price."""
    return 100 - limit_price_cents


def inverted_strategy_name(strategy_name: str) -> str:
    """Return the public strategy name for an inverted strategy."""
    return f"inverted_{strategy_name}"


class InvertedStrategy:
    """Wrap any strategy and invert its YES/NO recommendations."""

    def __init__(self, strategy: Strategy):
        self.strategy = strategy
        self.name = inverted_strategy_name(strategy.name)
        self.supported_sports_leagues = strategy.supported_sports_leagues

    def evaluate(self, lines: list[MarketLine]) -> StrategyRun:
        """Evaluate the wrapped strategy, then invert every action."""
        base_run = self.strategy.evaluate(lines)
        actions = [self.invert_action(action) for action in base_run.actions]
        return StrategyRun(
            strategy_name=self.name,
            sports_league=base_run.sports_league,
            actions=actions,
            data_as_of_utc=base_run.data_as_of_utc,
            metadata={
                **base_run.metadata,
                "base_strategy_name": base_run.strategy_name,
                "inverted": True,
            },
        )

    def invert_action(self, action: WagerAction) -> WagerAction:
        """Return one action with side and limit price inverted."""
        return replace(
            action,
            side=inverted_side(action.side),
            limit_price_cents=inverted_limit_price_cents(action.limit_price_cents),
            strategy=self.name,
            reason=f"Inverted {action.strategy}: {action.reason}",
            metadata={
                **action.metadata,
                "base_strategy": action.strategy,
                "base_side": action.side,
                "base_limit_price_cents": action.limit_price_cents,
                "inverted": True,
            },
        )

    def metadata(self) -> dict[str, object]:
        """Return a serializable identity row."""
        return {
            "name": self.name,
            "base_strategy_name": self.strategy.name,
            "inverted": True,
            "supported_sports_leagues": sorted(
                sports_league.value for sports_league in self.supported_sports_leagues
            ),
        }
