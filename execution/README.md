# Execution Layer

Execution owns venue-specific market discovery and order placement. Strategy
code should not know about Kalshi tickers.

Responsibilities:

- Find venue markets, such as active Kalshi MLB totals
- Normalize venue markets into `strategy.MarketLine` rows
- Keep the private mapping from `line_id` to `ExecutionTarget`
- Pass normalized lines to strategies
- Validate strategy names and max stake limits
- Dry-run recommendations by default
- Submit live orders only through `kalshi.KalshiTrading.place_order`

Example:

```python
from execution import ExecutionConfig, ExecutionTarget, KalshiExecutionEngine
from strategy import SportsLeague, StrategyRun, WagerAction

line_id = "mlb:2026-05-17:nyy-bos:total_runs:8.5"

run = StrategyRun(
    strategy_name="mlb_totals_v1",
    sports_league=SportsLeague.MLB,
    actions=[
        WagerAction(
            line_id=line_id,
            action="buy",
            side="yes",
            limit_price_cents=42,
            stake_cents=100,
            strategy="mlb_totals_v1",
        )
    ],
)

engine = KalshiExecutionEngine(
    targets=[
        ExecutionTarget(
            line_id=line_id,
            venue="kalshi",
            venue_ticker="KXMLB-...",
        )
    ],
    config=ExecutionConfig(mode="dry_run", max_order_stake_cents=100),
)

results = engine.execute_run_rows(run)
```

Finding Kalshi MLB submarkets:

```python
from execution import KalshiMarketLineProvider

provider = KalshiMarketLineProvider()
lines = provider.list_lines(
    market_types={"game_moneyline", "game_total", "first5_total", "team_total"},
    start_time_utc="2026-05-17T00:00:00Z",
    end_time_utc="2026-05-18T00:00:00Z",
)
targets = provider.execution_targets()
```

Each `MarketLine` is safe for strategy code. Each `ExecutionTarget` is private
to execution and contains the Kalshi ticker that can be traded.

Daily execution:

```python
from execution import (
    DailyExecutionRunner,
    ExecutionConfig,
    KalshiExecutionEngine,
    KalshiMarketLineProvider,
)
from strategy.mlb import UnderdogStrategy

provider = KalshiMarketLineProvider()
engine = KalshiExecutionEngine(config=ExecutionConfig(mode="dry_run"))
runner = DailyExecutionRunner(provider=provider, engine=engine)

result = runner.run_strategy(
    UnderdogStrategy(stake_cents=100),
    run_date="2026-05-17",
    market_types={"game_moneyline"},
)
```

`run_date` is interpreted as an `America/New_York` calendar day by default and
converted to a UTC `[start, end)` window before querying markets.

Weekly and date-range execution:

```python
from execution import DateRangeExecutionRunner, WeeklyExecutionRunner

weekly = WeeklyExecutionRunner(provider=provider, engine=engine)
weekly_result = weekly.run_strategy(
    UnderdogStrategy(stake_cents=100),
    run_date="2026-05-17",
    market_types={"game_moneyline"},
)

date_range = DateRangeExecutionRunner(provider=provider, engine=engine)
range_result = date_range.run_strategy(
    UnderdogStrategy(stake_cents=100),
    start_date="2026-05-17",
    end_date="2026-05-24",
    market_types={"game_moneyline"},
)
```

Date ranges use `[start_date, end_date)`, so the weekly runner is just a
date-range run from `run_date` through `run_date + 7 days`.

CLI:

```bash
python -m execution.run daily --strategy underdog --date 2026-05-17
python -m execution.run weekly --strategy underdog --date 2026-05-17
python -m execution.run date-range --strategy underdog --start-date 2026-05-17 --end-date 2026-05-24
```

All CLI modes dry-run by default. Add `--live` only when you want real orders.

For live trading, set both:

- `ExecutionConfig(mode="live")`
- `KALSHI_ALLOW_LIVE_TRADING=true` in `.env`
