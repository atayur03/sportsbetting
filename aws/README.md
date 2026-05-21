# AWS Infrastructure

AWS CDK infrastructure for the sports betting project.

This creates the S3 bucket used for private logs/status CSVs, the public
sanitized website JSON, and the Lambda entry points that replace the update CLI
commands.

## Layout

```text
s3://<bucket>/private/kalshi/trading/real_trade_log.csv
s3://<bucket>/private/execution/status/trade_status_YYYY-MM-DD.csv
s3://<bucket>/private/execution/simulations/kalshi/simulated_trade_log.csv
s3://<bucket>/private/execution/simulations/kalshi/trade_status_YYYY-MM-DD.csv
s3://<bucket>/public/data/trade-status.json
```

The bucket blocks public access. The website reads sanitized JSON through
`/api/status`, which calls the project `aws.read` API.

## Deploy

Use the repo-root `.env` for AWS/CDK values. Do not create a separate
`aws/.env`.

`aws/.env.example` is only a reference for the values that belong in the root
`.env`.

```bash
cd aws
npm install
npm run synth
npm run deploy
```

This app defines two stacks:

```text
SportsBettingStack
LambdaSportsBettingStack
```

`SportsBettingStack` owns the S3 bucket and IAM users/roles. `LambdaSportsBettingStack`
owns the Lambda entry points for the commands we previously ran locally.

To choose a stable bucket name:

```bash
SPORTSBETTING_S3_BUCKET=ashwintayur-sportsbetting npm run deploy
```

Or pass CDK context:

```bash
npm run deploy -- -c bucketName=ashwintayur-sportsbetting
```

The bucket name is not secret. It appears in the public JSON URL. Runtime code
can either read it from `SPORTSBETTING_S3_BUCKET` or discover it from the
deployed CloudFormation stack output named `BucketName`. The stack name defaults
to:

```text
SportsBettingStack
```

After deploy, configure Vercel with AWS runtime credentials and
`SPORTSBETTING_S3_BUCKET`. The website API route reads S3 through `aws.read`.

The stack defines a least-privilege IAM user for the website API:

```text
WebsiteStatusApiUser
```

That user can only read `public/data/trade-status.json`. Create an access key
for the output `WebsiteStatusApiUserName`, then add these values to Vercel:

```text
AWS_REGION=us-east-1
SPORTSBETTING_S3_BUCKET=ashwintayur-sportsbetting
AWS_ACCESS_KEY_ID=<WebsiteStatusApiUser access key>
AWS_SECRET_ACCESS_KEY=<WebsiteStatusApiUser secret key>
```

Do not use the broader local execution credentials for the website API.

## S3 File Helpers

The runtime S3 API intentionally exposes only two functions:

```python
from aws import read, write

write("website/public/data/trade-status.json", "public/data/trade-status.json")
read("website/public/data/trade-status.json", "public/data/trade-status.json")
```

Execution uses these helpers internally for project-managed artifacts. The
logical local paths still exist in code, but writes are redirected to the S3
keys shown in the layout above and cached under `.s3_cache/` while reading or
rewriting CSVs.

Install the Python dependency:

```bash
pip install -r aws/requirements.txt
```

`path` can be either a bucket-relative key:

```text
public/data/trade-status.json
```

or a full S3 URI:

```text
s3://ashwintayur-sportsbetting/public/data/trade-status.json
```

When using bucket-relative keys, the bucket can be supplied with:

```text
SPORTSBETTING_S3_BUCKET=ashwintayur-sportsbetting
```

or discovered from the deployed CloudFormation stack output:

```text
SPORTSBETTING_STACK_NAME=SportsBettingStack
```

The bucket name is not secret. The sensitive boundary is IAM access: browser
code does not call S3 directly.

Dashboard JSON is now published by `ExportStatusJsonFunction`, not by checking
`trade-status.json` into the repo.

## Lambda Commands

All update-style CLI commands have Lambda equivalents under `aws/lambdas/`.

### `RunStrategyFunction`

