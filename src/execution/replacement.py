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


def _score(row: dict[str, Any]) -> float:
    return _safe_float(row.get("expected_edge_score", row.get("priority_score", row.get("final_score"))), 0.0)


def _holding_days(row: dict[str, Any]) -> int:
    return int(_safe_float(row.get("holding_days", row.get("days_held")), 0.0))


def _relative_strength(row: dict[str, Any]) -> float:
    for field in ("relative_strength", "rs", "rs_20d", "rs_60d", "relative_strength_score", "rs_score"):
        if field in row:
            return _safe_float(row.get(field), 0.0)
    return 0.0


def _weak_reasons(holding: dict[str, Any], policy: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    min_days = int(_safe_float(policy.get("min_holding_days_before_replacement"), 40.0))
    rs = _relative_strength(holding)
    close = _safe_float(holding.get("close"), 0.0)
    ma120 = _safe_float(holding.get("ma120"), 0.0)
    if _holding_days(holding) >= min_days and rs < 0:
        reasons.append("HOLDING_DAYS_AND_RS_WEAK")
    if _safe_float(holding.get("unrealized_pnl_pct"), 0.0) <= -0.06 and close > 0 and ma120 > 0 and close < ma120:
        reasons.append("LOSS_AND_BELOW_MA120")
    if _safe_float(holding.get("stock_q_blended"), 0.0) >= 60.0:
        reasons.append("VALUATION_NOT_CHEAP")
    if _safe_bool(holding.get("fundamental_break")):
        reasons.append("FUNDAMENTAL_BREAK")
    if holding.get("thesis_still_valid") is not None and not _safe_bool(holding.get("thesis_still_valid")):
        reasons.append("THESIS_NOT_VALID")
    return reasons


def _base_pair(weakest: dict[str, Any] | None, candidate: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    sell_value = _safe_float(weakest.get("shares"), _safe_float(weakest.get("current_shares"), 0.0)) * _safe_float(weakest.get("close"), 0.0) if weakest else 0.0
    buy_value = _safe_float(candidate.get("lot_notional"), _safe_float(candidate.get("close"), 0.0) * _safe_float(policy.get("round_lot"), 100.0))
    fee = _safe_float(policy.get("commission_rate"), 0.0003)
    tax = _safe_float(policy.get("stamp_duty_rate_sell"), 0.0005)
    estimated_cost = sell_value * (fee + tax) + buy_value * fee
    return {
        "simulated_sell_symbol": weakest.get("symbol") if weakest else None,
        "simulated_buy_symbol": candidate.get("symbol"),
        "sell_industry": weakest.get("industry") if weakest else None,
        "buy_industry": candidate.get("industry"),
        "weakest_holding_score": _score(weakest or {}),
        "candidate_score": _score(candidate),
        "score_gap": round(_score(candidate) - _score(weakest or {}), 4),
        "estimated_turnover": round(sell_value + buy_value, 4),
        "estimated_cost": round(estimated_cost, 4),
        "replacement_month_count": int(_safe_float(policy.get("month_replacement_count"), 0.0)) + 1,
    }


def evaluate_50k_core_replacement(
    holdings: list[dict[str, Any]],
    candidate: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    """Evaluate a 50k core research-only simulated switch plan.

    In live/manual mode this only returns an advisory pair and never marks the
    replacement as executable. In backtests, callers may use a triggered result
    to simulate sell-then-buy cash release.
    """

    active_holdings = [item for item in holdings if _safe_float(item.get("shares", item.get("current_shares")), 0.0) > 0]
    weakest = min(active_holdings, key=lambda item: (_score(item), str(item.get("symbol", "")))) if active_holdings else None
    pair = _base_pair(weakest, candidate, policy)
    result = {
        "triggered": False,
        "reason": "",
        "advisory_only": True,
        "research_only_simulated_replacement": False,
        "sell_reason": "",
        "buy_reason": "",
        **pair,
    }
    if not _safe_bool(policy.get("enabled"), True):
        result["reason"] = "REPLACEMENT_DISABLED"
        return result
    if not _safe_bool(policy.get("portfolio_full"), False):
        result["reason"] = "PORTFOLIO_NOT_FULL"
        return result
    if not weakest:
        result["reason"] = "NO_HOLDING_TO_REPLACE"
        return result
    if int(_safe_float(policy.get("month_replacement_count"), 0.0)) >= int(_safe_float(policy.get("max_replacements_per_month"), 1.0)):
        result["reason"] = "MONTHLY_REPLACEMENT_LIMIT"
        return result
    if _safe_bool(candidate.get("structural_lot_block")):
        result["reason"] = "CANDIDATE_STRUCTURAL_LOT_BLOCK"
        return result
    account_equity = _safe_float(policy.get("account_equity"), 50_000.0)
    max_single = account_equity * _safe_float(policy.get("max_single_stock_weight"), 0.16)
    lot_notional = _safe_float(candidate.get("lot_notional"), _safe_float(candidate.get("close"), 0.0) * _safe_float(policy.get("round_lot"), 100.0))
    if lot_notional > max_single + 1e-9:
        result["reason"] = "CANDIDATE_ONE_LOT_ABOVE_SINGLE_NAME_CAP"
        return result
    industry_counts = policy.get("industry_position_counts") or {}
    candidate_industry = str(candidate.get("industry", ""))
    weakest_industry = str(weakest.get("industry", ""))
    industry_limit = int(_safe_float(policy.get("industry_max_positions"), 0.0))
    if candidate_industry != weakest_industry and industry_limit > 0 and int(industry_counts.get(candidate_industry, 0)) >= industry_limit:
        result["reason"] = "INDUSTRY_LIMIT"
        return result
    if _safe_bool(weakest.get("thesis_still_valid")) and _relative_strength(weakest) > 0:
        result["reason"] = "HOLDING_THESIS_VALID_RS_POSITIVE"
        return result
    weak_reasons = _weak_reasons(weakest, policy)
    if not weak_reasons:
        result["reason"] = "WEAKEST_HOLDING_NOT_WEAK_ENOUGH"
        return result
    score_gap = _score(candidate) - _score(weakest)
    if score_gap < _safe_float(policy.get("score_gap_threshold"), 10.0) - 1e-9:
        result["reason"] = "SCORE_GAP_INSUFFICIENT"
        return result

    result["sell_reason"] = ",".join(weak_reasons)
    result["buy_reason"] = "EXPECTED_EDGE_SCORE_GAP_AND_LOT_FIT"
    result["reason"] = "RESEARCH_ONLY_SIMULATED_SWITCH"
    if str(policy.get("mode", "backtest")) != "backtest":
        result["reason"] = "LIVE_MANUAL_ADVISORY_ONLY"
        return result
    if not _safe_bool(policy.get("backtest_switch_plan_enabled"), True):
        result["reason"] = "BACKTEST_SWITCH_PLAN_DISABLED"
        return result

    result["triggered"] = True
    result["advisory_only"] = False
    result["research_only_simulated_replacement"] = True
    return result
