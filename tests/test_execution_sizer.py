from __future__ import annotations

from src.execution.models import ExecutionReason, ExecutionStatus
from src.execution.sizer import size_add, size_new_buy
from src.strategy.signals import compute_lot_aware_order


def test_new_buy_generates_minimum_round_lot_order() -> None:
    result = size_new_buy(
        symbol="600000.sh",
        price=20.0,
        account_equity=50_000,
        available_cash=50_000,
        min_trade_value=1_500,
        round_lot=100,
        max_single_stock_weight=0.12,
        target_position_value=1_500,
    )

    assert result["execution_status"] == ExecutionStatus.EXECUTABLE
    assert result["execution_reason"] == ExecutionReason.EXECUTABLE
    assert result["executable_shares"] == 100
    assert result["executable_amount"] == 2_000


def test_new_buy_blocks_when_one_lot_exceeds_single_name_limit() -> None:
    result = size_new_buy(
        symbol="600309.sh",
        price=82.0,
        account_equity=50_000,
        available_cash=50_000,
        min_trade_value=1_500,
        round_lot=100,
        max_single_stock_weight=0.12,
        target_position_value=6_000,
    )

    assert result["execution_status"] == ExecutionStatus.BLOCKED
    assert result["execution_reason"] == ExecutionReason.BLOCK_PRICE_TOO_HIGH_FOR_ACCOUNT_LOT
    assert result["block_reason"] == "PRICE_TOO_HIGH_FOR_ACCOUNT_LOT"


def test_new_buy_cash_shortfall_is_pending_not_blocked() -> None:
    result = size_new_buy(
        symbol="600000.sh",
        price=20.0,
        account_equity=50_000,
        available_cash=1_500,
        min_trade_value=1_500,
        round_lot=100,
        max_single_stock_weight=0.12,
        target_position_value=6_000,
    )

    assert result["execution_status"] == ExecutionStatus.PENDING
    assert result["execution_reason"] == ExecutionReason.PENDING_CASH_INSUFFICIENT_FOR_ONE_LOT
    assert result["block_reason"] == ""
    assert result["execution_ineligible_reason"] == "CASH_INSUFFICIENT_FOR_ONE_LOT"


def test_add_pending_when_remaining_capacity_below_one_lot() -> None:
    result = size_add(
        symbol="600000.sh",
        price=20.0,
        current_position_shares=250,
        current_position_value=5_000,
        account_equity=50_000,
        available_cash=20_000,
        min_trade_value=1_500,
        round_lot=100,
        max_single_stock_weight=0.12,
        target_position_value=6_000,
        intended_order_value=1_000,
    )

    assert result["execution_status"] == ExecutionStatus.PENDING
    assert result["execution_reason"] == ExecutionReason.PENDING_SINGLE_NAME_CAPACITY
    assert result["pending_reason"] == "SINGLE_NAME_CAPACITY"
    assert result["block_reason"] == ""


def test_add_pending_when_gap_has_not_accumulated_to_one_lot() -> None:
    result = size_add(
        symbol="600000.sh",
        price=20.0,
        current_position_shares=100,
        current_position_value=2_000,
        account_equity=50_000,
        available_cash=20_000,
        min_trade_value=1_500,
        round_lot=100,
        max_single_stock_weight=0.12,
        target_position_value=2_500,
        intended_order_value=500,
    )

    assert result["execution_status"] == ExecutionStatus.PENDING
    assert result["execution_reason"] == ExecutionReason.PENDING_LOT_ACCUMULATION_REQUIRED
    assert result["pending_reason"] == "LOT_SIZE_ACCUMULATION_REQUIRED"


def test_add_pending_when_cash_below_one_lot() -> None:
    result = size_add(
        symbol="600000.sh",
        price=20.0,
        current_position_shares=100,
        current_position_value=2_000,
        account_equity=50_000,
        available_cash=1_500,
        min_trade_value=1_500,
        round_lot=100,
        max_single_stock_weight=0.12,
        target_position_value=6_000,
        intended_order_value=4_000,
    )

    assert result["execution_status"] == ExecutionStatus.PENDING
    assert result["execution_reason"] == ExecutionReason.PENDING_CASH_INSUFFICIENT_FOR_ONE_LOT
    assert result["pending_reason"] == "CASH_INSUFFICIENT_FOR_ONE_LOT"


def test_legacy_compute_lot_aware_order_keeps_old_fields_and_adds_execution_fields() -> None:
    result = compute_lot_aware_order(
        symbol="600000.sh",
        latest_price=20.0,
        current_position_shares=0,
        current_position_value=0,
        account_equity=50_000,
        available_cash=1_500,
        min_trade_value=1_500,
        round_lot=100,
        max_single_stock_weight=0.12,
        target_position_value=6_000,
        intended_order_value=6_000,
        action_type="NEW_BUY",
        current_positions_count=99,
        max_positions=1,
        daily_new_position_count=99,
        max_new_positions_per_day=1,
        daily_add_count=99,
        max_adds_per_day=1,
    )

    for field in {
        "executable",
        "executable_amount",
        "executable_shares",
        "block_reason",
        "pending_add_state",
        "pending_reason",
        "pending_until_condition",
        "lot_notional",
        "minimum_lot_order_value",
        "minimum_lots",
        "max_single_position_value",
        "remaining_single_name_capacity",
        "execution_status",
        "execution_reason",
        "all_failed_checks",
        "unblock_hint",
    }:
        assert field in result
    assert result["execution_status"] == ExecutionStatus.PENDING
    assert result["execution_reason"] == ExecutionReason.PENDING_CASH_INSUFFICIENT_FOR_ONE_LOT
    assert result["block_reason"] == ""