Runs one strategy over a daily, weekly, or date-range market window. This is the
Lambda version of `python -m execution.cli.run`. It can run in simulation mode
or live mode. Simulation assumes accepted actions fill successfully and writes
simulated logs/status files to S3. Live mode places real Kalshi orders and uses
Secrets Manager for Kalshi credentials.

```bash
aws lambda invoke \
  --function-name <RunStrategyFunctionName> \
  --payload '{"window":"daily","engine":"kalshi","strategy":"underdog","date":"2026-05-19","stake_cents":100,"max_order_stake_cents":100,"simulate":true}' \
  /tmp/run-strategy.json
```

Sample payloads:

```json
{
  "window": "daily",
  "engine": "kalshi",
  "strategy": "underdog",
  "date": "2026-05-19",
  "stake_cents": 100,
  "max_order_stake_cents": 100,
  "simulate": true
}
```

```json
{
  "window": "date-range",
  "engine": "kalshi",
  "strategy": "game_total_under",
  "start_date": "2026-05-19",
  "end_date": "2026-05-26",
  "stake_cents": 100,
  "max_order_stake_cents": 100,
  "simulate": true
}
```

```json
{
  "window": "daily",
  "engine": "kalshi",
  "strategy": "underdog",
  "inverted": true,
  "date": "2026-05-19",
  "stake_cents": 100,
  "max_order_stake_cents": 100,
  "live": true
}
```

### `RefreshTradeStatusFunction`

Updates date-scoped trade status CSVs from the real and simulated trade logs in
S3. This is the Lambda version of `python -m execution.cli.status --date ...`.
It checks open markets and marks rows as `open`, `won`, or `lost` when possible.

```bash
aws lambda invoke \
  --function-name <RefreshTradeStatusFunctionName> \
  --payload '{"date":"2026-05-19"}' \
  /tmp/status-refresh.json
```

Sample payload:

```json
{
  "date": "2026-05-19",
  "timezone": "America/New_York",
  "refresh_all": false,
  "market_lookup_timeout": 8,
  "market_lookup_retries": 1
}
```

### `ExportStatusJsonFunction`

Reads all real and simulated trade status CSVs from S3, strips private fields,
and writes the dashboard payload to `public/data/trade-status.json`. This is the
function the website reads through `/api/status`.

```bash
aws lambda invoke \
  --function-name <ExportStatusJsonFunctionName> \
  --payload '{}' \
  /tmp/status-export.json
```

Sample payload:

```json
{
  "output_key": "public/data/trade-status.json"
}
```

For live strategy runs, the Lambda stack creates a placeholder Secrets Manager
secret. The default name is:

```text
sportsbetting/kalshi
```

You can choose a different managed secret name during deploy:

```bash
npm run deploy -- -c kalshiSecretName=sportsbetting/kalshi
```

After deploy, open the output `KalshiCredentialsSecretName` in AWS Secrets
Manager and manually replace the placeholder JSON with:

```json
{
  "KALSHI_API_KEY_ID": "...",
  "KALSHI_PRIVATE_KEY_PEM": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n",
  "KALSHI_BASE_URL": "https://external-api.kalshi.com/trade-api/v2",
  "KALSHI_ALLOW_LIVE_TRADING": "true"
}
```

Then invoke with `"live": true` instead of `"simulate": true`.

Optional schedules can be created by deploying with:

```bash
npm run deploy -- -c enableSchedules=true
```

This creates two EventBridge schedules:

- `HourlyRollingStatusRefreshSchedule`: runs on the hour and invokes
  `RefreshTradeStatusFunction` three times, for today, yesterday, and two days
  ago in `America/New_York`.
- `HourlyStatusExportSchedule`: runs at 10 minutes past every hour and invokes
  `ExportStatusJsonFunction` with `public/data/trade-status.json`.

Lambda bundling uses the CDK Python 3.11 Docker image, so Docker needs to be
available when you synth/deploy `LambdaSportsBettingStack`.

Simulation, status, and export jobs do not need Kalshi trading credentials.
