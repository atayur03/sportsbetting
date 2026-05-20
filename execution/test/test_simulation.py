import csv

from execution import ExecutionConfig, ExecutionTarget
from execution.kalshi.engine import KalshiExecutionEngine
from kalshi.trading.client import TRADE_LOG_COLUMNS
from strategy import WagerAction


def test_simulation_writes_real_trade_log_schema(tmp_path, monkeypatch):
    def fake_get_market_anywhere(ticker, prefer_historical=False):
        return (
            {
                "ticker": ticker,
                "event_ticker": "KXMLB-26TEST",
                "status": "active",
                "title": "Test Team at Other Team",
                "subtitle": "Moneyline",
                "occurrence_datetime": "2026-05-17T23:00:00Z",
                "yes_ask_dollars": "0.4200",
                "no_ask_dollars": "0.5800",
            },
            "test",
        )

    monkeypatch.setattr("execution.kalshi.engine.get_market_anywhere", fake_get_market_anywhere)

    log_path = tmp_path / "simulated_trade_log.csv"
    engine = KalshiExecutionEngine(
        targets=[
            ExecutionTarget(
                line_id="mlb:2026-05-17:test:moneyline:underdog",
                venue="kalshi",
                venue_ticker="KXMLB-26TEST-YES",
            )
        ],
        config=ExecutionConfig(mode="simulation", max_order_stake_cents=100),
        simulation_trade_log_path=log_path,
    )
    action = WagerAction(
        line_id="mlb:2026-05-17:test:moneyline:underdog",
        action="buy",
        side="yes",
        limit_price_cents=42,
        stake_cents=100,
        strategy="underdog",
    )

    result = engine.execute_action(action, run_id="run-1", strategy_name="underdog")

    assert result.accepted
    assert result.mode == "simulation"
    assert result.log_path == str(log_path)
    with log_path.open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))

    assert rows
    assert list(rows[0].keys()) == TRADE_LOG_COLUMNS
    assert rows[0]["order_id"].startswith("sim-")
    assert rows[0]["order_status"] == "filled"
    assert rows[0]["strategy"] == "underdog"
