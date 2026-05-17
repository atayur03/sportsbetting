#!/usr/bin/env python3
"""Fetch ESPN MLB game summary JSON files and maintain a game index."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = BASE_DIR / "data"

SPORT = "baseball"
LEAGUE = "mlb"
API_BASE = f"https://site.api.espn.com/apis/site/v2/sports/{SPORT}/{LEAGUE}"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
    ),
    "Accept": "application/json,text/plain,*/*",
}


@dataclass(frozen=True)
class GameIndexRow:
    game_id: str
    game_date: str
    start_time_utc: str
    season: str
    season_type: str
    status: str
    completed: str
    home_team_id: str
    home_team: str
    home_abbrev: str
    away_team_id: str
    away_team: str
    away_abbrev: str
    home_score: str
    away_score: str
    summary_path: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Discover ESPN MLB game IDs from scoreboard dates, save one summary "
            "JSON per game, and write a game index CSV."
        )
    )
    parser.add_argument(
        "--start-date",
        help="First scoreboard date to scan, in YYYYMMDD format.",
    )
    parser.add_argument(
        "--end-date",
        help="Last scoreboard date to scan, in YYYYMMDD format.",
    )
    parser.add_argument(
        "--start-season",
        type=int,
        help="First MLB season to scan. Used only if --start-date is omitted.",
    )
    parser.add_argument(
        "--end-season",
        type=int,
        help="Last MLB season to scan. Used only if --end-date is omitted.",
    )
    parser.add_argument(
        "--last-seasons",
        type=int,
        default=5,
        help="Number of seasons to scan when explicit dates/seasons are omitted.",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help="Root data directory. Defaults to scrapers/espn/data.",
    )
    parser.add_argument(
        "--index-path",
        type=Path,
        help="Output CSV path for the game index. Defaults under --data-dir.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=1000,
        help="Scoreboard event limit per day.",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.2,
        help="Seconds to sleep between scoreboard API requests.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Concurrent workers for summary downloads. Keep this modest; 1 is safest.",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=3,
        help="Attempts per API request before giving up.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="Read timeout in seconds for each API request.",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Refetch summary JSON files even when they already exist locally.",
    )
    parser.add_argument(
        "--discover-only",
        action="store_true",
        help="Only write the game index; do not download summary JSON files.",
    )
    return parser.parse_args()


def request_json(url: str, *, timeout: int = 60, retries: int = 3) -> dict[str, Any]:
    last_error: Exception | None = None

    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, headers=HEADERS, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            last_error = exc
            if attempt == retries:
                break

            delay = min(2 ** (attempt - 1), 10)
            print(f"request failed, retrying in {delay}s ({attempt}/{retries}): {url} [{exc}]")
            time.sleep(delay)

    assert last_error is not None
    raise last_error


def yyyymmdd(value: date) -> str:
    return value.strftime("%Y%m%d")


def parse_yyyymmdd(value: str) -> date:
    return datetime.strptime(value, "%Y%m%d").date()


def iter_dates(start: date, end: date):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def default_date_window(args: argparse.Namespace) -> tuple[date, date]:
    today = date.today()

    if args.start_date or args.end_date:
        start = parse_yyyymmdd(args.start_date) if args.start_date else date(today.year, 1, 1)
        end = parse_yyyymmdd(args.end_date) if args.end_date else today
        return start, end

    end_season = args.end_season or today.year
    start_season = args.start_season or (end_season - args.last_seasons + 1)
    return date(start_season, 1, 1), date(end_season, 12, 31)


def scoreboard_url(scoreboard_date: date, limit: int) -> str:
    query = urlencode({"dates": yyyymmdd(scoreboard_date), "limit": limit})
    return f"{API_BASE}/scoreboard?{query}"


def summary_url(game_id: str) -> str:
    query = urlencode({"event": game_id})
    return f"{API_BASE}/summary?{query}"


def event_competitors(event: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    competition = (event.get("competitions") or [{}])[0]
    competitors = competition.get("competitors") or []

    home = next((item for item in competitors if item.get("homeAway") == "home"), {})
    away = next((item for item in competitors if item.get("homeAway") == "away"), {})
    return home, away


def season_from_event(event: dict[str, Any]) -> str:
    season = event.get("season") or {}
    year = season.get("year")
    return str(year) if year is not None else ""


def season_type_from_event(event: dict[str, Any]) -> str:
    season = event.get("season") or {}
    season_type = season.get("type")
    return str(season_type) if season_type is not None else ""


def event_date(event: dict[str, Any]) -> str:
    value = event.get("date") or ""
    return value[:10] if value else ""


def event_start_time_utc(event: dict[str, Any]) -> str:
    return str(event.get("date") or "")


def scoreboard_date_from_event(event: dict[str, Any]) -> str:
    value = str(event.get("_scoreboard_date") or "")
    if len(value) == 8:
        return f"{value[:4]}-{value[4:6]}-{value[6:8]}"
    return event_date(event)


def team_field(competitor: dict[str, Any], key: str) -> str:
    value = (competitor.get("team") or {}).get(key)
    return str(value) if value is not None else ""


def score_field(competitor: dict[str, Any]) -> str:
    score = competitor.get("score")
    return str(score) if score is not None else ""


def row_from_event(event: dict[str, Any], summary_path: Path | None, data_dir: Path) -> GameIndexRow:
    home, away = event_competitors(event)
    status_type = ((event.get("status") or {}).get("type") or {})
    relative_summary_path = str(summary_path.relative_to(data_dir)) if summary_path else ""

    return GameIndexRow(
        game_id=str(event.get("id") or ""),
        game_date=scoreboard_date_from_event(event),
        start_time_utc=event_start_time_utc(event),
        season=season_from_event(event),
        season_type=season_type_from_event(event),
        status=str(status_type.get("description") or ""),
        completed=str(status_type.get("completed") if status_type.get("completed") is not None else ""),
        home_team_id=team_field(home, "id"),
        home_team=team_field(home, "displayName"),
        home_abbrev=team_field(home, "abbreviation"),
        away_team_id=team_field(away, "id"),
        away_team=team_field(away, "displayName"),
        away_abbrev=team_field(away, "abbreviation"),
        home_score=score_field(home),
        away_score=score_field(away),
        summary_path=relative_summary_path,
    )


def summary_path(data_dir: Path, season: str, game_id: str) -> Path:
    season_dir = season or "unknown_season"
    return data_dir / "raw" / "espn" / "mlb" / "summary" / season_dir / f"{game_id}.json.gz"


def write_json_gz(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.tmp-{os.getpid()}")

    with gzip.open(tmp_path, "wt", encoding="utf-8") as file:
        json.dump(payload, file, sort_keys=True, separators=(",", ":"))

    tmp_path.replace(path)


def write_index(path: Path, rows: list[GameIndexRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    rows = sorted(rows, key=lambda row: (row.game_date, row.game_id))
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(GameIndexRow.__dataclass_fields__.keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(row.__dict__)


def discover_events(
    start: date,
    end: date,
    limit: int,
    sleep_seconds: float,
    timeout: int,
    retries: int,
) -> dict[str, dict[str, Any]]:
    events_by_id: dict[str, dict[str, Any]] = {}

    for scoreboard_date in iter_dates(start, end):
        url = scoreboard_url(scoreboard_date, limit)
        payload = request_json(url, timeout=timeout, retries=retries)
        events = payload.get("events") or []

        if events:
            print(f"{yyyymmdd(scoreboard_date)}: discovered {len(events)} games")

        for event in events:
            game_id = str(event.get("id") or "")
            if game_id:
                event = dict(event)
                event["_scoreboard_date"] = yyyymmdd(scoreboard_date)
                events_by_id[game_id] = event

        time.sleep(sleep_seconds)

    return events_by_id


def fetch_summaries(
    events_by_id: dict[str, dict[str, Any]],
    data_dir: Path,
    workers: int,
    timeout: int,
    retries: int,
    refresh: bool,
    discover_only: bool,
) -> list[GameIndexRow]:
    rows: list[GameIndexRow] = []
    jobs: list[tuple[str, dict[str, Any], Path]] = []

    for game_id, event in sorted(events_by_id.items(), key=lambda item: (event_date(item[1]), item[0])):
        season = season_from_event(event) or event_date(event)[:4]
        path = summary_path(data_dir, season, game_id)

        if discover_only:
            rows.append(row_from_event(event, path, data_dir))
            continue

        if path.exists() and not refresh:
            print(f"{game_id}: exists, skipping")
        else:
            jobs.append((game_id, event, path))

        rows.append(row_from_event(event, path, data_dir))

    if jobs:
        print(f"Downloading {len(jobs)} summaries with {workers} worker(s)")

    def download_one(job: tuple[str, dict[str, Any], Path]) -> tuple[str, Path]:
        game_id, _event, path = job
        payload = request_json(summary_url(game_id), timeout=timeout, retries=retries)
        write_json_gz(path, payload)
        return game_id, path

    failures: list[tuple[str, str]] = []

    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {executor.submit(download_one, job): job[0] for job in jobs}
        for future in as_completed(futures):
            game_id_for_failure = futures[future]
            try:
                game_id, path = future.result()
                print(f"{game_id}: saved {path}")
            except Exception as exc:
                failures.append((game_id_for_failure, repr(exc)))
                print(f"{game_id_for_failure}: failed after retries: {exc}")

    if failures:
        print(f"Failed to download {len(failures)} summaries. Rerun the same command to retry missing files.")

    return rows


def main() -> None:
    args = parse_args()
    start, end = default_date_window(args)

    data_dir = args.data_dir.resolve()
    index_path = args.index_path or (data_dir / "raw" / "espn" / "mlb" / "game_index.csv")

    print(f"Scanning ESPN MLB scoreboard dates {yyyymmdd(start)} through {yyyymmdd(end)}")
    events_by_id = discover_events(start, end, args.limit, args.sleep, args.timeout, args.retries)
    print(f"Discovered {len(events_by_id)} unique games")

    rows = fetch_summaries(
        events_by_id=events_by_id,
        data_dir=data_dir,
        workers=args.workers,
        timeout=args.timeout,
        retries=args.retries,
        refresh=args.refresh,
        discover_only=args.discover_only,
    )
    write_index(index_path, rows)
    print(f"Wrote index: {index_path}")


if __name__ == "__main__":
    main()
