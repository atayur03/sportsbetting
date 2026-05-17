# ESPN MLB Scraper

This folder contains ESPN MLB scraping experiments and scripts.

## Endpoints

Game discovery uses ESPN's scoreboard endpoint:

```text
https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard?dates={YYYYMMDD}&limit=1000
```

The scoreboard response contains game/event IDs in `events[].id`.

Per-game raw data uses ESPN's summary endpoint:

```text
https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/summary?event={game_id}
```

## Script

```text
fetch_mlb_summaries.py
```

The script:

- scans scoreboard dates to discover MLB game IDs
- writes a game index CSV with game date, season, home team, away team, game ID, scores, and status
- saves one raw summary JSON gzip file per game

## Outputs

Raw summary JSON files:

```text
scrapers/espn/data/raw/espn/mlb/summary/{season}/{game_id}.json.gz
```

Game index:

```text
scrapers/espn/data/raw/espn/mlb/game_index.csv
```

Index columns:

```text
game_id
game_date
start_time_utc
season
season_type
status
completed
home_team_id
home_team
home_abbrev
away_team_id
away_team
away_abbrev
home_score
away_score
summary_path
```

`game_date` is the ESPN scoreboard date that produced the event. `start_time_utc` is ESPN's event timestamp. These can differ for late games because the event timestamp is in UTC.

## Usage

Discover games for a date range and write only the index:

```bash
python scrapers/espn/fetch_mlb_summaries.py --start-date 20260501 --end-date 20260507 --discover-only
```

Download summaries for a date range:

```bash
python scrapers/espn/fetch_mlb_summaries.py --start-date 20260501 --end-date 20260507
```

Download summaries with modest parallelism:

```bash
python scrapers/espn/fetch_mlb_summaries.py --start-date 20260501 --end-date 20260507 --workers 4
```

Download the last five seasons, based on the current year:

```bash
python scrapers/espn/fetch_mlb_summaries.py --last-seasons 5
```

Download explicit seasons:

```bash
python scrapers/espn/fetch_mlb_summaries.py --start-season 2022 --end-season 2026
```

By default, existing summary JSON files are not refetched. To refresh them:

```bash
python scrapers/espn/fetch_mlb_summaries.py --start-season 2022 --end-season 2026 --refresh
```

Use a small `--sleep` delay to be polite to ESPN:

```bash
python scrapers/espn/fetch_mlb_summaries.py --start-season 2022 --end-season 2026 --sleep 0.5
```

Use retries and a longer timeout for larger backfills:

```bash
python scrapers/espn/fetch_mlb_summaries.py --start-date 20220407 --end-date 20260516 --workers 4 --timeout 90 --retries 5
```

## Notes

The scoreboard endpoint can be queried by day. For multi-year backfills, this script intentionally scans one date at a time because it is simpler, reliable, and avoids depending on large range responses.

`--sleep` applies to scoreboard discovery requests. Summary downloads can be parallelized with `--workers`; keep this modest because ESPN can still rate limit or drop connections. Start with 2-4 workers for a large backfill.

Summary JSON gzip files are written to a temporary file first and then atomically renamed into place. If the process is interrupted, incomplete `.tmp-*` files can be deleted and the command can be rerun. Existing completed `.json.gz` files are skipped unless `--refresh` is passed.

The saved JSON files are the source of truth. Once a game summary is downloaded, downstream processing should read the local file instead of calling ESPN again.
