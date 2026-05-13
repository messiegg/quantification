from __future__ import annotations

from math import ceil

from src.execution.models import ExecutionReason, ExecutionStatus


LEGACY_REASON_MAP = {
    ExecutionReason.BLOCK_MISSING_FILL_PRICE: "MISSING_FILL_PRICE",
    ExecutionReason.BLOCK_INVALID_INPUT: "INVALID_INPUT",
    ExecutionReason.BLOCK_PRICE_TOO_HIGH_FOR_ACCOUNT_LOT: "PRICE_TOO_HIGH_FOR_ACCOUNT_LOT",
    ExecutionReason.BLOCK_MIN_TRADE_VALUE: "MIN_TRADE_VALUE",
    ExecutionReason.BLOCK_LOT_SIZE_ZERO: "LOT_SIZE_ZERO",
    ExecutionReason.PENDING_CASH_INSUFFICIENT_FOR_ONE_LOT: "CASH_INSUFFICIENT_FOR_ONE_LOT",
    ExecutionReason.PENDING_CASH_RESERVED: "CASH_RESERVED",
    ExecutionReason.PENDING_LOT_ACCUMULATION_REQUIRED: "LOT_SIZE_ACCUMULATION_REQUIRED",
    ExecutionReason.PENDING_SINGLE_NAME_CAPACITY: "SINGLE_NAME_CAPACITY",
}


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def compute_lot_notional(price: float, round_lot: int) -> float:
    return float(price) * int(round_lot)


def compute_minimum_lots(lot_notional: float, min_trade_value: float) -> int:
    if lot_notional <= 0:
        return 0
    minimum_order_value = max(float(min_trade_value), float(lot_notional))
    return int(ceil(minimum_order_value / lot_notional))


def _hint(reason: str) -> str:
    hints = {
        ExecutionReason.PENDING_CASH_INSUFFICIENT_FOR_ONE_LOT: "Wait for available cash to cover at least one round lot.",
        ExecutionReason.PENDING_CASH_RESERVED: "Wait for reserved cash to be released or reduce the cash reserve.",
        ExecutionReason.PENDING_LOT_ACCUMULATION_REQUIRED: "Wait until target gap or pending add value accumulates to one round lot.",
        ExecutionReason.PENDING_SINGLE_NAME_CAPACITY: "Wait until single-name capacity is released by price or position changes.",
        ExecutionReason.BLOCK_PRICE_TOO_HIGH_FOR_ACCOUNT_LOT: "One round lot exceeds the single-name account cap.",
        ExecutionReason.BLOCK_MISSING_FILL_PRICE: "Provide a valid positive fill price.",
        ExecutionReason.BLOCK_INVALID_INPUT: "Provide positive account equity and round-lot settings.",
        ExecutionReason.BLOCK_LOT_SIZE_ZERO: "No positive round-lot order can be produced.",
        ExecutionReason.BLOCK_MIN_TRADE_VALUE: "Order cannot satisfy the minimum trade value.",
    }
    return hints.get(reason, "")


def _base_payload(
    *,
    symbol: str,
    action_type: str,
    price: float,
    round_lot: int,
    min_trade_value: float,
    account_equity: float,
    max_single_stock_weight: float,
    current_position_value: float = 0.0,
) -> dict:
    lot_notional = compute_lot_notional(price, round_lot) if price > 0 and round_lot > 0 else 0.0
    minimum_lots = compute_minimum_lots(lot_notional, min_trade_value)
    minimum_lot_order_value = minimum_lots * lot_notional
    max_single_value = max(0.0, account_equity) * max(0.0, max_single_stock_weight)
    remaining_capacity = max(0.0, max_single_value - max(0.0, current_position_value))
    return {
        "symbol": symbol,
        "action_type": action_type,
        "lot_notional": lot_notional,
        "minimum_lot_order_value": minimum_lot_order_value,
        "minimum_lots": minimum_lots,
        "max_single_position_value": max_single_value,
        "remaining_single_name_capacity": remaining_capacity,
        "executable": False,
        "executable_amount": 0.0,
        "executable_shares": 0,
        "block_reason": "",
        "pending_add_state": False,
        "pending_reason": "",
        "pending_until_condition": "",
        "execution_eligible_for_new_buy": False,
        "execution_ineligible_reason": "",
        "execution_status": ExecutionStatus.NO_ACTION,
        "execution_reason": ExecutionReason.NO_ACTION,
        "all_failed_checks": [],
        "unblock_hint": "",
    }


