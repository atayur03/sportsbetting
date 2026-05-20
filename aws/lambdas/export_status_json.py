"""Export sanitized status JSON from S3-backed status CSVs."""

from __future__ import annotations

import csv
import datetime as dt
import json
import tempfile
from pathlib import Path
from typing import Any

from aws import read, write
from aws.helpers.s3_storage import list_keys


STATUS_PREFIXES = [
    ("private/execution/status/", False),
    ("private/execution/simulations/kalshi/", True),
]
OUTPUT_KEY = "public/data/trade-status.json"
SAFE_FIELDS = [
    "id",
    "gameDate",
    "settledAt",
    "checkedDate",
    "engine",
    "simulated",
    "status",
    "strategy",
    "sport",
    "side",
    "contracts",
    "priceDollars",
    "stakeDollars",
    "payoutDollars",
    "pnlDollars",
    "marketTitle",
    "marketSubtitle",
    "marketResult",
    "marketStatus",
]


def lambda_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    payload = export_status_payload()
    with tempfile.TemporaryDirectory() as temp_dir:
        local_file = Path(temp_dir) / "trade-status.json"
        local_file.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        destination = write(local_file, event.get("output_key", OUTPUT_KEY))
    return {"rows": len(payload["bets"]), "output": destination, "generatedAt": payload["generatedAt"]}


def export_status_payload() -> dict[str, Any]:
    bets: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)
        for prefix, simulated in STATUS_PREFIXES:
            for key in sorted(list_keys(prefix)):
                if not Path(key).name.startswith("trade_status_") or not key.endswith(".csv"):
                    continue
                local_file = temp_root / key.replace("/", "_")
                read(local_file, key)
                with local_file.open(newline="", encoding="utf-8") as file:
                    for row in csv.DictReader(file):
                        bets.append(sanitized_bet(row, len(bets), simulated))
    return {"generatedAt": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"), "bets": bets}


def sanitized_bet(row: dict[str, str], index: int, simulated: bool) -> dict[str, Any]:
    status = (row.get("trade_status") or "unknown").lower()
    contracts = number_value(row.get("count"))
    price_dollars = number_value(row.get("price_at_placement_dollars") or row.get("limit_price_dollars"))
    stake_dollars = number_value(row.get("amount_dollars")) or contracts * price_dollars
    payout_dollars = contracts if status == "won" else 0
    pnl_dollars = payout_dollars - stake_dollars if status in {"won", "lost"} else 0
    record = {
        "id": f"{date_only(row.get('occurrence_datetime'))}-{index}",
        "gameDate": date_only(row.get("occurrence_datetime") or row.get("expected_expiration_time")),
        "settledAt": row.get("settlement_ts") or row.get("expiration_time") or row.get("expected_expiration_time") or row.get("close_time") or "",
        "checkedDate": date_only(row.get("checked_time_utc")),
        "engine": row.get("engine") or "kalshi",
        "simulated": simulated,
        "status": status,
        "strategy": row.get("strategy") or "unknown",
        "sport": row.get("sports_league") or "",
        "side": row.get("side") or "",
        "contracts": contracts,
        "priceDollars": price_dollars,
        "stakeDollars": stake_dollars,
        "payoutDollars": payout_dollars,
        "pnlDollars": pnl_dollars,
        "marketTitle": row.get("title") or "",
        "marketSubtitle": row.get("subtitle") or row.get("yes_sub_title") or row.get("no_sub_title") or "",
        "marketResult": row.get("market_result") or row.get("expiration_value") or ("open" if status == "open" else ""),
        "marketStatus": row.get("market_status") or "",
    }
    return {field: record[field] for field in SAFE_FIELDS}


def date_only(value: str | None) -> str:
    return str(value or "")[:10]


def number_value(value: str | None) -> float:
    try:
        return float(value or 0)
    except ValueError:
        return 0

