from __future__ import annotations

from collections import Counter
from typing import Any


QUALITY_FILL_ACTION = "BUY_DEFENSIVE_FILL"
QUALITY_FILL_BLOCKED = "WATCH_ONLY_DEFENSIVE_FILL_BLOCKED"
WINNER_ADD_ACTION = "BUY_WINNER_ADD"
WINNER_ADD_BLOCKED = "WATCH_ONLY_WINNER_ADD_BLOCKED"
GROUP_CAP_BLOCKED = "WATCH_ONLY_GROUP_CONCENTRATION"
REGIME_REVIEW_ACTION = "BUY_REGIME_REVIEW_FILL"
REGIME_REVIEW_BLOCKED = "WATCH_ONLY_REGIME_REVIEW_BLOCKED"
CASH_SLEEVE_ACTION = "BUY_CASH_SLEEVE_RESEARCH"
CASH_SLEEVE_LABEL = "CASH_SLEEVE_RESEARCH_ONLY"


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


def _thresholds(cfg: dict[str, Any]) -> dict[str, Any]:
    profile = str(cfg.get("threshold_profile", cfg.get("profile", "strict")))
    if "thresholds" in cfg:
        return dict((cfg.get("thresholds") or {}).get(profile, {}))
    return dict((cfg.get("thresholds_grid") or {}).get(profile, {}))


def _lot_status_ok(status: object, allowed: list[str] | tuple[str, ...] | set[str] | None = None) -> bool:
    allowed_set = {str(item).upper() for item in (allowed or ["OK", "ACCEPTABLE", "FIT", "STRETCHED"])}
    aliases = {"FIT": "OK", "STRETCHED": "ACCEPTABLE"}
    normalized = str(status or "").upper()
    return normalized in allowed_set or aliases.get(normalized, normalized) in allowed_set


def _valuation_depth(decision: dict[str, Any]) -> float:
    return max(0.0, min(100.0, 100.0 - _safe_float(decision.get("stock_q_blended", decision.get("stock_valuation_quantile")), 100.0)))


def _dividend_score(decision: dict[str, Any]) -> float:
    return max(0.0, min(100.0, _safe_float(decision.get("dv_ttm")) / 0.06 * 100.0))


def _trend_confirmation(decision: dict[str, Any]) -> float:
    close = _safe_float(decision.get("close"))
    ma60 = _safe_float(decision.get("ma60"))
    ma120 = _safe_float(decision.get("ma120"))
    ma20_slope = _safe_float(decision.get("ma20_slope_10d"))
    score = 40.0
    if close > 0 and ma60 > 0 and close >= ma60:
        score += 30.0
    if ma20_slope >= 0:
        score += 20.0
    if close > 0 and ma120 > 0 and close <= ma120 * 1.08:
        score += 10.0
    return max(0.0, min(100.0, score))


def _industry_count(portfolio_state: dict[str, Any], industry: str) -> int:
    counts = portfolio_state.get("industry_position_counts")
    if isinstance(counts, dict):
        return int(_safe_float(counts.get(industry)))
    positions = portfolio_state.get("positions") or []
    return sum(1 for item in positions if str(item.get("industry", "")) == industry)


def _quality_required_checks(decision: dict[str, Any], portfolio_state: dict[str, Any], cfg: dict[str, Any]) -> dict[str, bool]:
    market_regime = str(portfolio_state.get("market_regime", decision.get("market_regime", "")))
    cash_ratio = _safe_float(portfolio_state.get("cash_ratio", decision.get("cash_ratio")))
    has_executable_stock_buy = _safe_bool(portfolio_state.get("has_executable_stock_buy", decision.get("has_executable_stock_buy")))
    thresholds = _thresholds(cfg)
    close = _safe_float(decision.get("close"))
    ma120 = _safe_float(decision.get("ma120"))
    close_to_ma120 = close / ma120 if close > 0 and ma120 > 0 else 999.0
    allowed_lot_status = (cfg.get("required") or {}).get("lot_fit_status_in") or ["OK", "ACCEPTABLE", "FIT", "STRETCHED"]
    return {
        "risk_on": market_regime == "risk_on",
        "cash_ratio_gt_0_30": cash_ratio > 0.30,
        "no_executable_stock_buy": not has_executable_stock_buy,
        "effective_universe_only": _safe_bool(decision.get("in_effective_universe"), True),
        "exclude_current_holdings": _safe_float(decision.get("current_shares")) <= 0 and _safe_float(decision.get("shares")) <= 0,
        "exclude_cyclical_rotation": str(decision.get("bucket", "")) != "cyclical_rotation",
        "quality_pass": _safe_bool(decision.get("quality_pass"), True),
        "fundamental_break_false": not _safe_bool(decision.get("fundamental_break")),
        "data_stale_false": not _safe_bool(decision.get("data_stale")),
        "core_fields_complete": _safe_bool(decision.get("core_fields_complete"), True),
        "lot_fit_status": _lot_status_ok(decision.get("lot_fit_status", "OK"), allowed_lot_status),
        "structural_lot_block_false": not _safe_bool(decision.get("structural_lot_block")),
        "final_score_min": _safe_float(decision.get("final_score", decision.get("universe_final_score"))) >= _safe_float(thresholds.get("final_score_min"), 0.0),
        "stock_q_blended_max": _safe_float(decision.get("stock_q_blended", decision.get("stock_valuation_quantile")), 100.0) <= _safe_float(thresholds.get("stock_q_blended_max"), 100.0),
        "industry_q_blended_max": _safe_float(decision.get("industry_q_blended"), 0.0) <= _safe_float(thresholds.get("industry_q_blended_max"), 100.0),
        "dv_ttm_min": _safe_float(decision.get("dv_ttm")) >= _safe_float(thresholds.get("dv_ttm_min"), 0.0),
        "close_to_ma120_max": close_to_ma120 <= _safe_float(thresholds.get("close_to_ma120_max"), 999.0),
        "ma20_slope_10d_min": _safe_float(decision.get("ma20_slope_10d")) >= _safe_float(thresholds.get("ma20_slope_10d_min"), -999.0),
    }


