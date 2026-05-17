# ESPN MLB Summary Raw JSON

This folder stores raw ESPN MLB game summary payloads, one gzipped JSON file per game.

## Source

Endpoint pattern:

```text
https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/summary?event={game_id}
```

Example:

```text
https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/summary?event=401815350
```

## File Layout

```text
data/raw/espn/mlb/summary/{season}/{game_id}.json.gz
```

Example:

```text
data/raw/espn/mlb/summary/2026/401815350.json.gz
```

Each file is a downloaded snapshot of the ESPN API response for one game. After a game file is saved, local processing should read this file instead of calling ESPN again. Call the API again only to fetch a new game, refresh a corrected game, or backfill more games.

## Top-Level Schema

Observed top-level keys for `401815350.json`:

| Key | Type | Meaning |
| --- | --- | --- |
| `header` | dict | Game identity: event id, league, season, week, competitors, score, status, links. |
| `boxscore` | dict | Main box score data, split into `players` and `teams`. |
| `plays` | list | Play-by-play events. For this game: 722 items. |
| `playsMap` | dict | Play lookup map keyed by ESPN play id. |
| `atBats` | dict | MLB-specific plate appearance data keyed by ESPN at-bat id. |
| `winprobability` | list | ESPN win probability timeline. For this game: 91 items. |
| `rosters` | list | Game roster data for both teams. |
| `injuries` | list | Injury context for both teams. |
| `odds` | list | Odds records when available. Empty for this saved game. |
| `pickcenter` | list | ESPN betting/pickcenter context when available. |
| `againstTheSpread` | list | Against-the-spread records by team. |
| `gameInfo` | dict | Venue, attendance, game duration, officials. |
| `broadcasts` | list | Broadcast metadata. |
| `format` | dict | Game format, such as regulation length. |
| `seasonseries` | list | Season-series context between the teams. |
| `standings` | dict | Standings context included by ESPN. |
| `news` | dict | ESPN article objects attached to the game. |
| `videos` | list | ESPN video objects attached to the game. Empty for this saved game. |
| `notes` | list | ESPN notes. Empty for this saved game. |
| `meta` | dict | ESPN internal metadata: game state, sync URL, timestamps, topics. |
| `wallclockAvailable` | bool | Whether wall-clock timing data is available. |

## Box Score Schema

`boxscore` has two main children:

```text
boxscore
├── teams
└── players
```

### `boxscore.teams`

Team-level box score stats. Each team entry contains:

- `team`: team identity and display info.
- `statistics`: stat groups such as batting, pitching, fielding, and records.

The notebook flattens this into `team_stats_df` with columns like:

```text
team_id
team
abbrev
stat_group
stat_group_label
stat_name
stat_label
value
```

### `boxscore.players`

Player-level box score stats by team. Each team entry contains:

- `team`: team identity and display info.
- `statistics`: player stat groups.

For MLB, ESPN does not always label player stat groups clearly. The notebook infers:

- `batting` from labels such as `H-AB`, `AB`, `RBI`, `SLG`.
- `pitching` from labels such as `IP`, `ER`, `PC-ST`, `ERA`.

The notebook flattens this into `player_boxscore_df` with columns like:

```text
team_id
team
abbrev
stat_group
athlete_id
athlete
position
H-AB
AB
R
H
RBI
HR
BB
K
#P
AVG
OBP
SLG
IP
ER
PC-ST
ERA
PC
```

Batting and pitching views can be filtered from `player_boxscore_df`.

## Play Data

### `plays`

Ordered play-by-play event list. Observed fields include:

```text
id
atBatId
sequenceNumber
period
text
type
team
awayScore
homeScore
outs
pitchCount
resultCount
scoreValue
scoringPlay
summaryType
wallclock
```

Use this for full game event flow.

### `atBats`

Dictionary keyed by ESPN at-bat id. This is baseball-specific and groups pitch/play activity by plate appearance. Use this when plate appearances are more useful than individual play events.

### `playsMap`

Dictionary keyed by ESPN play id. This is useful for direct lookup but is usually less convenient for tabular analysis than `plays`.

## Context Sections

`rosters`, `injuries`, `gameInfo`, `broadcasts`, `format`, `seasonseries`, `standings`, and `meta` provide context around the game rather than box score lines.

`news`, `videos`, and `notes` are ESPN editorial/media sections. They may be empty or change independently from the game stats.

`odds`, `pickcenter`, and `againstTheSpread` provide betting context when ESPN includes it. These sections may be sparse or empty.

## Recommended Processing

Keep the raw JSON file intact as the source of truth. Build analysis tables from it later, for example:

```text
games
team_stats
player_boxscores
batting
pitching
plays
at_bats
winprobability
odds
```

For local processing:

```python
import gzip
import json
from pathlib import Path

path = Path("data/raw/espn/mlb/summary/2026/401815350.json.gz")
with gzip.open(path, "rt", encoding="utf-8") as file:
    data = json.load(file)
```

Then pass `data` into the notebook's flattening functions.
