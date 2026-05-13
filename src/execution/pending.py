from __future__ import annotations


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def normalize_pending_add_record(
    *,
    symbol: str,
    pending_add_value: float = 0.0,
    first_pending_date: str | None = None,
    pending_reason: str = "",
    required_lot_notional: float = 0.0,
    required_cash: float = 0.0,
    required_capacity: float = 0.0,
    pending_until_condition: str = "",
) -> dict:
    return {
        "symbol": symbol,
        "pending_add_value": max(0.0, _safe_float(pending_add_value)),
        "first_pending_date": first_pending_date,
        "pending_reason": pending_reason,
        "required_lot_notional": max(0.0, _safe_float(required_lot_notional)),
        "required_cash": max(0.0, _safe_float(required_cash)),
        "required_capacity": max(0.0, _safe_float(required_capacity)),
        "pending_until_condition": pending_until_condition,
    }


def merge_pending_add_value(existing_pending_value: float, current_target_gap: float, intended_order_value: float) -> float:
    return max(
        0.0,
        _safe_float(existing_pending_value),
        _safe_float(current_target_gap),
        _safe_float(intended_order_value),
    )


def build_pending_add_hint(
    *,
    pending_reason: str,
    required_lot_notional: float,
    required_cash: float,
    required_capacity: float,
) -> str:
    if pending_reason == "CASH_INSUFFICIENT_FOR_ONE_LOT":
        return f"Need available cash >= {required_cash:.2f}."
    if pending_reason == "SINGLE_NAME_CAPACITY":
        return f"Need remaining single-name capacity >= {required_capacity:.2f}."
    return f"Need accumulated add value >= {required_lot_notional:.2f}."


def update_pending_adds_from_allocated_decisions(decisions: list[dict]) -> list[dict]:
    records: list[dict] = []
    for decision in decisions:
        if not decision.get("pending_add_state"):
            continue
        records.append(
            normalize_pending_add_record(
                symbol=str(decision.get("symbol", "")),
                pending_add_value=_safe_float(decision.get("pending_add_value")),
                first_pending_date=decision.get("first_pending_date"),
                pending_reason=str(decision.get("pending_reason") or ""),
                required_lot_notional=_safe_float(decision.get("required_lot_notional")),
                required_cash=_safe_float(decision.get("required_cash")),
                required_capacity=_safe_float(decision.get("required_capacity")),
                pending_until_condition=str(decision.get("pending_until_condition") or ""),
            )
        )
    return records
