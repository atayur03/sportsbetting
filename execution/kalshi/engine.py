"""Kalshi execution engine for strategy recommendations."""

from __future__ import annotations

from kalshi import KalshiTrading
from strategy import StrategyRun, WagerAction

from execution.spec import ExecutionConfig, ExecutionResult, ExecutionTarget


class KalshiExecutionEngine:
    """Resolve strategy line IDs and route orders through KalshiTrading."""

    def __init__(
        self,
        targets: list[ExecutionTarget] | None = None,
        *,
        trading: KalshiTrading | None = None,
        config: ExecutionConfig | None = None,
    ):
        self.trading = trading
        self.config = config or ExecutionConfig()
        self.targets_by_line_id = {target.line_id: target for target in targets or []}

    def authenticated_trading(self) -> KalshiTrading:
        """Return an authenticated trading client, loading env only when needed."""
        if self.trading is None:
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

    def execute_run(self, run: StrategyRun) -> list[ExecutionResult]:
        """Execute every action in a strategy run and return result rows."""
        return [
            self.execute_action(action, run_id=run.run_id, strategy_name=run.strategy_name)
            for action in run.actions
        ]

    def execute_run_rows(self, run: StrategyRun) -> list[dict[str, object]]:
        """Execute a strategy run and return serializable result rows."""
        return [result.to_dict() for result in self.execute_run(run)]
