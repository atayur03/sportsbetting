# Sports Trading Research

This repo is organized around four pieces:

1. Scrapers collect sports data.
2. Strategies turn normalized market lines into recommended actions.
3. Kalshi APIs provide market discovery and trading primitives.
4. Execution consumes strategy recommendations and routes approved orders
   through the logged Kalshi trading path.

The key boundary is:

```text
execution market discovery -> strategy.StrategyRun -> execution.KalshiExecutionEngine -> kalshi.KalshiTrading
```

Execution owns venue-specific market lookup and translates those markets into
portable `strategy.MarketLine` rows. Strategies emit `strategy.WagerAction`
objects keyed by `line_id`, not Kalshi tickers. Execution then resolves
`line_id` back to the venue target, validates guardrails, dry-runs by default,
and only places live orders through the existing Kalshi logging path.

Strategies declare a non-empty set of `strategy.SportsLeague` values as part of
their public identity, so querying a strategy tells you which sports leagues it
supports. Market lines and strategy runs carry one concrete sports league. The
enum currently defines `MLB`, `NBA`, `WNBA`, `NFL`, and `NHL`, but only `MLB`
is wired through execution right now.

For Kalshi MLB totals, `execution.KalshiMarketLineProvider` normalizes active
submarkets like game totals, first-five totals, and team totals into strategy
lines while keeping the ticker mapping inside execution.

Kalshi-specific execution code lives under `execution/kalshi/`. Scheduled
execution runners live under `execution/schedules/` and support daily, weekly,
and date-range runs.
