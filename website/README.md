# Execution Status Website

React dashboard for viewing sanitized execution status files.

## Data

The app does not read the raw trade log or raw status CSVs directly. Export a
sanitized JSON file first:

```bash
cd website
npm run export-status
```

This reads:

```text
../execution/data/trade_status_YYYY-MM-DD.csv
```

and writes:

```text
public/data/trade-status.json
```

The exported JSON excludes tickers, event tickers, order IDs, client order IDs,
raw rule text, and raw order responses.

## Run

```bash
cd website
npm install
npm run export-status
npm run dev
```

The filters above the chart apply to the summary, graph, and table. The first
chart shows cumulative closed-bet P&L overall and by strategy. The table
underneath shows sanitized status rows and supports click-to-sort column
headers.
