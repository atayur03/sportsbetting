"""Strategy-layer public interface.

Strategies consume normalized market lines and emit recommendations. They do
not import Kalshi or submit orders directly.
"""

from strategy.interface import Strategy
from strategy.inverted import InvertedStrategy, inverted_strategy_name
from strategy.registry import (
    normalize_supported_sports_leagues,
    strategies_for_sports_league,
    strategy_metadata,
)
from strategy.spec import MarketLine, SportsLeague, StrategyRun, WagerAction

__all__ = [
    "MarketLine",
    "SportsLeague",
    "Strategy",
    "StrategyRun",
    "WagerAction",
    "InvertedStrategy",
    "inverted_strategy_name",
    "normalize_supported_sports_leagues",
    "strategies_for_sports_league",
    "strategy_metadata",
]
