import json

from execution.cli.status import build_status_row, build_trade_status_rows, merge_order_updates


def base_resting_order_row():
    return {
        "strategy": "test",
        "placed_time_utc": "2026-05-20T00:00:00Z",
        "ticker": "KXMLBGAME-X",
        "event_ticker": "KXMLBGAME-X",
        "order_id": "order-1",
        "client_order_id": "client-1",
        "order_status": "resting",
        "action": "buy",
        "side": "no",
        "count": "7",
        "limit_price_cents": "65",
        "limit_price_dollars": "0.6500",
        "amount_dollars": "4.5500",
        "order_response": json.dumps(
            {
                "order": {
                    "status": "resting",
                    "initial_count_fp": "7.00",
                    "fill_count_fp": "0.00",
                    "remaining_count_fp": "7.00",
                }
            }
        ),
    }


def status_for(row):
    return build_status_row(
        row,
        market={"status": "active", "title": "Game"},
        market_lookup_source="live",
        checked_time_utc="2026-05-20T01:00:00Z",
    )


class StaticMarkets:
    def get_market_anywhere(self, *_args, **_kwargs):
        return {"status": "active", "title": "Game"}, "test"


class FailingOrderUpdates:
    def order_for_id(self, _order_id):
        raise RuntimeError("kalshi auth failed")

    def fills_for_order_id(self, _order_id):
        raise RuntimeError("kalshi auth failed")


def test_resting_order_with_no_fills_is_unfilled():
    row = status_for(base_resting_order_row())

    assert row["trade_status"] == "unfilled"
    assert row["fill_status"] == "unfilled"
    assert row["position_status"] == "none"
    assert row["filled_count"] == "0"
    assert row["remaining_count"] == "7"
    assert row["filled_cost_dollars"] == "0.0000"


def test_later_fill_rehydrates_contracts_and_stake():
    row = merge_order_updates(
        base_resting_order_row(),
        current_order={},
        fills=[
            {
                "count_fp": "7.00",
                "no_price_dollars": "0.6500",
                "created_time": "2026-05-20T01:00:00Z",
            }
        ],
    )
    status = status_for(row)

    assert status["trade_status"] == "open"
    assert status["order_lifecycle_status"] == "filled"
    assert status["fill_status"] == "filled"
    assert status["position_status"] == "open"
    assert status["filled_count"] == "7"
    assert status["remaining_count"] == "0"
    assert status["filled_cost_dollars"] == "4.5500"
    assert status["avg_fill_price_dollars"] == "0.6500"


def test_duplicate_live_and_historical_fill_is_counted_once():
    row = merge_order_updates(
        base_resting_order_row(),
        current_order={},
        fills=[
            {
                "fill_id": "fill-1",
                "source": "live",
                "count_fp": "1.00",
                "no_price_dollars": "0.8000",
                "created_time": "2026-05-20T01:00:00Z",
            },
            {
                "fill_id": "different-endpoint-id",
                "source": "historical",
                "count_fp": "1.00",
                "no_price_dollars": "0.8000",
                "created_time": "2026-05-20T01:00:00Z",
            },
        ],
    )
    status = status_for(row)

    assert status["filled_count"] == "1"
    assert status["remaining_count"] == "6"
    assert status["filled_cost_dollars"] == "0.8000"
    assert status["avg_fill_price_dollars"] == "0.8000"


def test_maker_fill_replaces_existing_maker_cost_without_double_counting():
    row = merge_order_updates(
        base_resting_order_row(),
        current_order={
            "maker_fill_cost_dollars": "0.800000",
            "taker_fill_cost_dollars": "0.000000",
        },
        fills=[
            {
                "fill_id": "maker-fill-1",
                "count_fp": "1.00",
                "no_price_dollars": "0.8000",
                "is_taker": False,
                "created_time": "2026-05-20T01:00:00Z",
            },
        ],
    )
    status = status_for(row)

    assert status["filled_count"] == "1"
    assert status["filled_cost_dollars"] == "0.8000"
    assert status["avg_fill_price_dollars"] == "0.8000"


def test_taker_fill_replaces_existing_taker_cost_without_double_counting():
    row = merge_order_updates(
        base_resting_order_row(),
        current_order={
            "maker_fill_cost_dollars": "0.000000",
            "taker_fill_cost_dollars": "0.800000",
        },
        fills=[
            {
                "fill_id": "taker-fill-1",
                "count_fp": "1.00",
                "no_price_dollars": "0.8000",
                "is_taker": True,
                "created_time": "2026-05-20T01:00:00Z",
            },
        ],
    )
    status = status_for(row)

    assert status["filled_count"] == "1"
    assert status["filled_cost_dollars"] == "0.8000"
    assert status["avg_fill_price_dollars"] == "0.8000"


def test_partial_fill_rehydrates_partial_order():
    row = merge_order_updates(
        base_resting_order_row(),
        current_order={},
        fills=[
            {
                "count_fp": "3.00",
                "no_price_dollars": "0.6500",
                "created_time": "2026-05-20T01:00:00Z",
            }
        ],
    )
    status = status_for(row)

    assert status["trade_status"] == "partial_order"
    assert status["order_lifecycle_status"] == "partially_filled"
    assert status["fill_status"] == "partial"
    assert status["position_status"] == "open"
    assert status["filled_count"] == "3"
    assert status["remaining_count"] == "4"
    assert status["filled_cost_dollars"] == "1.9500"


def test_order_update_failure_preserves_existing_status_row():
    filled_row = status_for(
        merge_order_updates(
            base_resting_order_row(),
            current_order={},
            fills=[
                {
                    "count_fp": "7.00",
                    "no_price_dollars": "0.6500",
                    "created_time": "2026-05-20T01:00:00Z",
                }
            ],
        )
    )

    rows = build_trade_status_rows(
        [base_resting_order_row()],
        markets=StaticMarkets(),
        existing_status_rows=[filled_row],
        refresh_only_unresolved=False,
        order_updates=FailingOrderUpdates(),
        checked_time_utc="2026-05-20T02:00:00Z",
    )

    assert rows[0]["trade_status"] == "open"
    assert rows[0]["fill_status"] == "filled"
    assert rows[0]["filled_count"] == "7"
    assert rows[0]["filled_cost_dollars"] == "4.5500"
