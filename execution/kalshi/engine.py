"""Kalshi execution engine for strategy recommendations."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import TYPE_CHECKING

from kalshi.markets.mlb_markets import get_market_anywhere
from kalshi.trading.order_log import append_trade_log, build_order_payload, build_trade_log_row, utc_now_iso
from strategy import StrategyRun, WagerAction

from execution.core.spec import ExecutionConfig, ExecutionResult, ExecutionTarget

if TYPE_CHECKING:
    from kalshi import KalshiTrading


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SIMULATED_TRADE_LOG_PATH = (
    PROJECT_ROOT / "execution" / "data" / "simulations" / "kalshi" / "simulated_trade_log.csv"
)


class KalshiExecutionEngine:
    """Resolve strategy line IDs and route orders through KalshiTrading."""

    def __init__(
        self,
        targets: list[ExecutionTarget] | None = None,
        *,
        trading: "KalshiTrading | None" = None,
        config: ExecutionConfig | None = None,
        simulation_trade_log_path: Path = DEFAULT_SIMULATED_TRADE_LOG_PATH,
    ):
        self.trading = trading
        self.config = config or ExecutionConfig()
        self.simulation_trade_log_path = simulation_trade_log_path
        self.targets_by_line_id = {target.line_id: target for target in targets or []}

    def authenticated_trading(self) -> "KalshiTrading":
        """Return an authenticated trading client, loading env only when needed."""
        if self.trading is None:
            from kalshi import KalshiTrading

            self.trading = KalshiTrading.from_env()
        return self.trading

    def add_targets(self, targets: list[ExecutionTarget]) -> None:
        """Add or replace venue targets by `line_id`."""
        self.targets_by_line_id.update({target.line_id: target for target in targets})

    def resolve_target(self, line_id: str) -> ExecutionTarget:
        """Return the venue target for a strategy-facing line ID."""
        try:
            return self.targets_by_line_id[line_id]
        except KeyError as exc:
            raise ValueError(f"no execution target for line_id: {line_id}") from exc

    def execute_action(
        self,
        action: WagerAction,
        *,
        run_id: str,
        strategy_name: str,
    ) -> ExecutionResult:
        """Dry-run or place one recommendation.

        Returns one `ExecutionResult` row. Real orders still require both
        `ExecutionConfig(mode="live")` and `KALSHI_ALLOW_LIVE_TRADING=true`.
        """
        try:
            self.config.validate(action)
            target = self.resolve_target(action.line_id)
        except ValueError as exc:
            return ExecutionResult(
                run_id=run_id,
                strategy_name=strategy_name,
                recommendation=action.to_dict(),
                mode=self.config.mode,
                accepted=False,
                skipped=True,
                reason=str(exc),
            )

        order_kwargs = action.to_order_kwargs(ticker=target.venue_ticker)
        if self.config.dry_run:
            return ExecutionResult(
                run_id=run_id,
                strategy_name=strategy_name,
                recommendation=action.to_dict(),
                mode=self.config.mode,
                accepted=True,
                skipped=False,
                target=target.to_dict(),
                order={**order_kwargs, "dry_run": True},
                response={"dry_run": True},
            )

        if self.config.simulation:
            try:
                result = self.simulate_logged_order(action=action, target=target)
            except Exception as exc:
                return ExecutionResult(
                    run_id=run_id,
                    strategy_name=strategy_name,
                    recommendation=action.to_dict(),
                    mode=self.config.mode,
                    accepted=False,
                    skipped=False,
                    reason=f"simulation failed: {exc}",
                    target=target.to_dict(),
                )

            return ExecutionResult(
                run_id=run_id,
                strategy_name=strategy_name,
                recommendation=action.to_dict(),
                mode=self.config.mode,
                accepted=True,
                skipped=False,
                target=target.to_dict(),
                order=result.get("order"),
                response=result.get("response"),
                log_path=result.get("log_path"),
            )

        try:
            result = self.authenticated_trading().place_order(**order_kwargs, dry_run=False)
        except Exception as exc:
            return ExecutionResult(
                run_id=run_id,
                strategy_name=strategy_name,
                recommendation=action.to_dict(),
                mode=self.config.mode,
                accepted=False,
                skipped=False,
                reason=f"order failed: {exc}",
                target=target.to_dict(),
            )

        return ExecutionResult(
            run_id=run_id,
            strategy_name=strategy_name,
            recommendation=action.to_dict(),
            mode=self.config.mode,
            accepted=True,
            skipped=False,
            target=target.to_dict(),
            order=result.get("order"),
            response=result.get("response") or result.get("log_preview"),
            log_path=result.get("log_path"),
        )

    def simulate_logged_order(self, *, action: WagerAction, target: ExecutionTarget) -> dict[str, object]:
        """Append an assumed-filled order using the real trade-log schema."""
        order_kwargs = action.to_order_kwargs(ticker=target.venue_ticker)
        order = build_order_payload(
            ticker=str(order_kwargs["ticker"]),
            action=str(order_kwargs["action"]),
            side=str(order_kwargs["side"]),
            count=int(order_kwargs["count"]),
            order_type=str(order_kwargs.get("order_type") or "limit"),
            yes_price=order_kwargs.get("yes_price"),
            no_price=order_kwargs.get("no_price"),
            client_order_id=str(order_kwargs.get("client_order_id") or uuid.uuid4()),
        )
        simulated_order_id = f"sim-{uuid.uuid4()}"
        response = {
            "simulated": True,
            "assumed_filled": True,
            "order": {
                "order_id": simulated_order_id,
                "id": simulated_order_id,
                "status": "filled",
            },
        }
        market, market_source = get_market_anywhere(target.venue_ticker, prefer_historical=False)
        row = build_trade_log_row(
            placed_time_utc=utc_now_iso(),
            market=market,
            market_source=market_source,
            order=order,
            order_response=response,
            strategy=action.strategy,
        )
        log_destination = append_trade_log(self.simulation_trade_log_path, row)
        return {
            "simulated": True,
            "order": order,
            "response": response,
            "log_path": log_destination,
            "log_row": row,
        }

    def execute_run(self, run: StrategyRun) -> list[ExecutionResult]:
        """Execute every action in a strategy run and return result rows."""
        return [
            self.execute_action(action, run_id=run.run_id, strategy_name=run.strategy_name)
            for action in run.actions
        ]

    def execute_run_rows(self, run: StrategyRun) -> list[dict[str, object]]:
        """Execute a strategy run and return serializable result rows."""
        return [result.to_dict() for result in self.execute_run(run)]
