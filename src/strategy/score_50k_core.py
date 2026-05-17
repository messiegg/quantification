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


def _safe_bool(value: object, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


def _clip(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, float(value)))


def _valuation_depth(decision: dict[str, Any]) -> float:
    for field in ("stock_q_blended", "stock_valuation_quantile", "stock_pb_q_blended", "stock_pe_ttm_q_blended"):
        if field in decision:
            return _clip(100.0 - _safe_float(decision.get(field), 100.0))
    return 0.0


def _quality_score(decision: dict[str, Any]) -> float:
    if "universe_final_score" in decision or "final_score" in decision:
        base = _clip(_safe_float(decision.get("universe_final_score", decision.get("final_score")), 50.0))
    else:
        base = 50.0
    if _safe_bool(decision.get("quality_pass")):
        base = max(base, 65.0)
    roe = _safe_float(decision.get("roe"), 0.0)
    cfo = _safe_float(decision.get("cfo_ttm"), 0.0)
    profit = _safe_float(decision.get("latest_net_profit"), 0.0)
    fundamentals = 0.0
    if roe > 0:
        fundamentals += min(20.0, roe * 100.0)
    if cfo > 0:
        fundamentals += 10.0
    if profit > 0:
        fundamentals += 10.0
    return _clip(base * 0.75 + fundamentals)


def _dividend_or_shareholder_return(decision: dict[str, Any]) -> float:
    if str(decision.get("bucket", "")) != "defensive_dividend":
        return 0.0
    dv = _safe_float(decision.get("dv_ttm"), 0.0)
    if dv <= 0.0:
        return 0.0
    return _clip((dv / 0.06) * 100.0)


def _trend_confirmation(decision: dict[str, Any]) -> float:
    close = _safe_float(decision.get("close"), 0.0)
    ma60 = _safe_float(decision.get("ma60"), 0.0)
    ma120 = _safe_float(decision.get("ma120"), 0.0)
    ma20_slope = _safe_float(decision.get("ma20_slope_10d"), 0.0)
    ma120_slope = _safe_float(decision.get("ma120_slope_20d"), 0.0)
    score = 50.0
    if close > 0 and ma60 > 0 and close >= ma60:
        score += 25.0
    if ma20_slope >= 0:
        score += 20.0
    if close > 0 and ma120 > 0 and close < ma120 and ma120_slope < 0:
        score -= 35.0
    return _clip(score)


def _relative_strength(decision: dict[str, Any]) -> float:
    for field in ("relative_strength_score", "rs_score"):
        if field in decision:
            return _clip(_safe_float(decision.get(field), 50.0))
    for field in ("relative_strength", "rs", "rs_20d", "rs_60d", "benchmark_rs"):
        if field in decision:
            raw = _safe_float(decision.get(field), 0.0)
            return _clip(50.0 + raw * 5.0 if abs(raw) > 1 else 50.0 + raw * 100.0)
    return 50.0


