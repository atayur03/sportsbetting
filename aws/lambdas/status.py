"""Lambda wrapper for `python -m execution.cli.status` behavior."""

from __future__ import annotations

import datetime as dt
from typing import Any

from execution.cli.status import refresh_trade_status_csvs_for_date


def lambda_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    run_date = event.get("date") or dt.date.today().isoformat()
    outputs = refresh_trade_status_csvs_for_date(
        run_date=run_date,
        timezone=event.get("timezone", "America/New_York"),
        refresh_only_unresolved=not bool(event.get("refresh_all", False)),
        market_lookup_timeout=int(event.get("market_lookup_timeout", 8)),
        market_lookup_retries=int(event.get("market_lookup_retries", 1)),
    )
    return {"date": str(run_date), "outputs": outputs}