def _finish(payload: dict, status: str, reason: str, *, executable_amount: float = 0.0, executable_shares: int = 0) -> dict:
    payload["execution_status"] = status
    payload["execution_reason"] = reason
    payload["all_failed_checks"] = [] if status == ExecutionStatus.EXECUTABLE else [reason]
    payload["unblock_hint"] = "" if status == ExecutionStatus.EXECUTABLE else _hint(reason)
    legacy_reason = LEGACY_REASON_MAP.get(reason, reason)
    if status == ExecutionStatus.EXECUTABLE:
        payload["executable"] = True
        payload["executable_amount"] = float(executable_amount)
        payload["executable_shares"] = int(executable_shares)
        payload["execution_ineligible_reason"] = ""
    elif status == ExecutionStatus.BLOCKED:
        payload["block_reason"] = legacy_reason
        payload["execution_ineligible_reason"] = legacy_reason
    elif status == ExecutionStatus.PENDING:
        payload["block_reason"] = ""
        payload["pending_reason"] = legacy_reason
        payload["execution_ineligible_reason"] = legacy_reason
        payload["pending_add_state"] = True
    return payload


def size_new_buy(
    *,
    symbol: str = "",
    price: float,
    account_equity: float,
    available_cash: float,
    min_trade_value: float,
    round_lot: int,
    max_single_stock_weight: float,
    target_position_value: float,
) -> dict:
    price = _safe_float(price)
    equity = _safe_float(account_equity)
    cash = max(0.0, _safe_float(available_cash))
    min_trade = max(0.0, _safe_float(min_trade_value))
    lot = int(round_lot or 0)
    max_single_weight = max(0.0, _safe_float(max_single_stock_weight))
    target_value = max(0.0, _safe_float(target_position_value))
    payload = _base_payload(
        symbol=symbol,
        action_type="NEW_BUY",
        price=price,
        round_lot=lot,
        min_trade_value=min_trade,
        account_equity=equity,
        max_single_stock_weight=max_single_weight,
    )
    if price <= 0:
        return _finish(payload, ExecutionStatus.BLOCKED, ExecutionReason.BLOCK_MISSING_FILL_PRICE)
    if lot <= 0 or equity <= 0:
        return _finish(payload, ExecutionStatus.BLOCKED, ExecutionReason.BLOCK_INVALID_INPUT)

    lot_notional = payload["lot_notional"]
    max_single_value = payload["max_single_position_value"]
    minimum_lots = payload["minimum_lots"]
    minimum_lot_order_value = payload["minimum_lot_order_value"]
    if lot_notional > max_single_value + 1e-9:
        return _finish(payload, ExecutionStatus.BLOCKED, ExecutionReason.BLOCK_PRICE_TOO_HIGH_FOR_ACCOUNT_LOT)
    if minimum_lot_order_value > max_single_value + 1e-9:
        return _finish(payload, ExecutionStatus.BLOCKED, ExecutionReason.BLOCK_PRICE_TOO_HIGH_FOR_ACCOUNT_LOT)
    if minimum_lot_order_value > cash + 1e-9:
        return _finish(payload, ExecutionStatus.PENDING, ExecutionReason.PENDING_CASH_INSUFFICIENT_FOR_ONE_LOT)

    desired_value = min(target_value, max_single_value, cash)
    desired_lots = int(desired_value // lot_notional)
    if desired_lots < minimum_lots:
        desired_lots = minimum_lots
    order_value = desired_lots * lot_notional
    if order_value > max_single_value + 1e-9 or order_value > cash + 1e-9:
        order_value = minimum_lot_order_value
        desired_lots = minimum_lots
    if order_value > max_single_value + 1e-9:
        return _finish(payload, ExecutionStatus.BLOCKED, ExecutionReason.BLOCK_PRICE_TOO_HIGH_FOR_ACCOUNT_LOT)
    if order_value > cash + 1e-9:
        return _finish(payload, ExecutionStatus.PENDING, ExecutionReason.PENDING_CASH_INSUFFICIENT_FOR_ONE_LOT)
    if desired_lots <= 0:
        return _finish(payload, ExecutionStatus.BLOCKED, ExecutionReason.BLOCK_LOT_SIZE_ZERO)

    payload["execution_eligible_for_new_buy"] = True
    return _finish(payload, ExecutionStatus.EXECUTABLE, ExecutionReason.EXECUTABLE, executable_amount=order_value, executable_shares=desired_lots * lot)


def size_add(
    *,
    symbol: str = "",
    price: float,
    current_position_shares: float,
    current_position_value: float | None = None,
    account_equity: float,
    available_cash: float,
    min_trade_value: float,
    round_lot: int,
    max_single_stock_weight: float,
    target_position_value: float,
    intended_order_value: float,
    pending_add_value: float = 0.0,
) -> dict:
    price = _safe_float(price)
    equity = _safe_float(account_equity)
    cash = max(0.0, _safe_float(available_cash))
    min_trade = max(0.0, _safe_float(min_trade_value))
    lot = int(round_lot or 0)
    shares = max(0.0, _safe_float(current_position_shares))
    current_value = _safe_float(current_position_value, shares * price)
    if current_position_value is None:
        current_value = shares * price
    max_single_weight = max(0.0, _safe_float(max_single_stock_weight))
    target_value = max(0.0, _safe_float(target_position_value))
    intended_value = max(0.0, _safe_float(intended_order_value))
    pending_value = max(0.0, _safe_float(pending_add_value))
    payload = _base_payload(
        symbol=symbol,
        action_type="ADD",
        price=price,
        round_lot=lot,
        min_trade_value=min_trade,
        account_equity=equity,
        max_single_stock_weight=max_single_weight,
        current_position_value=current_value,
    )
    payload["pending_until_condition"] = (
        "remaining_single_name_capacity >= lot_notional and available_cash >= lot_notional "
        "and accumulated_target_gap >= lot_notional"
    )
    if price <= 0:
        return _finish(payload, ExecutionStatus.BLOCKED, ExecutionReason.BLOCK_MISSING_FILL_PRICE)
    if lot <= 0 or equity <= 0:
        return _finish(payload, ExecutionStatus.BLOCKED, ExecutionReason.BLOCK_INVALID_INPUT)

    lot_notional = payload["lot_notional"]
    remaining_capacity = payload["remaining_single_name_capacity"]
    target_gap = max(0.0, target_value - current_value)
    accumulated_gap = max(target_gap, intended_value, pending_value)
    minimum_lots = payload["minimum_lots"]
    minimum_lot_order_value = payload["minimum_lot_order_value"]
    if remaining_capacity < lot_notional - 1e-9:
        return _finish(payload, ExecutionStatus.PENDING, ExecutionReason.PENDING_SINGLE_NAME_CAPACITY)
    if cash < lot_notional - 1e-9:
        return _finish(payload, ExecutionStatus.PENDING, ExecutionReason.PENDING_CASH_INSUFFICIENT_FOR_ONE_LOT)
    if accumulated_gap < lot_notional - 1e-9:
        return _finish(payload, ExecutionStatus.PENDING, ExecutionReason.PENDING_LOT_ACCUMULATION_REQUIRED)
    if accumulated_gap < min_trade - 1e-9 and minimum_lot_order_value > min(remaining_capacity, cash) + 1e-9:
        return _finish(payload, ExecutionStatus.PENDING, ExecutionReason.PENDING_LOT_ACCUMULATION_REQUIRED)

    desired_value = min(accumulated_gap, remaining_capacity, cash)
    desired_lots = int(desired_value // lot_notional)
    order_value = desired_lots * lot_notional
    if order_value < min_trade - 1e-9:
        minimum_add_lots = max(minimum_lots, int(ceil(min_trade / lot_notional)) if lot_notional > 0 else 0)
        minimum_add_value = minimum_add_lots * lot_notional
        if minimum_add_value <= remaining_capacity + 1e-9 and minimum_add_value <= cash + 1e-9:
            desired_lots = minimum_add_lots
            order_value = minimum_add_value
        elif minimum_add_value > remaining_capacity + 1e-9:
            return _finish(payload, ExecutionStatus.PENDING, ExecutionReason.PENDING_SINGLE_NAME_CAPACITY)
        else:
            return _finish(payload, ExecutionStatus.PENDING, ExecutionReason.PENDING_LOT_ACCUMULATION_REQUIRED)
    if desired_lots <= 0:
        return _finish(payload, ExecutionStatus.BLOCKED, ExecutionReason.BLOCK_LOT_SIZE_ZERO)
    if order_value > remaining_capacity + 1e-9:
        return _finish(payload, ExecutionStatus.PENDING, ExecutionReason.PENDING_SINGLE_NAME_CAPACITY)
    if order_value > cash + 1e-9:
        return _finish(payload, ExecutionStatus.PENDING, ExecutionReason.PENDING_CASH_INSUFFICIENT_FOR_ONE_LOT)
    return _finish(payload, ExecutionStatus.EXECUTABLE, ExecutionReason.EXECUTABLE, executable_amount=order_value, executable_shares=desired_lots * lot)


def legacy_compute_lot_aware_order(**kwargs) -> dict:
    action_type = str(kwargs.get("action_type", "")).upper()
    if action_type == "NEW_BUY":
        return size_new_buy(
            symbol=str(kwargs.get("symbol", "")),
            price=_safe_float(kwargs.get("latest_price")),
            account_equity=_safe_float(kwargs.get("account_equity")),
            available_cash=_safe_float(kwargs.get("available_cash")),
            min_trade_value=_safe_float(kwargs.get("min_trade_value")),
            round_lot=int(kwargs.get("round_lot") or 0),
            max_single_stock_weight=_safe_float(kwargs.get("max_single_stock_weight")),
            target_position_value=_safe_float(kwargs.get("target_position_value")),
        )
    if action_type == "ADD":
        return size_add(
            symbol=str(kwargs.get("symbol", "")),
            price=_safe_float(kwargs.get("latest_price")),
            current_position_shares=_safe_float(kwargs.get("current_position_shares")),
            current_position_value=_safe_float(kwargs.get("current_position_value")),
            account_equity=_safe_float(kwargs.get("account_equity")),
            available_cash=_safe_float(kwargs.get("available_cash")),
            min_trade_value=_safe_float(kwargs.get("min_trade_value")),
            round_lot=int(kwargs.get("round_lot") or 0),
            max_single_stock_weight=_safe_float(kwargs.get("max_single_stock_weight")),
            target_position_value=_safe_float(kwargs.get("target_position_value")),
            intended_order_value=_safe_float(kwargs.get("intended_order_value")),
            pending_add_value=_safe_float(kwargs.get("pending_add_value")),
        )
    payload = _base_payload(
        symbol=str(kwargs.get("symbol", "")),
        action_type=action_type or "UNKNOWN",
        price=_safe_float(kwargs.get("latest_price")),
        round_lot=int(kwargs.get("round_lot") or 0),
        min_trade_value=_safe_float(kwargs.get("min_trade_value")),
        account_equity=_safe_float(kwargs.get("account_equity")),
        max_single_stock_weight=_safe_float(kwargs.get("max_single_stock_weight")),
        current_position_value=_safe_float(kwargs.get("current_position_value")),
    )
    return _finish(payload, ExecutionStatus.BLOCKED, ExecutionReason.BLOCK_INVALID_INPUT)


compute_lot_aware_order = legacy_compute_lot_aware_order
