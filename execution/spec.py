"""Specs for resolving strategy actions into venue-specific execution."""

from __future__ import annotations

import datetime as dt
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from strategy import WagerAction


ExecutionMode = Literal["dry_run", "simulation", "live"]
Venue = Literal["kalshi"]
Engine = Literal["kalshi"]


def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class ExecutionTarget:
    """Venue-specific tradable target hidden from strategy code.

    `line_id` is the normalized strategy-facing ID. `venue_ticker` is the
    exchange-facing identifier execution uses when placing an order.
    """

    line_id: str
    venue: Venue
    venue_ticker: str
    event_ticker: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.line_id:
            raise ValueError("line_id is required")
        if self.venue != "kalshi":
            raise ValueError("only kalshi execution targets are supported for now")
        if not self.venue_ticker:
            raise ValueError("venue_ticker is required")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExecutionConfig:
    """Guardrails applied before an order reaches a venue.

    Returned shape: serializable dict via `to_dict()`.
    """

    mode: ExecutionMode = "dry_run"
    max_order_stake_cents: int = 100
    allowed_strategies: set[str] | None = None

    def __post_init__(self) -> None:
        if self.mode not in {"dry_run", "simulation", "live"}:
            raise ValueError("mode must be 'dry_run', 'simulation', or 'live'")
        if self.max_order_stake_cents <= 0:
            raise ValueError("max_order_stake_cents must be positive")

    @property
    def dry_run(self) -> bool:
        return self.mode == "dry_run"

    @property
    def simulation(self) -> bool:
        return self.mode == "simulation"

    def validate(self, action: WagerAction) -> None:
        if self.allowed_strategies is not None and action.strategy not in self.allowed_strategies:
            raise ValueError(f"strategy is not allowed: {action.strategy}")
        if action.estimated_cost_cents > self.max_order_stake_cents:
            raise ValueError(
                "estimated order cost exceeds max_order_stake_cents: "
                f"{action.estimated_cost_cents} > {self.max_order_stake_cents}"
            )

    def to_dict(self) -> dict[str, Any]:
        row = asdict(self)
        if self.allowed_strategies is not None:
            row["allowed_strategies"] = sorted(self.allowed_strategies)
        return row


@dataclass(frozen=True)
class ExecutionResult:
    """Result row for one strategy action consumed by execution.

    Returned shape: serializable dict via `to_dict()`.
    """

    run_id: str
    strategy_name: str
    recommendation: dict[str, Any]
    mode: ExecutionMode
    accepted: bool
    skipped: bool
    reason: str = ""
    target: dict[str, Any] | None = None
    order: dict[str, Any] | None = None
    response: dict[str, Any] | None = None
    log_path: str | None = None
    executed_at_utc: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
