# Strategy Layer

The strategy layer turns normalized market lines into recommended actions. It
should not submit orders, know about private Kalshi credentials, call Kalshi, or
depend on Kalshi tickers.

Inputs are supplied by execution as `MarketLine` rows:

```python
from strategy import MarketLine, SportsLeague

line = MarketLine(
    line_id="mlb:2026-05-17:nyy-bos:total_runs:8.5",
    sports_league=SportsLeague.MLB,
    league="mlb",
    event_id="mlb:2026-05-17:nyy-bos",
    market_type="total_runs",
    selection="over",
    participant=None,
    line_value=8.5,
    event_name="Yankees at Red Sox",
    yes_ask_cents=42,
)
```

Output contract:

```python
from strategy import SportsLeague, StrategyRun, WagerAction

run = StrategyRun(
    strategy_name="mlb_totals_v1",
    sports_league=SportsLeague.MLB,
    actions=[
        WagerAction(
            line_id="mlb:2026-05-17:nyy-bos:total_runs:8.5",
            action="buy",
            side="yes",
            limit_price_cents=42,
            stake_cents=100,
            strategy="mlb_totals_v1",
            confidence=0.57,
            edge_cents=4.2,
            reason="Strategy fair price exceeds current ask.",
        )
    ],
)
```

Execution resolves `line_id` to a venue-specific target, such as a Kalshi
ticker, and decides whether to dry-run, skip, or place a real logged order.

Strategy interface:

```python
from strategy import MarketLine, SportsLeague, StrategyRun

class MyStrategy:
    name = "mlb_totals_v1"
    supported_sports_leagues = {SportsLeague.MLB}

    def evaluate(self, lines: list[MarketLine]) -> StrategyRun:
        ...
```

Strategy discovery:

```python
from strategy import SportsLeague, strategies_for_sports_league, strategy_metadata

strategy_metadata(MyStrategy())
# {"name": "mlb_totals_v1", "supported_sports_leagues": ["MLB"]}

mlb_strategies = strategies_for_sports_league([MyStrategy()], SportsLeague.MLB)
```

Built-in MLB strategies:

```python
from strategy.mlb import UnderdogStrategy

strategy = UnderdogStrategy(stake_cents=100)
run = strategy.evaluate(lines)
```

`UnderdogStrategy` expects `game_moneyline` lines and emits one YES buy action
for the lowest YES ask in each game.

```python
from strategy.mlb import GameTotalUnderStrategy

strategy = GameTotalUnderStrategy(stake_cents=100)
run = strategy.evaluate(lines)
```

`GameTotalUnderStrategy` expects `game_total` lines and emits a NO buy action
for each line where the under price is between 40 and 60 cents.
