"""Basic MLB game-total under strategy."""

from __future__ import annotations

from strategy import MarketLine, SportsLeague, StrategyRun, WagerAction


class GameTotalUnderStrategy:
    """Buy NO on game-total over markets when under odds are in range."""

    name = "game_total_under"
    supported_sports_leagues = {SportsLeague.MLB}

    def __init__(
        self,
        *,
        stake_cents: int = 100,
        min_odds_cents: int = 40,
        max_odds_cents: int = 60,
    ):
        if stake_cents <= 0:
            raise ValueError("stake_cents must be positive")
        if not 1 <= min_odds_cents <= 99:
            raise ValueError("min_odds_cents must be between 1 and 99")
        if not 1 <= max_odds_cents <= 99:
            raise ValueError("max_odds_cents must be between 1 and 99")
        if min_odds_cents > max_odds_cents:
            raise ValueError("min_odds_cents must be <= max_odds_cents")
        self.stake_cents = stake_cents
        self.min_odds_cents = min_odds_cents
        self.max_odds_cents = max_odds_cents

    def evaluate(self, lines: list[MarketLine]) -> StrategyRun:
        """Return one NO buy recommendation for each eligible game-total line."""
        actions: list[WagerAction] = []
        game_total_lines_seen = 0
        missing_price = 0
        out_of_range = 0

        for line in sorted(lines, key=lambda market_line: market_line.line_id):
            if line.sports_league != SportsLeague.MLB:
                continue
            if line.market_type != "game_total":
                continue

            game_total_lines_seen += 1
            if line.no_ask_cents is None:
                missing_price += 1
                continue
            if not self.min_odds_cents <= line.no_ask_cents <= self.max_odds_cents:
                out_of_range += 1
                continue

            actions.append(
                WagerAction(
                    line_id=line.line_id,
                    action="buy",
                    side="no",
                    limit_price_cents=int(line.no_ask_cents),
                    stake_cents=self.stake_cents,
                    strategy=self.name,
                    reason="Under price is inside the configured odds range for a game-total market.",
                    metadata={
                        "event_id": line.event_id,
                        "line_value": line.line_value,
                        "market_type": line.market_type,
                        "min_odds_cents": self.min_odds_cents,
                        "max_odds_cents": self.max_odds_cents,
                    },
                )
            )

        return StrategyRun(
            strategy_name=self.name,
            sports_league=SportsLeague.MLB,
            actions=actions,
            metadata={
                "stake_cents": self.stake_cents,
                "min_odds_cents": self.min_odds_cents,
                "max_odds_cents": self.max_odds_cents,
                "game_total_lines_seen": game_total_lines_seen,
                "missing_price": missing_price,
                "out_of_range": out_of_range,
            },
        )