def compute_quality_defensive_fill_candidate(decision: dict[str, Any], portfolio_state: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    checks = _quality_required_checks(decision, portfolio_state, cfg)
    fail_reasons = [key.upper() for key, passed in checks.items() if not passed]
    industry = str(decision.get("industry", ""))
    concentration_penalty = 8.0 * max(0, _industry_count(portfolio_state, industry) - 0)
    lot_fit_penalty = 5.0 if str(decision.get("lot_fit_status", "")).upper() in {"ACCEPTABLE", "STRETCHED"} else 0.0
    fill_score = (
        0.35 * _safe_float(decision.get("expected_edge_score"), _safe_float(decision.get("final_score", decision.get("universe_final_score"))))
        + 0.25 * _safe_float(decision.get("universe_final_score", decision.get("final_score")))
        + 0.20 * _valuation_depth(decision)
        + 0.10 * _dividend_score(decision)
        + 0.10 * _trend_confirmation(decision)
        - concentration_penalty
        - lot_fit_penalty
    )
    eligible = not fail_reasons and _safe_bool(cfg.get("enabled"), True)
    return {
        "eligible": bool(eligible),
        "action_label": QUALITY_FILL_ACTION if eligible else QUALITY_FILL_BLOCKED,
        "fill_score": round(float(fill_score), 4),
        "fail_reasons": fail_reasons,
        "required_checks": checks,
        "trace_fields": {
            "symbol": decision.get("symbol"),
            "industry": industry,
            "bucket": decision.get("bucket"),
            "lot_notional": decision.get("lot_notional"),
            "stock_q_blended": decision.get("stock_q_blended", decision.get("stock_valuation_quantile")),
            "dv_ttm": decision.get("dv_ttm"),
            "future_return_used": False,
        },
    }


def quality_fill_sort_key(item: dict[str, Any]) -> tuple:
    decision = item.get("decision", item)
    result = item.get("result", {})
    return (
        -_safe_float(result.get("fill_score", decision.get("fill_score"))),
        abs(_safe_float(decision.get("lot_notional")) - _safe_float(decision.get("target_position_budget"))),
        _safe_float(decision.get("industry_position_count")),
        -_safe_float(decision.get("dv_ttm")),
        str(decision.get("symbol", "")),
    )


def compute_winner_add_candidate(holding: dict[str, Any], portfolio_state: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    market_regime = str(portfolio_state.get("market_regime", holding.get("market_regime", "")))
    cash_ratio = _safe_float(portfolio_state.get("cash_ratio", holding.get("cash_ratio")))
    positions_count = int(_safe_float(portfolio_state.get("positions_count"), 0.0))
    max_weight = _safe_float(cfg.get("max_single_stock_weight"), 0.16)
    close = _safe_float(holding.get("close"))
    ma60 = _safe_float(holding.get("ma60"))
    checks = {
        "CURRENT_POSITION": _safe_float(holding.get("shares", holding.get("current_shares"))) > 0,
        "RISK_ON": market_regime == "risk_on",
        "CASH_RATIO_GT_0_30": cash_ratio > 0.30,
        "POSITIONS_COUNT_GTE_3": positions_count >= 3,
        "WINNER_ONLY": _safe_float(holding.get("unrealized_pnl_pct")) >= 0.03,
        "CLOSE_GTE_MA60": close > 0 and ma60 > 0 and close >= ma60,
        "MA20_SLOPE_NON_NEGATIVE": _safe_float(holding.get("ma20_slope_10d")) >= 0,
        "THESIS_STILL_VALID": _safe_bool(holding.get("thesis_still_valid"), True),
        "FUNDAMENTAL_BREAK_FALSE": not _safe_bool(holding.get("fundamental_break")),
        "STRUCTURAL_LOT_BLOCK_FALSE": not _safe_bool(holding.get("structural_lot_block")),
        "MAX_SINGLE_STOCK_WEIGHT": _safe_float(holding.get("current_weight")) < max_weight - 1e-12,
        "MONTHLY_LIMIT": int(_safe_float(portfolio_state.get("winner_adds_this_month"), 0.0)) < int(_safe_float(cfg.get("max_adds_per_month"), 1.0)),
        "GROUP_CAP": bool((portfolio_state.get("group_cap_result") or {"allowed": True}).get("allowed", True)),
    }
    if close > 0 and _safe_float(holding.get("avg_cost")) > 0:
        checks["NO_AVERAGE_DOWN"] = close >= _safe_float(holding.get("avg_cost"))
    fail_reasons = [key for key, passed in checks.items() if not passed]
    eligible = _safe_bool(cfg.get("enabled"), True) and not fail_reasons
    return {
        "eligible": bool(eligible),
        "action_label": WINNER_ADD_ACTION if eligible else WINNER_ADD_BLOCKED,
        "fail_reasons": fail_reasons if "CLOSE_GTE_MA60" not in fail_reasons else [reason if reason != "CLOSE_GTE_MA60" else "TREND_NOT_CONFIRMED" for reason in fail_reasons],
        "required_checks": checks,
        "extra_lots": min(1, int(_safe_float(cfg.get("max_extra_lots_per_symbol"), 1.0))),
        "trace_fields": {
            "symbol": holding.get("symbol"),
            "unrealized_pnl_pct": holding.get("unrealized_pnl_pct"),
            "current_weight": holding.get("current_weight"),
            "max_single_stock_weight": max_weight,
            "future_return_used": False,
        },
    }


def _group_for_industry(industry: str, cfg: dict[str, Any]) -> str:
    definitions = cfg.get("group_definitions") or {
        "financial": {"industries": ["银行", "非银金融"]},
        "defensive_utility": {"industries": ["公用事业"]},
    }
    for group, info in definitions.items():
        if industry in set(info.get("industries", [])):
            return str(group)
    return ""


def evaluate_group_concentration(portfolio_state: dict[str, Any], candidate: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    if not _safe_bool(cfg.get("enabled"), True):
        return {"allowed": True, "blocked_reason": "", "group": "", "do_not_force_sell_existing": True}
    industry = str(candidate.get("industry", ""))
    group = _group_for_industry(industry, cfg)
    if not group:
        return {"allowed": True, "blocked_reason": "", "group": "", "do_not_force_sell_existing": True}
    positions = list(portfolio_state.get("positions") or [])
    candidate_symbol = str(candidate.get("symbol", ""))
    group_positions = [item for item in positions if _group_for_industry(str(item.get("industry", "")), cfg) == group]
    current_symbols = {str(item.get("symbol", "")) for item in group_positions}
    current_weight = sum(_safe_float(item.get("weight", item.get("current_weight"))) for item in group_positions)
    current_candidate_weight = sum(_safe_float(item.get("weight", item.get("current_weight"))) for item in group_positions if str(item.get("symbol", "")) == candidate_symbol)
    candidate_weight_after = _safe_float(candidate.get("weight_after_buy", candidate.get("target_weight", candidate.get("weight", 0.0))))
    post_positions = len(current_symbols | {candidate_symbol})
    post_weight = current_weight - current_candidate_weight + max(current_candidate_weight, candidate_weight_after)

    if group == "financial":
        max_positions = int(_safe_float(cfg.get("financial_max_positions"), 1.0))
        max_weight = _safe_float(cfg.get("financial_max_weight"), 0.30)
    else:
        max_positions = int(_safe_float(cfg.get("utility_max_positions"), 1.0))
        max_weight = _safe_float(cfg.get("utility_max_weight"), 0.20)
    allowed = post_positions <= max_positions and post_weight <= max_weight + 1e-12
    return {
        "allowed": bool(allowed),
        "blocked_reason": "" if allowed else GROUP_CAP_BLOCKED,
        "group": group,
        "group_current_weight": round(float(current_weight), 6),
        "group_post_weight": round(float(post_weight), 6),
        "group_current_positions": len(current_symbols),
        "group_post_positions": post_positions,
        "blocked_candidates": [] if allowed else [candidate_symbol],
        "avoided_drawdown_estimate": 0.0,
        "diagnostic_only": True,
        "do_not_force_sell_existing": True,
    }


def evaluate_market_regime_review_fill(decision: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    regime = str(decision.get("market_regime", ""))
    checks = {
        "NOT_RISK_OFF": regime != "risk_off",
        "REGIME_ALLOWED": regime in {"neutral", "risk_on"},
        "QUALITY_DEFENSIVE_FILL": _safe_bool(decision.get("is_quality_defensive_fill"), True),
        "NOT_CYCLICAL": str(decision.get("bucket", "")) != "cyclical_rotation",
        "CASH_RATIO_GT_0_30": _safe_float(decision.get("cash_ratio")) > 0.30,
        "FINAL_SCORE_MIN": _safe_float(decision.get("final_score", decision.get("universe_final_score"))) >= 68.0,
        "STOCK_Q_MAX": _safe_float(decision.get("stock_q_blended", decision.get("stock_valuation_quantile")), 100.0) <= 40.0,
        "CLOSE_GTE_MA60": _safe_float(decision.get("close")) > 0 and _safe_float(decision.get("close")) >= _safe_float(decision.get("ma60")),
        "FUNDAMENTAL_BREAK_FALSE": not _safe_bool(decision.get("fundamental_break")),
        "LOT_FIT_OK": _lot_status_ok(decision.get("lot_fit_status", "OK"), ["OK", "FIT"]),
    }
    fail_reasons = [key for key, passed in checks.items() if not passed]
    allowed = not fail_reasons and _safe_bool(cfg.get("enabled", True), True)
    return {
        "allowed": bool(allowed),
        "action_label": REGIME_REVIEW_ACTION if allowed else REGIME_REVIEW_BLOCKED,
        "fail_reasons": fail_reasons,
        "required_checks": checks,
        "diagnostic_only": False,
    }


def evaluate_cash_sleeve_research(context: dict[str, Any], market_data: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    available = {symbol: frame for symbol, frame in (market_data or {}).items() if getattr(frame, "empty", True) is False}
    active = (
        str(context.get("market_regime", "")) == "risk_on"
        and _safe_float(context.get("cash_ratio")) > 0.35
        and _safe_bool(context.get("no_executable_stock_buy"), True)
        and _safe_bool(context.get("no_quality_defensive_fill"), True)
        and _safe_bool(context.get("no_winner_add"), True)
    )
    if not available or not active:
        return {
            "cash_sleeve_data_available": bool(available),
            "cash_sleeve_trades": [],
            "cash_sleeve_trades_count": 0,
            "cash_sleeve_pnl": 0.0,
            "feasibility_only": not bool(available),
            "live_approval": False,
            "diagnostic_label": CASH_SLEEVE_LABEL,
        }

    symbol, frame = sorted(available.items())[0]
    row = frame.iloc[-1].to_dict()
    price = _safe_float(row.get("close"))
    nav = _safe_float(cfg.get("nav"), _safe_float(context.get("nav"), 50_000.0))
    cash = _safe_float(cfg.get("cash"), _safe_float(context.get("cash"), 0.0))
    round_lot = int(_safe_float(cfg.get("round_lot"), 100.0))
    max_weight = _safe_float(cfg.get("max_weight_risk_on"), 0.15)
    shares = int(min(cash, nav * max_weight) / max(price * round_lot, 1e-9)) * round_lot if price > 0 else 0
    trades = []
    if shares > 0:
        trades.append(
            {
                "symbol": symbol,
                "side": "BUY",
                "shares": shares,
                "price": price,
                "amount": shares * price,
                "action_label": CASH_SLEEVE_ACTION,
                "diagnostic_label": CASH_SLEEVE_LABEL,
                "research_only": True,
            }
        )
    return {
        "cash_sleeve_data_available": True,
        "cash_sleeve_trades": trades,
        "cash_sleeve_trades_count": len(trades),
        "cash_sleeve_pnl": 0.0,
        "feasibility_only": False,
        "live_approval": False,
        "diagnostic_label": CASH_SLEEVE_LABEL,
    }


def group_weight_snapshot(positions: list[dict[str, Any]], cfg: dict[str, Any]) -> dict[str, Any]:
    rows = []
    by_group: dict[str, Counter[str]] = {}
    weights: Counter[str] = Counter()
    for item in positions:
        group = _group_for_industry(str(item.get("industry", "")), cfg)
        if not group:
            continue
        by_group.setdefault(group, Counter())[str(item.get("symbol", ""))] += 1
        weights[group] += _safe_float(item.get("weight", item.get("current_weight")))
    for group, symbols in by_group.items():
        rows.append({"group": group, "positions": len(symbols), "weight": float(weights[group])})
    return {"groups": rows}
