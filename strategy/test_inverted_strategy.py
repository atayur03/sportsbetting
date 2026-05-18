from strategy import InvertedStrategy, MarketLine, SportsLeague
from strategy.mlb import GameTotalUnderStrategy


def test_inverted_strategy_flips_side_price_and_name():
    strategy = InvertedStrategy(GameTotalUnderStrategy(stake_cents=100))
    run = strategy.evaluate(
        [
            MarketLine(
                line_id="mlb:2026-05-17:nyy-bos:total_runs:8.5",
                sports_league=SportsLeague.MLB,
                league="MLB",
                event_id="nyy-bos",
                market_type="game_total",
                selection="total_runs",
                line_value=8.5,
                no_ask_cents=42,
            )
        ]
    )

    assert run.strategy_name == "inverted_game_total_under"
    assert len(run.actions) == 1
    action = run.actions[0]
    assert action.strategy == "inverted_game_total_under"
    assert action.side == "yes"
    assert action.limit_price_cents == 58
    assert action.metadata["base_strategy"] == "game_total_under"
    assert action.metadata["base_side"] == "no"
    assert action.metadata["base_limit_price_cents"] == 42
