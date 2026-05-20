# Execution Status Website

React dashboard for viewing sanitized execution status files.

## Data

The app does not read the raw trade log or raw status CSVs directly. It fetches
sanitized status data from `/api/status`. That API route calls `from aws import
read`, so AWS access stays behind the project AWS module.

For local development, export a sanitized JSON file first:

```bash
cd website
npm run export-status
```

The exporter reads legacy local CSVs under `execution/data` and S3-backed CSVs
cached under `.s3_cache/private/execution`. When both exist for the same date,
the S3-backed cache wins.

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

For production, upload the sanitized JSON to S3 and set the AWS runtime
environment variables in Vercel, including `SPORTSBETTING_S3_BUCKET`,
`AWS_REGION`, `AWS_ACCESS_KEY_ID`, and `AWS_SECRET_ACCESS_KEY`.

Use the CDK-created `WebsiteStatusApiUser` credentials for Vercel. That user is
least-privilege and can only read `public/data/trade-status.json`.

With that set, the deployed site fetches `/api/status`; the API route reads the
latest S3 JSON through the `aws.read` API. No `trade-status.json` file needs to
be committed or deployed with the website.

To upload the sanitized JSON to S3:

```bash
python -c "from aws import write; print(write('website/public/data/trade-status.json', 'public/data/trade-status.json'))"
```

## Run

```bash
cd website
npm install
npm run dev
```

`npm run dev` runs the Vite client and a local `/api/status` middleware. The
middleware shells out to `python -m api.status`, which calls `from aws import
read`, so local AWS access still goes through the project AWS module.

Open the URL printed by Vite, usually:

```text
http://localhost:5173
```

Use this local Vite path for development. `npx vercel dev` can route the app
through Vercel's static-build adapter and may serve `index.html` through Vite's
module transform path, which produces an invalid-JS parse error.

Deploy Vercel from the repo root when possible so `api/status.py`,
`requirements.txt`, and the `aws` Python module are included. If the Vercel
project is already rooted at `website/`, `website/api/status.py` wraps the same
root API handler and imports the root `aws` module.

Both the repo root and `website/` have explicit `vercel.json` files so
`/api/status` is served by `@vercel/python` instead of falling through to Vite.
For production, prefer repo-root deployment; a website-rooted deployment will
not include the root `aws` Python module unless Vercel is configured to include
the full repository.

The filters above the chart apply to the summary, graph, and table. Strategy,
sport, and status filters support include and exclude selections, so a view can
include MLB while excluding another league when more sports are present.

The first chart shows cumulative closed-bet P&L overall and by strategy. The
table underneath shows sanitized status rows with pagination, column visibility
controls, click-to-sort headers, and draggable column resize handles.
