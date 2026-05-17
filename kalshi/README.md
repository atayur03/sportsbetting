# Kalshi MLB Markets

Small experiments for listing active MLB markets from Kalshi's public REST API.

## Public Interface

Strategy code should import from the package-level interface:

```python
from kalshi import KalshiMarkets, KalshiTrading

markets = KalshiMarkets()
trading = KalshiTrading.from_env()
```

Market methods intended for reuse:

```python
markets.list_active_mlb_markets()
markets.active_mlb_markets_dataframe()
markets.get_market(ticker)
markets.get_historical_market(ticker)
markets.get_market_anywhere(ticker)
markets.market_summary_row(market)
markets.market_resolution_row(market)
```

Trading/account methods intended for reuse:

```python
trading.get_balance()
trading.get_order_history()
trading.get_fill_history()
trading.export_fill_history_csv()
trading.build_order(...)
trading.place_order(..., dry_run=True)
```

All live orders should go through `trading.place_order(..., dry_run=False)`,
which routes through the logged order path.

## Endpoint

```text
GET https://external-api.kalshi.com/trade-api/v2/markets?status=open&limit=1000
```

The response is cursor-paginated. `markets/mlb_markets.py` follows the cursor and filters markets whose ticker, event ticker, series ticker, title, subtitle, or rules mention MLB/baseball.

By default the helper passes `mve_filter=exclude` to avoid multivariate/combo markets. Use `--include-multivariate` if you want those included in the scan.

## Notebook

Open:

```text
kalshi/markets/test_mlb_markets.ipynb
```

Run the cells top to bottom to fetch active MLB markets and inspect the raw payload fields.

For a single historical/resolved market lookup, open:

```text
kalshi/markets/test_historical_market.ipynb
```

## CLI

```bash
python kalshi/markets/mlb_markets.py
```

Save a raw JSON payload and a compact CSV:

```bash
python kalshi/markets/mlb_markets.py \
  --json-path kalshi/markets/data/raw/active_mlb_markets.json \
  --csv-path kalshi/markets/data/active_mlb_markets.csv
```

Fetch one market by ticker and print its resolution fields:

```bash
python kalshi/markets/mlb_markets.py --ticker KXMLB-26-ATL
```

Use only the historical endpoint for settled markets:

```bash
python kalshi/markets/mlb_markets.py --ticker KXMLB-26-ATL --historical
```

Save one market payload:

```bash
python kalshi/markets/mlb_markets.py \
  --ticker KXMLB-26-ATL \
  --json-path kalshi/markets/data/historical/KXMLB-26-ATL.json
```

## Trading

Authenticated trading uses API key signing. Copy the example env file and fill
in your own values:

```bash
cp kalshi/.env.example .env
```

`trading/client.py` reads credentials with `os.getenv`, so your shell or editor
must load the env file into the process environment. In VS Code, set:

```json
{
  "python.terminal.useEnvFile": true,
  "python.envFile": "${workspaceFolder}/.env"
}
```

Keep `KALSHI_ALLOW_LIVE_TRADING=false` while testing. Dry-run an order payload:

```bash
python kalshi/trading/client.py place-order \
  --ticker KXMLB-26-ATL \
  --action buy \
  --side yes \
  --count 1 \
  --yes-price 1 \
  --strategy mlb1
```

Live orders are routed through `KalshiTradingClient.place_logged_order`, which
captures a market snapshot and appends accepted orders to:

```text
kalshi/trading/data/real_trade_log.csv
```

The log includes order timing, side, count, limit price, estimated amount, the
best bid/ask seen at placement, Kalshi's order response, and the normalized
market fields used in `kalshi/markets/data/active_mlb_markets.csv`. It also
includes a `strategy` column, so multiple systems can share the same log.

Fetch authenticated account info:

```bash
python kalshi/trading/client.py balance
python kalshi/trading/client.py orders --limit 20
```

Export your matched trade history. Kalshi calls matched trades "fills"; recent
fills come from `/portfolio/fills`, while older fills come from
`/historical/fills`, so the default command queries both and combines them:

```bash
python kalshi/trading/client.py fills
```

The default output is:

```text
kalshi/trading/data/fill_history.csv
```

Useful filters:

```bash
python kalshi/trading/client.py fills --ticker KXMLB-26-ATL
python kalshi/trading/client.py fills --live-only
python kalshi/trading/client.py fills --historical-only
```

To submit a live order, set `KALSHI_ALLOW_LIVE_TRADING=true` in `.env` and pass
`--live` to `place-order`. This double opt-in is intentional.