def _lot_fit(decision: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    close = _safe_float(decision.get("close"), 0.0)
    round_lot = int(_safe_float(policy.get("round_lot"), 100.0))
    account_equity = _safe_float(policy.get("account_equity"), _safe_float(policy.get("capital"), 50_000.0))
    cash_reserve_ratio = _safe_float(policy.get("cash_reserve_ratio"), 0.10)
    max_positions = max(1, int(_safe_float(policy.get("max_positions"), 5.0)))
    max_single_stock_weight = _safe_float(policy.get("max_single_stock_weight"), 0.16)
    lot_ratio = _safe_float(policy.get("lot_notional_max_ratio_to_target_budget"), 1.0)
    target_budget = account_equity * (1.0 - cash_reserve_ratio) / max_positions
    lot_notional = close * round_lot if close > 0 and round_lot > 0 else 0.0
    single_name_cap = account_equity * max_single_stock_weight
    structural_block = lot_notional > single_name_cap + 1e-9 if lot_notional > 0 else False
    if structural_block:
        status = "STRUCTURAL_BLOCK"
        penalty = 100.0
    elif lot_notional <= target_budget * lot_ratio + 1e-9:
        status = "FIT"
        penalty = 0.0
    elif lot_notional <= target_budget + 1e-9:
        status = "STRETCHED"
        penalty = min(20.0, (lot_notional / max(target_budget * lot_ratio, 1e-9) - 1.0) * 60.0)
    else:
        status = "OVER_BUDGET"
        penalty = min(45.0, 20.0 + (lot_notional / max(target_budget, 1e-9) - 1.0) * 80.0)
    return {
        "lot_fit_status": status,
        "lot_fit_penalty": round(float(penalty), 4),
        "lot_notional": round(float(lot_notional), 4),
        "target_position_budget": round(float(target_budget), 4),
        "structural_lot_block": bool(structural_block),
    }


def _industry_penalty(decision: dict[str, Any], policy: dict[str, Any]) -> float:
    counts = policy.get("industry_position_counts") or {}
    industry = str(decision.get("industry", ""))
    limit = int(_safe_float(policy.get("industry_max_positions"), 0.0))
    if not industry or limit <= 0:
        return 0.0
    return 20.0 if int(counts.get(industry, 0)) >= limit else 0.0


def _weak_holding_penalty(decision: dict[str, Any]) -> float:
    if _safe_float(decision.get("current_shares"), 0.0) <= 0 and _safe_float(decision.get("current_position_tranches"), 0.0) <= 0:
        return 0.0
    penalty = 0.0
    if _safe_float(decision.get("unrealized_pnl_pct"), 0.0) < -0.06:
        penalty += 8.0
    if _relative_strength(decision) < 45.0:
        penalty += 6.0
    if _valuation_depth(decision) < 35.0:
        penalty += 6.0
    return min(20.0, penalty)


def _cyclical_overlay(decision: dict[str, Any], policy: dict[str, Any], trend_score: float) -> tuple[bool, list[str]]:
    if str(decision.get("bucket", "")) != "cyclical_rotation":
        return True, []
    reasons: list[str] = []
    if str(policy.get("market_regime", "")).lower() != "risk_on":
        reasons.append("CYCLICAL_NOT_RISK_ON")
    if int(_safe_float(policy.get("cyclical_max_positions"), 1.0)) <= 0:
        reasons.append("CYCLICAL_DISABLED")
    if trend_score < 75.0:
        reasons.append("CYCLICAL_TREND_NOT_CONFIRMED")
    if _safe_bool(decision.get("cycle_peak_trap")):
        reasons.append("CYCLICAL_PEAK_TRAP")
    return not reasons, reasons


def compute_50k_expected_edge_score(decision: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    """Compute a 0-100 expected edge score plus audit fields for the 50k core profile.

    The function is intentionally standalone. It does not mutate combined_v2 ranking,
    does not call broker/order APIs, and uses only fields already present on the
    decision row for the current PIT date.
    """

    valuation = _valuation_depth(decision)
    quality = _quality_score(decision)
    dividend = _dividend_or_shareholder_return(decision)
    trend = _trend_confirmation(decision)
    relative_strength = _relative_strength(decision)
    lot = _lot_fit(decision, policy)
    industry_penalty = _industry_penalty(decision, policy)
    weak_penalty = _weak_holding_penalty(decision)
    cyclical_executable, watch_reasons = _cyclical_overlay(decision, policy, trend)
    expected = (
        0.30 * valuation
        + 0.25 * quality
        + 0.20 * dividend
        + 0.15 * trend
        + 0.10 * relative_strength
        - lot["lot_fit_penalty"]
        - industry_penalty
        - weak_penalty
    )
    components = {
        "valuation_depth": round(valuation, 4),
        "quality_score": round(quality, 4),
        "dividend_or_shareholder_return": round(dividend, 4),
        "trend_confirmation": round(trend, 4),
        "relative_strength": round(relative_strength, 4),
        "lot_fit_penalty": round(float(lot["lot_fit_penalty"]), 4),
        "industry_concentration_penalty": round(industry_penalty, 4),
        "weak_holding_penalty": round(weak_penalty, 4),
    }
    return {
        "expected_edge_score": round(float(expected), 4),
        "score_components": components,
        "lot_fit_status": lot["lot_fit_status"],
        "lot_notional": lot["lot_notional"],
        "target_position_budget": lot["target_position_budget"],
        "structural_lot_block": lot["structural_lot_block"],
        "cyclical_executable": bool(cyclical_executable),
        "watch_only_reasons": watch_reasons,
    }
