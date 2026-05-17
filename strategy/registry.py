"""Small helpers for discovering strategies by sports league."""

from __future__ import annotations

from strategy.interface import Strategy
from strategy.spec import SportsLeague


def normalize_supported_sports_leagues(strategy: Strategy) -> set[SportsLeague]:
    """Return a validated non-empty set of supported sports leagues."""
    sports_leagues = {
        sports_league if isinstance(sports_league, SportsLeague) else SportsLeague(sports_league)
        for sports_league in strategy.supported_sports_leagues
    }
    if not sports_leagues:
        raise ValueError(f"strategy must support at least one sports league: {strategy.name}")
    return sports_leagues


def strategy_metadata(strategy: Strategy) -> dict[str, object]:
    """Return the public identity row for one strategy."""
    return {
        "name": strategy.name,
        "supported_sports_leagues": sorted(
            sports_league.value for sports_league in normalize_supported_sports_leagues(strategy)
        ),
    }


def strategies_for_sports_league(
    strategies: list[Strategy],
    sports_league: SportsLeague,
) -> list[Strategy]:
    """Return strategies that declare support for `sports_league`."""
    return [
        strategy
        for strategy in strategies
        if sports_league in normalize_supported_sports_leagues(strategy)
    ]
