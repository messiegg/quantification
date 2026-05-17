from __future__ import annotations

from typing import Any


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        numeric = float(value)
    except (TypeError, ValueError):
        return default
    if numeric != numeric:
        return default
    return numeric


def evaluate_partial_derisk(holding: dict[str, Any], policy: dict[str, Any] | None = None) -> dict[str, Any]:
    """Research-only 50k partial de-risk rule.

    This helper only returns an auditable action proposal. It does not place
    orders, does not talk to a broker, and keeps all sell shares in round lots.
    """

    policy = policy or {}
    round_lot = max(1, int(_safe_float(holding.get("round_lot", policy.get("round_lot")), 100.0)))
    shares = int(_safe_float(holding.get("shares", holding.get("current_shares")), 0.0))
    shares = shares // round_lot * round_lot
    loss_trigger = _safe_float(holding.get("unrealized_pnl_pct"), 0.0) <= _safe_float(policy.get("unrealized_pnl_pct_lte"), -0.08)
    close = _safe_float(holding.get("close"), 0.0)
    ma120 = _safe_float(holding.get("ma120"), 0.0)
    below_ma120 = close > 0 and ma120 > 0 and close < ma120
    rs_weak = _safe_float(holding.get("relative_strength", holding.get("rs")), 0.0) < _safe_float(policy.get("relative_strength_lt"), 0.0)
    slope_weak = _safe_float(holding.get("ma20_slope_10d"), 0.0) < 0.0
    confirmed = rs_weak or slope_weak
    reason_codes: list[str] = []
    if loss_trigger:
        reason_codes.append("LOSS_TRIGGER")
    if below_ma120:
        reason_codes.append("BELOW_MA120")
    if rs_weak:
        reason_codes.append("RS_WEAK")
    if slope_weak:
        reason_codes.append("MA20_SLOPE_WEAK")
    if shares <= 0:
        return {"action": "HOLD", "sell_shares": 0, "reason": "NO_ROUND_LOT_POSITION", "reason_codes": reason_codes}
    if not (loss_trigger and below_ma120 and confirmed):
        return {"action": "HOLD", "sell_shares": 0, "reason": "PARTIAL_DERISK_CONDITIONS_NOT_MET", "reason_codes": reason_codes}
    if shares <= round_lot:
        if bool(policy.get("single_lot_hold_with_risk_flag", False)):
            return {"action": "HOLD_WITH_RISK_FLAG", "sell_shares": 0, "reason": "SINGLE_LOT_RISK_FLAG", "reason_codes": reason_codes}
        return {"action": "SELL_ALL", "sell_shares": shares, "reason": "SINGLE_LOT_DERISK_SELL_ALL", "reason_codes": reason_codes}
    half = shares // 2
    sell_shares = max(round_lot, (half // round_lot) * round_lot)
    sell_shares = min(shares - round_lot, sell_shares)
    sell_shares = sell_shares // round_lot * round_lot
    return {"action": "REDUCE", "sell_shares": int(sell_shares), "reason": "PARTIAL_DERISK_ROUND_LOT_REDUCE", "reason_codes": reason_codes}
