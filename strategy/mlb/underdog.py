"""Basic MLB underdog strategy."""

from __future__ import annotations

from collections import defaultdict

from strategy import MarketLine, SportsLeague, StrategyRun, WagerAction


class UnderdogStrategy:
    """Buy YES on the lowest-priced game moneyline in each MLB game."""

    name = "underdog"
    supported_sports_leagues = {SportsLeague.MLB}

    def __init__(self, *, stake_cents: int = 100, skip_ties: bool = True):
        if stake_cents <= 0:
            raise ValueError("stake_cents must be positive")
        self.stake_cents = stake_cents
        self.skip_ties = skip_ties

    def evaluate(self, lines: list[MarketLine]) -> StrategyRun:
        """Return one YES buy recommendation per game moneyline underdog."""
        lines_by_event_id: dict[str, list[MarketLine]] = defaultdict(list)
        for line in lines:
            if line.sports_league != SportsLeague.MLB:
                continue
            if line.market_type != "game_moneyline":
                continue
            if line.yes_ask_cents is None:
                continue
            lines_by_event_id[line.event_id].append(line)

        actions: list[WagerAction] = []
        skipped_ties = 0
        for event_id, event_lines in sorted(lines_by_event_id.items()):
            if len(event_lines) < 2:
                continue
            lowest_ask = min(line.yes_ask_cents for line in event_lines if line.yes_ask_cents is not None)
            underdogs = [line for line in event_lines if line.yes_ask_cents == lowest_ask]
            if self.skip_ties and len(underdogs) != 1:
                skipped_ties += 1
                continue

            underdog = sorted(underdogs, key=lambda line: line.line_id)[0]
            actions.append(
                WagerAction(
                    line_id=underdog.line_id,
                    action="buy",
                    side="yes",
                    limit_price_cents=int(lowest_ask),
                    stake_cents=self.stake_cents,
                    strategy=self.name,
                    reason="Lowest YES ask among game moneyline markets for this event.",
                    metadata={
                        "event_id": event_id,
                        "participant": underdog.participant,
                        "market_type": underdog.market_type,
                    },
                )
            )

        return StrategyRun(
            strategy_name=self.name,
            sports_league=SportsLeague.MLB,
            actions=actions,
            metadata={
                "stake_cents": self.stake_cents,
                "skip_ties": self.skip_ties,
                "events_seen": len(lines_by_event_id),
                "skipped_ties": skipped_ties,
            },
        )
