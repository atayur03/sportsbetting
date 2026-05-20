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
python -m execution.cli.run daily --engine kalshi --strategy underdog --date 2026-05-17
python -m execution.cli.run weekly --engine kalshi --strategy underdog --date 2026-05-17
python -m execution.cli.run date-range --engine kalshi --strategy underdog --start-date 2026-05-17 --end-date 2026-05-24
```

Available strategies:

- `underdog`: MLB game moneyline, buy YES on the underdog.
- `game_total_under`: MLB full-game totals, buy NO on lines priced between 40 and 60 cents.
- `inverted_underdog`: same MLB moneyline inputs as `underdog`, but flips each YES action to NO.
- `inverted_game_total_under`: same MLB game-total inputs as `game_total_under`, but flips each NO action to YES.

The inverted strategies are wrappers around the base strategies. Base strategy
names remain backwards compatible, and the CLI automatically uses the base
strategy's required market type when you choose an `inverted_*` strategy.
You can also use `--inverted` as a toggle:

```bash
python -m execution.cli.run daily --engine kalshi --strategy underdog --inverted --date 2026-05-17
python -m execution.cli.run daily --engine kalshi --strategy inverted_underdog --inverted --date 2026-05-17
```

The first command runs `inverted_underdog`. The second toggles back to
`underdog`.

All CLI modes dry-run by default. Add `--live` only when you want real orders:

```bash
python -m execution.cli.run daily --engine kalshi --strategy underdog --date 2026-05-19 --stake-cents 100 --max-order-stake-cents 100 --live
python -m execution.cli.run daily --engine kalshi --strategy game_total_under --date 2026-05-17 --stake-cents 100 --max-order-stake-cents 100 --live
python -m execution.cli.run daily --engine kalshi --strategy inverted_underdog --date 2026-05-17 --stake-cents 100 --max-order-stake-cents 100 --live
python -m execution.cli.run daily --engine kalshi --strategy inverted_game_total_under --date 2026-05-17 --stake-cents 100 --max-order-stake-cents 100 --live
```

Simulation uses the selected engine's market mapping but does not place real
orders. Simulated orders are assumed filled, use UUID-backed simulated order
IDs, and write the same columns as the real trade log:

```bash
python -m execution.cli.run daily --engine kalshi --strategy underdog --date 2026-05-17 --stake-cents 100 --max-order-stake-cents 100 --simulate
```

Daily execution refreshes the date-scoped trade status CSV after the run. Use
`--skip-status-refresh` if you only want discovery/order execution:

```bash
python -m execution.cli.run daily --engine kalshi --strategy underdog --date 2026-05-17 --skip-status-refresh
```

For live trading, set both:

- `ExecutionConfig(mode="live")`
- `KALSHI_ALLOW_LIVE_TRADING=true` in `.env`

Trade status dashboard:

Real trades are appended to S3 at:

```text
private/kalshi/trading/real_trade_log.csv
```

The old local path, `kalshi/trading/data/real_trade_log.csv`, is now only a
logical path used to choose the S3 key. If a local file already exists and the
S3 object does not, the first write seeds S3 from that local file.

Status dashboards are written by game date to S3:

```text
private/execution/status/trade_status_YYYY-MM-DD.csv
```

Simulated trades are appended to S3 at:

```text
private/execution/simulations/kalshi/simulated_trade_log.csv
```

Simulated status dashboards are written by game date to S3:

```text
private/execution/simulations/kalshi/trade_status_YYYY-MM-DD.csv
```

To update one date manually, run:

```bash
python -m execution.cli.status --date 2026-05-17
```

That reads the trade log, filters to games on that local date, checks only
unresolved rows by default, and writes both real and simulated outputs when the
source logs exist:

```text
private/execution/status/trade_status_2026-05-17.csv
private/execution/simulations/kalshi/trade_status_2026-05-17.csv
```

Useful status commands:

```bash
python -m execution.cli.status --date 2026-05-17
python -m execution.cli.status --date 2026-05-17 --refresh-all
python -m execution.cli.status --date 2026-05-17 --market-lookup-timeout 15 --market-lookup-retries 2
```

The S3 cache and any legacy local status CSVs/trade logs are ignored by git
because they can contain real trade/account metadata.

AWS Lambda equivalents live under `aws/lambdas/` and are deployed by
`LambdaSportsBettingStack`. Use those for scheduled or manual cloud updates
instead of running local status/export commands once the stack is deployed.
