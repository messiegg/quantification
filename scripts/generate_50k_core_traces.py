#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import run_50k_compact_experiments as compact
from scripts.audit_common import DEFAULT_END_DATE, DEFAULT_START_DATE, load_audit_configs, load_benchmark_window, load_feature_window
from scripts.run_50k_core_experiments import (
    BUY_ACTIONS,
    PROFILE_NAME,
    SELL_ACTIONS,
    CoreParams,
    _account_cfg,
    _core_policy,
    _core_rank_key,
    _holding_records,
    _params_from_config,
    _prepare_feature_by_date,
    _regime_name,
    _safe_float,
    _safe_int,
    _strategy_cfg,
    _target_weight,
    core_account_gate,
)
from scripts.run_50k_core_repair_experiments import build_repair_variants
from src.execution.partial_derisk import evaluate_partial_derisk
from src.execution.replacement import evaluate_50k_core_replacement
from src.strategy.backtest_engine import BacktestEngine, Position
from src.strategy.regime import determine_market_regime
from src.strategy.score_50k_core import compute_50k_expected_edge_score
from src.strategy.signals import SignalEngine
from src.utils.config import load_yaml, resolve_path


CONFIG_PATH = "config/strategy_v2_50k_core.yml"
DEFAULT_OUTPUT_DIR = "reports/backtest/50k_core/traces"
DEFAULT_REPAIR_BEST_VARIANT = "mp5_tr1_tu8_cr10_sw18_ind2_def3_cy0_lot100_gap8_rpm1_ro85_ne60_rf25_rep1_cyc1_disable_both_monthly_review"

REQUIRED_TRACE_OUTPUTS = [
    "daily_portfolio_ledger.csv",
    "daily_position_pnl.csv",
    "trade_ledger.csv",
    "signal_execution_trace.csv",
    "exit_rule_trace.csv",
    "replacement_candidate_trace.csv",
    "drawdown_attribution_trace.csv",
    "risk_on_cash_trace.csv",
    "no_trade_interval_trace.csv",
    "trace_data_quality_report.md",
    "trace_diagnostic_report.md",
    "trace_missing_fields.json",
    "trace_effective_config.yml",
    "drawdown_attribution_summary.md",
    "risk_on_cash_trace_summary.md",
    "no_trade_interval_summary.md",
]

STAGE_FAILED_ENUM = {
    "NONE",
    "NOT_IN_UNIVERSE",
    "NO_RAW_SIGNAL",
    "STRATEGY_RULE_BLOCK",
    "MARKET_REGIME_BLOCK",
    "DATA_STALE_BLOCK",
    "FUNDAMENTAL_BREAK",
    "CYCLE_TRAP",
    "LOT_FIT_BLOCK",
    "ACCOUNT_CASH_BLOCK",
    "SINGLE_NAME_CAP_BLOCK",
    "PORTFOLIO_FULL",
    "INDUSTRY_CONCENTRATION",
    "DAILY_NEW_LIMIT",
    "DAILY_ADD_LIMIT",
    "REPLACEMENT_NOT_TRIGGERED",
    "MAX_TRANCHES",
    "WATCH_ONLY",
    "PENDING",
    "UNKNOWN",
}

CASH_REASON_ENUM = {
    "CASH_RATIO_WITHIN_TARGET",
    "NO_RAW_SIGNAL",
    "NO_ACCOUNT_ACTIONABLE_SIGNAL",
    "LOT_FIT_BLOCK",
    "PORTFOLIO_FULL",
    "INDUSTRY_CONCENTRATION",
    "REPLACEMENT_NOT_TRIGGERED",
    "DAILY_NEW_LIMIT",
    "CYCLICAL_DISABLED_OR_BLOCKED",
    "DEFENSIVE_CORE_NOT_FILLED",
    "SIGNAL_SCORE_TOO_LOW",
    "DATA_QUALITY_BLOCK",
    "UNKNOWN",
}

REPLACEMENT_REASON_ENUM = {
    "NOT_PORTFOLIO_FULL",
    "SCORE_GAP_TOO_SMALL",
    "CANDIDATE_LOT_BLOCK",
    "CANDIDATE_NOT_ACCOUNT_ACTIONABLE",
    "INDUSTRY_CONCENTRATION",
    "MONTHLY_REPLACEMENT_LIMIT",
    "HOLDING_DAYS_TOO_SHORT",
    "WEAK_HOLDING_THESIS_STILL_VALID_RS_POSITIVE",
    "NO_WEAK_HOLDING",
    "CASH_AFTER_SELL_INSUFFICIENT",
    "UNKNOWN",
}


@dataclass
class TraceBundle:
    daily_portfolio_ledger: pd.DataFrame
    daily_position_pnl: pd.DataFrame
    trade_ledger: pd.DataFrame
    signal_execution_trace: pd.DataFrame
    exit_rule_trace: pd.DataFrame
    replacement_candidate_trace: pd.DataFrame
    drawdown_attribution_trace: pd.DataFrame
    risk_on_cash_trace: pd.DataFrame
    no_trade_interval_trace: pd.DataFrame
    trace_missing_fields: dict[str, Any]
    trace_effective_config: dict[str, Any]


def _json(value: Any) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=False, sort_keys=True, default=str)


def _empty_series(dtype: str = "float64") -> pd.Series:
    return pd.Series(dtype=dtype)


def _feature_value(row: dict[str, Any], field: str, default: Any = "") -> Any:
    value = row.get(field, default)
    if isinstance(value, float) and pd.isna(value):
        return default
    return value


def _map_stage_reason(reason: str) -> str:
    mapping = {
        "WATCH_ONLY_PORTFOLIO_FULL": "PORTFOLIO_FULL",
        "WATCH_ONLY_CASH_RESERVED": "ACCOUNT_CASH_BLOCK",
        "WATCH_ONLY_LOT_TOO_EXPENSIVE": "LOT_FIT_BLOCK",
        "WATCH_ONLY_DAILY_NEW_LIMIT": "DAILY_NEW_LIMIT",
        "WATCH_ONLY_DAILY_ADD_LIMIT": "DAILY_ADD_LIMIT",
        "WATCH_ONLY_INDUSTRY_CONCENTRATION": "INDUSTRY_CONCENTRATION",
        "WATCH_ONLY_CYCLICAL_DISABLED": "MARKET_REGIME_BLOCK",
        "WATCH_ONLY_CYCLICAL_NOT_RISK_ON": "MARKET_REGIME_BLOCK",
        "WATCH_ONLY_CYCLICAL_TREND_NOT_CONFIRMED": "MARKET_REGIME_BLOCK",
        "WATCH_ONLY_CYCLICAL_LIMIT": "MARKET_REGIME_BLOCK",
        "WATCH_ONLY_DEFENSIVE_CORE_SHORTFALL": "MARKET_REGIME_BLOCK",
        "WATCH_ONLY_STRUCTURAL_LOT_BLOCK": "SINGLE_NAME_CAP_BLOCK",
        "WATCH_ONLY_CORE_RANK_OUT": "WATCH_ONLY",
        "MISSING_FILL_PRICE": "DATA_STALE_BLOCK",
    }
    return mapping.get(str(reason), "UNKNOWN")


def _map_replacement_reason(reason: str, *, portfolio_full: bool) -> str:
    if not portfolio_full:
        return "NOT_PORTFOLIO_FULL"
    mapping = {
        "SCORE_GAP_INSUFFICIENT": "SCORE_GAP_TOO_SMALL",
        "CANDIDATE_STRUCTURAL_LOT_BLOCK": "CANDIDATE_LOT_BLOCK",
        "CANDIDATE_ONE_LOT_ABOVE_SINGLE_NAME_CAP": "CANDIDATE_LOT_BLOCK",
        "INDUSTRY_LIMIT": "INDUSTRY_CONCENTRATION",
        "MONTHLY_REPLACEMENT_LIMIT": "MONTHLY_REPLACEMENT_LIMIT",
        "HOLDING_THESIS_VALID_RS_POSITIVE": "WEAK_HOLDING_THESIS_STILL_VALID_RS_POSITIVE",
        "NO_HOLDING_TO_REPLACE": "NO_WEAK_HOLDING",
        "WEAKEST_HOLDING_NOT_WEAK_ENOUGH": "NO_WEAK_HOLDING",
        "PORTFOLIO_NOT_FULL": "NOT_PORTFOLIO_FULL",
        "RESEARCH_ONLY_SIMULATED_SWITCH": "UNKNOWN",
    }
    return mapping.get(str(reason), "UNKNOWN")


def _variant_params(source: str, variant: str | None) -> CoreParams:
    variant = variant or DEFAULT_REPAIR_BEST_VARIANT
    if source == "repair":
        for item in build_repair_variants():
            if item.name == variant:
                return item.params
        if variant == DEFAULT_REPAIR_BEST_VARIANT:
            for item in build_repair_variants():
                if item.name.endswith("_monthly_review"):
                    return item.params
    config = load_yaml(CONFIG_PATH)
    for item in _params_from_config(config):
        if item.variant_id == variant:
            return item
    # Fallback for the known stage1 top attempted variant if reports exist but
    # the sampled config order no longer reconstructs it directly.
    if "disable_both" in variant:
        return CoreParams(
            max_positions=5,
            max_tranches=1,
            target_universe_size=8,
            cash_reserve_ratio=0.10,
            max_single_stock_weight=0.18,
            max_new_positions_per_day=1,
            max_adds_per_day=0,
            industry_max_positions=2,
            defensive_core_min_positions=3,
            cyclical_max_positions=0,
            lot_notional_max_ratio_to_target_budget=1.00,
            score_gap_threshold=8,
            max_replacements_per_month=1,
            risk_on_target_exposure=0.85,
            neutral_target_exposure=0.60,
            risk_off_target_exposure=0.25,
            module_control="disable_both",
            replacement_enabled=True,
            cyclical_overlay_enabled=True,
            monthly_rebalance_review_enabled=variant.endswith("_monthly_review"),
            target_cash_ratio=0.35,
            repair_label="monthly_review" if variant.endswith("_monthly_review") else "",
        )
    raise ValueError(f"Cannot reconstruct params for variant={variant!r} source={source!r}")


def _position_snapshot(positions: dict[str, Position], prices: pd.DataFrame, nav: float) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for symbol, position in positions.items():
        close = _safe_float(prices.loc[symbol, "close"]) if symbol in prices.index and "close" in prices.columns else position.last_fill_price
        market_value = position.shares * close
        rows[symbol] = {
            "symbol": symbol,
            "shares": float(position.shares),
            "avg_cost": float(position.avg_cost),
            "industry": position.industry,
            "bucket": position.bucket,
            "entry_date": position.entry_date,
            "entry_index": position.entry_index,
            "entry_signal": position.entry_reason,
            "last_buy_date": position.last_buy_date,
            "last_sell_date": "",
            "close": close,
            "market_value": market_value,
            "unrealized_pnl": (close - position.avg_cost) * position.shares,
            "weight": market_value / max(nav, 1e-9),
        }
    return rows


def _signal_trace_row(
    *,
    date: str,
    params: CoreParams,
    decision: dict[str, Any],
    regime_name: str,
    nav: float,
    cash: float,
    positions: dict[str, Position],
    selected: bool,
    watch_reason: str,
    replacement_candidate: bool,
    replacement_triggered: bool,
    raw_rank: int | None,
    daily_new_used: int,
) -> dict[str, Any]:
    symbol = str(decision.get("symbol", ""))
    current_shares = _safe_float(decision.get("current_shares"), 0.0)
    current_weight = current_shares * _safe_float(decision.get("close"), 0.0) / max(nav, 1e-9)
    action = str(decision.get("action_enum", "HOLD"))
    raw_buy = action in BUY_ACTIONS
    stage = "NONE" if selected else (_map_stage_reason(watch_reason) if watch_reason else ("NO_RAW_SIGNAL" if not raw_buy else "UNKNOWN"))
    stage = stage if stage in STAGE_FAILED_ENUM else "UNKNOWN"
    return {
        "date": date,
        "variant": params.variant_id,
        "symbol": symbol,
        "name": decision.get("name", symbol),
        "bucket": decision.get("bucket", ""),
        "industry": decision.get("industry", ""),
        "in_effective_universe": bool(decision.get("in_effective_universe", False)),
        "market_regime": regime_name,
        "raw_signal_generated": raw_buy,
        "raw_signal_type": action if raw_buy else "",
        "strategy_intent": action,
        "intended_action_enum": action,
        "final_action_enum": action if selected else ("HOLD" if watch_reason else action),
        "user_visible_action": bool(selected),
        "account_actionable": bool(selected),
        "portfolio_actionable": bool(selected),
        "executable": bool(selected),
        "watch_only": bool(watch_reason),
        "blocked": stage.endswith("_BLOCK") or stage in {"PORTFOLIO_FULL", "INDUSTRY_CONCENTRATION"},
        "pending": stage == "PENDING",
        "skipped": not selected and not raw_buy,
        "stage_failed": stage,
        "primary_failure_reason": watch_reason,
        "all_failure_reasons_json": _json([watch_reason] if watch_reason else []),
        "raw_buy_rank": raw_rank,
        "compact_rank": raw_rank,
        "expected_edge_score": decision.get("expected_edge_score"),
        "score_components_json": _json(decision.get("score_components") or {}),
        "lot_notional": decision.get("lot_notional", _safe_float(decision.get("close")) * params.round_lot),
        "target_position_budget": decision.get("target_position_budget"),
        "lot_fit_status": decision.get("lot_fit_status", ""),
        "structural_lot_block": bool(decision.get("structural_lot_block", False)),
        "current_shares": current_shares,
        "current_weight": current_weight,
        "current_position_tranches": decision.get("current_position_tranches", 0),
        "target_weight": _target_weight(params, regime_name),
        "target_shares": decision.get("target_shares", ""),
        "delta_shares": decision.get("delta_shares", ""),
        "estimated_turnover": decision.get("target_order_value", ""),
        "available_cash_before": cash,
        "cash_reserve_required": params.cash_reserve_ratio * nav,
        "max_positions": params.max_positions,
        "positions_count": len(positions),
        "industry_positions_count": sum(1 for item in positions.values() if item.industry == str(decision.get("industry", ""))),
        "industry_max_positions": params.industry_max_positions,
        "replacement_candidate": bool(replacement_candidate),
        "replacement_required": bool(stage == "PORTFOLIO_FULL"),
        "replacement_triggered": bool(replacement_triggered),
        "daily_new_position_limit_used": daily_new_used,
        "daily_add_limit_used": 0,
        "risk_on_cash_deploy_candidate": bool(regime_name == "risk_on" and raw_buy and not selected),
        "trace_quality_flag": "FULLY_SUPPORTED",
    }


def _exit_row(
    *,
    date: str,
    params: CoreParams,
    symbol: str,
    position: Position,
    decision: dict[str, Any],
    regime_name: str,
    nav: float,
    current_index: int,
) -> dict[str, Any]:
    close = _safe_float(decision.get("close"), position.last_fill_price)
    ma120 = _safe_float(decision.get("ma120"))
    ma20_slope = _safe_float(decision.get("ma20_slope_10d"))
    ma120_slope = _safe_float(decision.get("ma120_slope_20d"))
    rs = _safe_float(decision.get("relative_strength", decision.get("rs", 0.0)))
    trend_would = close > 0 and ma120 > 0 and close < ma120 and (ma120_slope < 0 or ma20_slope < 0)
    trend_disabled = params.module_control in {"disable_trend_stop", "disable_both"}
    holding = {
        **decision,
        "symbol": symbol,
        "shares": position.shares,
        "round_lot": params.round_lot,
        "unrealized_pnl_pct": (close / position.avg_cost - 1.0) if position.avg_cost > 0 and close > 0 else 0.0,
    }
    derisk = evaluate_partial_derisk(holding, {"round_lot": params.round_lot}) if params.partial_derisk_enabled else {"action": "DISABLED_BY_PROFILE", "sell_shares": 0, "reason": "disabled_by_profile"}
    action = str(decision.get("action_enum", "HOLD"))
    selected_exit = action if action in SELL_ACTIONS else ("PARTIAL_DERISK" if derisk.get("action") in {"REDUCE", "SELL_ALL"} else "HOLD")
    return {
        "date": date,
        "variant": params.variant_id,
        "symbol": symbol,
        "bucket": position.bucket,
        "industry": position.industry,
        "market_regime": regime_name,
        "shares": position.shares,
        "position_weight": position.shares * close / max(nav, 1e-9),
        "holding_days": max(0, current_index - position.entry_index),
        "unrealized_pnl_pct": holding["unrealized_pnl_pct"],
        "close": close,
        "ma20": decision.get("ma20"),
        "ma60": decision.get("ma60"),
        "ma120": decision.get("ma120"),
        "ma250": decision.get("ma250"),
        "ma20_slope_10d": decision.get("ma20_slope_10d"),
        "ma120_slope_20d": decision.get("ma120_slope_20d"),
        "stock_q_blended": decision.get("stock_q_blended"),
        "industry_q_blended": decision.get("industry_q_blended"),
        "relative_strength": rs,
        "thesis_still_valid": not bool(decision.get("fundamental_break", False)) and _safe_float(decision.get("stock_q_blended"), 100.0) <= 60.0,
        "fundamental_break": bool(decision.get("fundamental_break", False)),
        "cycle_peak_trap": bool(decision.get("cycle_peak_trap", False)),
        "valuation_reversion_exit_triggered": _safe_float(decision.get("stock_q_blended"), 0.0) >= 60.0,
        "soft_trim_triggered": holding["unrealized_pnl_pct"] > 0.20 and rs < 0,
        "trend_stop_triggered": bool(trend_would and not trend_disabled),
        "would_have_triggered_trend_stop": bool(trend_would),
        "trend_stop_disabled_by_profile": bool(trend_disabled),
        "partial_derisk_triggered": derisk.get("action") in {"REDUCE", "SELL_ALL"},
        "partial_derisk_profile_state": "enabled" if params.partial_derisk_enabled else "disabled_by_profile",
        "cycle_peak_trap_trend_break_triggered": bool(decision.get("cycle_peak_trap", False) and trend_would),
        "replacement_sell_triggered": False,
        "force_exit_triggered": action == "SELL_ALL",
        "selected_exit_action": selected_exit,
        "selected_exit_reason": decision.get("action_reason", derisk.get("reason", "")),
        "exit_priority_order_json": _json(["force_exit", "replacement", "partial_derisk", "trend_stop", "soft_trim", "valuation_reversion"]),
        "reduce_or_sell_shares": derisk.get("sell_shares", position.shares if action == "SELL_ALL" else 0),
        "reduce_or_sell_lots": _safe_float(derisk.get("sell_shares", 0.0)) / max(params.round_lot, 1),
        "exit_executable": selected_exit != "HOLD",
        "exit_blocked_reason": "",
        "missed_exit_candidate": bool(trend_would and selected_exit == "HOLD"),
        "missed_exit_reason": "TREND_STOP_DISABLED_OR_NOT_SELECTED" if trend_would and selected_exit == "HOLD" else "",
        "trace_quality_flag": "PARTIALLY_SUPPORTED_RULE_HEURISTIC",
    }


def _future_return(feature_by_date: dict[str, pd.DataFrame], dates: list[str], date: str, symbol: str, horizon: int) -> float | None:
    try:
        idx = dates.index(date)
    except ValueError:
        return None
    future_idx = min(idx + horizon, len(dates) - 1)
    current = feature_by_date[date].set_index("symbol")
    future = feature_by_date[dates[future_idx]].set_index("symbol")
    if symbol not in current.index or symbol not in future.index:
        return None
    current_close = _safe_float(current.loc[symbol, "close"])
    future_close = _safe_float(future.loc[symbol, "close"])
    if current_close <= 0 or future_close <= 0:
        return None
    return future_close / current_close - 1.0


def _replacement_trace_row(
    *,
    date: str,
    params: CoreParams,
    candidate: dict[str, Any],
    holding_decisions: list[dict[str, Any]],
    replacement: dict[str, Any],
    portfolio_full: bool,
    month_count: int,
    feature_by_date: dict[str, pd.DataFrame],
    dates: list[str],
    pair_id: str,
) -> dict[str, Any]:
    sell_symbol = str(replacement.get("simulated_sell_symbol") or "")
    weakest = next((item for item in holding_decisions if str(item.get("symbol")) == sell_symbol), {})
    reason = _map_replacement_reason(str(replacement.get("reason", "")), portfolio_full=portfolio_full)
    cand20 = _future_return(feature_by_date, dates, date, str(candidate.get("symbol")), 20)
    weak20 = _future_return(feature_by_date, dates, date, sell_symbol, 20) if sell_symbol else None
    cand60 = _future_return(feature_by_date, dates, date, str(candidate.get("symbol")), 60)
    weak60 = _future_return(feature_by_date, dates, date, sell_symbol, 60) if sell_symbol else None
    return {
        "date": date,
        "variant": params.variant_id,
        "portfolio_full": bool(portfolio_full),
        "candidate_symbol": candidate.get("symbol"),
        "candidate_name": candidate.get("name", candidate.get("symbol")),
        "candidate_bucket": candidate.get("bucket"),
        "candidate_industry": candidate.get("industry"),
        "candidate_score": replacement.get("candidate_score"),
        "candidate_lot_notional": candidate.get("lot_notional"),
        "candidate_lot_fit_status": candidate.get("lot_fit_status"),
        "candidate_structural_lot_block": bool(candidate.get("structural_lot_block", False)),
        "candidate_account_actionable": not bool(candidate.get("structural_lot_block", False)),
        "candidate_expected_edge_score": candidate.get("expected_edge_score"),
        "weakest_holding_symbol": sell_symbol,
        "weakest_holding_name": weakest.get("name", sell_symbol),
        "weakest_holding_bucket": weakest.get("bucket"),
        "weakest_holding_industry": weakest.get("industry"),
        "weakest_holding_score": replacement.get("weakest_holding_score"),
        "weakest_holding_unrealized_pnl_pct": weakest.get("unrealized_pnl_pct"),
        "weakest_holding_holding_days": weakest.get("holding_days"),
        "weakest_holding_relative_strength": weakest.get("relative_strength", weakest.get("rs", 0.0)),
        "weakest_holding_thesis_still_valid": weakest.get("thesis_still_valid"),
        "weakest_holding_fundamental_break": weakest.get("fundamental_break", False),
        "score_gap": replacement.get("score_gap"),
        "score_gap_threshold": params.score_gap_threshold,
        "min_holding_days_before_replacement": params.min_holding_days_before_replacement,
        "max_replacements_per_month": params.max_replacements_per_month,
        "current_month_replacement_count": month_count,
        "replacement_triggered": bool(replacement.get("triggered")),
        "replacement_pair_id": pair_id if replacement.get("triggered") else "",
        "reason_not_triggered": "" if replacement.get("triggered") else reason,
        "all_replacement_checks_json": _json({"raw_reason": replacement.get("reason"), "mapped_reason": reason}),
        "diagnostic_future_return_20d_candidate": cand20,
        "diagnostic_future_return_20d_weakest": weak20,
        "diagnostic_opportunity_cost_20d": (cand20 - weak20) if cand20 is not None and weak20 is not None else None,
        "diagnostic_future_return_60d_candidate": cand60,
        "diagnostic_future_return_60d_weakest": weak60,
        "diagnostic_opportunity_cost_60d": (cand60 - weak60) if cand60 is not None and weak60 is not None else None,
        "diagnostic_only": True,
        "trace_quality_flag": "DIAGNOSTIC_ONLY_FUTURE_RETURN",
    }


def _trade_row(
    *,
    raw: dict[str, Any],
    params: CoreParams,
    trade_id: str,
    decision_lookup: dict[tuple[str, str], dict[str, Any]],
    before: dict[str, Any],
    after_position: Position | None,
    price_today: pd.DataFrame,
    next_day: pd.DataFrame,
    market_regime: str,
    replacement_pair_id: str = "",
) -> dict[str, Any]:
    symbol = str(raw.get("symbol"))
    side = str(raw.get("side", "")).upper()
    is_repl = bool(raw.get("replacement_simulated"))
    action = str(raw.get("action", raw.get("action_enum", side)))
    full_side = "REPLACEMENT_BUY" if is_repl and side == "BUY" else "REPLACEMENT_SELL" if is_repl and side == "SELL" else "SELL_ALL" if action == "SELL_ALL" else side
    shares = _safe_float(raw.get("shares"))
    price = _safe_float(raw.get("price"))
    previous_close = _safe_float(price_today.loc[symbol, "close"]) if symbol in price_today.index and "close" in price_today.columns else None
    next_open = _safe_float(next_day.loc[symbol, "open"]) if symbol in next_day.index and "open" in next_day.columns else None
    close = _safe_float(next_day.loc[symbol, "close"]) if symbol in next_day.index and "close" in next_day.columns else None
    avg_after = after_position.avg_cost if after_position else 0.0
    shares_after = after_position.shares if after_position else 0.0
    decision = decision_lookup.get((str(raw.get("signal_date", "")), symbol), {})
    return {
        "trade_id": trade_id,
        "date": raw.get("date"),
        "signal_date": raw.get("signal_date"),
        "variant": params.variant_id,
        "symbol": symbol,
        "name": raw.get("name", symbol),
        "bucket": raw.get("bucket", before.get("bucket", "")),
        "industry": raw.get("industry", before.get("industry", "")),
        "side": full_side,
        "action_enum": action,
        "action_source": "research_backtest_trace",
        "signal_level": raw.get("signal_level", action),
        "entry_signal": before.get("entry_signal", ""),
        "exit_signal": action if side != "BUY" else "",
        "replacement_pair_id": replacement_pair_id,
        "is_replacement_sell": bool(is_repl and side == "SELL"),
        "is_replacement_buy": bool(is_repl and side == "BUY"),
        "shares": shares,
        "round_lot": params.round_lot,
        "lots": shares / max(params.round_lot, 1),
        "fill_price": price,
        "previous_close": previous_close,
        "next_open": next_open,
        "close": close,
        "trade_value": _safe_float(raw.get("amount")),
        "commission": _safe_float(raw.get("fee")),
        "stamp_tax": _safe_float(raw.get("tax")),
        "slippage": abs(price - _safe_float(next_open, price)) * shares if next_open else 0.0,
        "total_cost": _safe_float(raw.get("fee")) + _safe_float(raw.get("tax")),
        "cash_before": raw.get("cash_before"),
        "cash_after": raw.get("cash_after"),
        "shares_before": before.get("shares", 0.0),
        "shares_after": shares_after,
        "position_value_before": before.get("market_value", 0.0),
        "position_value_after": shares_after * _safe_float(close, price),
        "average_cost_before": before.get("avg_cost", 0.0),
        "average_cost_after": avg_after,
        "realized_pnl": raw.get("realized_pnl", 0.0),
        "realized_pnl_pct": (_safe_float(raw.get("realized_pnl")) / max(abs(before.get("avg_cost", 0.0) * shares), 1e-9)) if side != "BUY" else 0.0,
        "holding_days_at_exit": decision.get("holding_days", ""),
        "market_regime": market_regime,
        "reason_codes_json": _json(raw.get("reason_codes", [])),
        "blocked_reason_before_execution": "",
        "execution_status": "EXECUTED",
        "execution_reason": raw.get("partial_derisk_reason", raw.get("fill_price_field", "")),
        "trace_quality_flag": "RESEARCH_ONLY_SIMULATED_NEXT_BAR",
    }


def generate_trace_bundle(params: CoreParams) -> TraceBundle:
    configs = load_audit_configs()
    features = load_feature_window(DEFAULT_START_DATE, DEFAULT_END_DATE)
    benchmark = load_benchmark_window(DEFAULT_START_DATE, DEFAULT_END_DATE)
    feature_by_date, approximate = _prepare_feature_by_date(features, configs)
    dates = sorted(feature_by_date)
    strategy = _strategy_cfg(configs["v2_strategy"], params)
    account = _account_cfg(configs["account"], params)
    signal_engine = SignalEngine(strategy, configs["v2_universe"], account)

    cash = params.capital
    positions: dict[str, Position] = {}
    month_replacements: Counter[str] = Counter()
    previous_nav = params.capital
    previous_position_unrealized: dict[str, float] = defaultdict(float)

    daily_rows: list[dict[str, Any]] = []
    position_rows: list[dict[str, Any]] = []
    trade_rows: list[dict[str, Any]] = []
    signal_rows: list[dict[str, Any]] = []
    exit_rows: list[dict[str, Any]] = []
    replacement_rows: list[dict[str, Any]] = []
    decision_lookup: dict[tuple[str, str], dict[str, Any]] = {}

    compact_params = compact.CompactParams(
        max_positions=params.max_positions,
        max_tranches=params.max_tranches,
        target_universe_size=params.target_universe_size,
        cash_reserve_ratio=params.cash_reserve_ratio,
        max_new_positions_per_day=params.max_new_positions_per_day,
        max_adds_per_day=params.max_adds_per_day,
        capital=params.capital,
        round_lot=params.round_lot,
        min_trade_value=params.min_trade_value,
        commission_rate=params.commission_rate,
        stamp_duty_rate_sell=params.stamp_duty_rate_sell,
        slippage_bps=params.slippage_bps,
        industry_max_positions=params.industry_max_positions,
    )

    for index in range(len(dates) - 1):
        signal_date = dates[index]
        fill_date = dates[index + 1]
        todays = feature_by_date[signal_date].copy()
        positions_before = copy.deepcopy(positions)
        positions_df = compact._positions_frame(positions, index, signal_date)
        todays = BacktestEngine._apply_positions_to_features(todays, positions_df)
        todays = BacktestEngine._apply_v2_holding_state(todays)
        price_today = todays.set_index("symbol")
        nav_before_trade = compact._portfolio_value(cash, positions, price_today)
        decision_scope = todays[todays["in_effective_universe"].astype(bool) | todays["symbol"].astype(str).isin(set(positions.keys()))].copy()
        regime = determine_market_regime(benchmark[benchmark["date"] <= signal_date], strategy)
        regime_name = _regime_name(regime)
        decisions = signal_engine.generate(
            decision_scope,
            positions_df,
            regime,
            safe_mode=False,
            account_state={
                "orders_degraded": False,
                "current_cash": params.capital * 100,
                "reserved_cash": 0.0,
                "latest_total_equity": max(nav_before_trade, params.capital),
                "current_invested_value": max(0.0, nav_before_trade - cash),
                "holdings_count": len(positions),
            },
        )
        for decision in decisions:
            decision_lookup[(signal_date, str(decision.get("symbol")))] = decision
        next_day = feature_by_date[fill_date].set_index("symbol")
        day_trade_rows_before = len(trade_rows)
        realized_by_symbol: defaultdict[str, float] = defaultdict(float)
        fee_by_symbol: defaultdict[str, float] = defaultdict(float)
        tax_by_symbol: defaultdict[str, float] = defaultdict(float)
        slippage_by_symbol: defaultdict[str, float] = defaultdict(float)
        traded_symbols: set[str] = set()
        replacement_pair_for_raw: dict[int, str] = {}

        # Exit evaluation before executing any exit.
        decisions_by_symbol = {str(item.get("symbol")): item for item in decisions}
        for symbol, position in positions.items():
            exit_rows.append(
                _exit_row(
                    date=signal_date,
                    params=params,
                    symbol=symbol,
                    position=position,
                    decision=decisions_by_symbol.get(symbol, {}),
                    regime_name=regime_name,
                    nav=nav_before_trade,
                    current_index=index,
                )
            )

        if params.partial_derisk_enabled:
            for symbol in list(positions.keys()):
                if symbol not in price_today.index:
                    continue
                row = price_today.loc[symbol].to_dict()
                position = positions[symbol]
                row.update(
                    {
                        "symbol": symbol,
                        "shares": position.shares,
                        "round_lot": params.round_lot,
                        "unrealized_pnl_pct": (_safe_float(row.get("close")) / position.avg_cost - 1.0) if position.avg_cost > 0 else 0.0,
                    }
                )
                derisk = evaluate_partial_derisk(row, {"round_lot": params.round_lot, "single_lot_hold_with_risk_flag": params.single_lot_hold_with_risk_flag})
                if derisk.get("action") in {"REDUCE", "SELL_ALL"}:
                    before_snapshot = _position_snapshot(positions, price_today, nav_before_trade).get(symbol, {})
                    cash, positions, raw_trade = _execute_partial_derisk_local(
                        signal_date=signal_date,
                        fill_date=fill_date,
                        symbol=symbol,
                        derisk=derisk,
                        params=params,
                        price_frame=next_day,
                        positions=positions,
                        cash=cash,
                    )
                    if raw_trade:
                        traded_symbols.add(symbol)
                        realized_by_symbol[symbol] += _safe_float(raw_trade.get("realized_pnl"))
                        fee_by_symbol[symbol] += _safe_float(raw_trade.get("fee"))
                        tax_by_symbol[symbol] += _safe_float(raw_trade.get("tax"))
                        slippage_by_symbol[symbol] += _safe_float(next_day.loc[symbol, "open"] - raw_trade.get("price")) * _safe_float(raw_trade.get("shares")) if symbol in next_day.index and "open" in next_day.columns else 0.0
                        trade_rows.append(
                            _trade_row(
                                raw=raw_trade,
                                params=params,
                                trade_id=f"T{len(trade_rows)+1:06d}",
                                decision_lookup=decision_lookup,
                                before=before_snapshot,
                                after_position=positions.get(symbol),
                                price_today=price_today,
                                next_day=next_day,
                                market_regime=regime_name,
                            )
                        )

        for decision in decisions:
            if decision.get("action_enum") not in SELL_ACTIONS:
                continue
            symbol = str(decision.get("symbol"))
            before_snapshot = _position_snapshot(positions, price_today, nav_before_trade).get(symbol, {})
            cash, positions, raw_trade = compact._execute_sell(
                fill_date=fill_date,
                decision=decision,
                params=compact_params,
                price_frame=next_day,
                positions=positions,
                cash=cash,
                nav=nav_before_trade,
            )
            if raw_trade:
                traded_symbols.add(symbol)
                realized_by_symbol[symbol] += _safe_float(raw_trade.get("realized_pnl"))
                fee_by_symbol[symbol] += _safe_float(raw_trade.get("fee"))
                tax_by_symbol[symbol] += _safe_float(raw_trade.get("tax"))
                trade_rows.append(
                    _trade_row(
                        raw=raw_trade,
                        params=params,
                        trade_id=f"T{len(trade_rows)+1:06d}",
                        decision_lookup=decision_lookup,
                        before=before_snapshot,
                        after_position=positions.get(symbol),
                        price_today=price_today,
                        next_day=next_day,
                        market_regime=regime_name,
                    )
                )

        holding_decisions = _holding_records(positions=positions, decisions=decisions, price_frame=price_today, current_index=index)
        selected, watch_records, raw_buy_count, replacement_plans = _select_buys_with_trace(
            signal_date=signal_date,
            buy_decisions=[item for item in decisions if item.get("action_enum") in BUY_ACTIONS],
            holding_decisions=holding_decisions,
            params=params,
            nav=nav_before_trade,
            cash=cash,
            positions=positions,
            regime=regime,
            current_index=index,
            month_replacement_count=month_replacements[signal_date[:7]],
            feature_by_date=feature_by_date,
            dates=dates,
            replacement_rows=replacement_rows,
        )
        selected_symbols = {str(item[0].get("symbol")) for item in selected}
        watch_by_symbol = {str(item.get("symbol")): str(item.get("reason_code")) for item in watch_records}
        repl_candidate_symbols = {str(plan["candidate"].get("symbol")) for plan in replacement_plans}
        raw_rank_map = {str(item.get("symbol")): rank for rank, item in enumerate(sorted([item for item in decisions if item.get("action_enum") in BUY_ACTIONS], key=_core_rank_key), start=1)}
        for decision in decisions:
            symbol = str(decision.get("symbol"))
            signal_rows.append(
                _signal_trace_row(
                    date=signal_date,
                    params=params,
                    decision=decision,
                    regime_name=regime_name,
                    nav=nav_before_trade,
                    cash=cash,
                    positions=positions,
                    selected=symbol in selected_symbols,
                    watch_reason=watch_by_symbol.get(symbol, ""),
                    replacement_candidate=symbol in repl_candidate_symbols,
                    replacement_triggered=False,
                    raw_rank=raw_rank_map.get(symbol),
                    daily_new_used=len(selected_symbols),
                )
            )

        for plan in replacement_plans[:1]:
            pair_id = f"R{len([row for row in trade_rows if row.get('replacement_pair_id')]) + 1:06d}"
            sell_symbol = str(plan["replacement"].get("simulated_sell_symbol"))
            before_sell = _position_snapshot(positions, price_today, nav_before_trade).get(sell_symbol, {})
            cash, positions, replacement_trades, _replacement_report = _execute_replacement_local(
                signal_date=signal_date,
                fill_date=fill_date,
                plan=plan,
                params=params,
                price_frame=next_day,
                positions=positions,
                cash=cash,
                nav=nav_before_trade,
            )
            if replacement_trades:
                month_replacements[signal_date[:7]] += 1
            for raw_trade in replacement_trades:
                symbol = str(raw_trade.get("symbol"))
                traded_symbols.add(symbol)
                replacement_pair_for_raw[id(raw_trade)] = pair_id
                realized_by_symbol[symbol] += _safe_float(raw_trade.get("realized_pnl"))
                fee_by_symbol[symbol] += _safe_float(raw_trade.get("fee"))
                tax_by_symbol[symbol] += _safe_float(raw_trade.get("tax"))
                before = before_sell if raw_trade.get("side") == "SELL" else _position_snapshot(positions_before, price_today, nav_before_trade).get(symbol, {})
                trade_rows.append(
                    _trade_row(
                        raw=raw_trade,
                        params=params,
                        trade_id=f"T{len(trade_rows)+1:06d}",
                        decision_lookup=decision_lookup,
                        before=before,
                        after_position=positions.get(symbol),
                        price_today=price_today,
                        next_day=next_day,
                        market_regime=regime_name,
                        replacement_pair_id=pair_id,
                    )
                )
            for row in replacement_rows:
                if row.get("date") == signal_date and row.get("candidate_symbol") == plan["candidate"].get("symbol") and row.get("replacement_triggered"):
                    row["replacement_pair_id"] = pair_id

        for decision, gate in selected:
            symbol = str(decision.get("symbol"))
            before_snapshot = _position_snapshot(positions, price_today, nav_before_trade).get(symbol, {})
            cash, positions, raw_trade, watch = compact._execute_buy(
                signal_date=signal_date,
                fill_date=fill_date,
                decision=decision,
                gate=gate,
                params=compact_params,
                price_frame=next_day,
                positions=positions,
                cash=cash,
                nav=nav_before_trade,
            )
            if raw_trade:
                traded_symbols.add(symbol)
                fee_by_symbol[symbol] += _safe_float(raw_trade.get("fee"))
                trade_rows.append(
                    _trade_row(
                        raw=raw_trade,
                        params=params,
                        trade_id=f"T{len(trade_rows)+1:06d}",
                        decision_lookup=decision_lookup,
                        before=before_snapshot,
                        after_position=positions.get(symbol),
                        price_today=price_today,
                        next_day=next_day,
                        market_regime=regime_name,
                    )
                )
            if watch:
                watch_by_symbol[symbol] = str(watch.get("reason_code", "UNKNOWN"))

        fill_nav = compact._portfolio_value(cash, positions, next_day)
        positions_after_snapshot = _position_snapshot(positions, next_day, fill_nav)
        symbols_for_pnl = set(positions_before) | set(positions) | traded_symbols
        day_position_total = 0.0
        for symbol in sorted(symbols_for_pnl):
            before = _position_snapshot(positions_before, price_today, nav_before_trade).get(symbol, {})
            after = positions_after_snapshot.get(symbol, {})
            position = positions.get(symbol) or positions_before.get(symbol)
            if not position:
                continue
            close = after.get("close", _safe_float(next_day.loc[symbol, "close"]) if symbol in next_day.index and "close" in next_day.columns else before.get("close", 0.0))
            prev_close = before.get("close", _safe_float(price_today.loc[symbol, "close"]) if symbol in price_today.index and "close" in price_today.columns else None)
            unrealized_end = after.get("unrealized_pnl", 0.0)
            unrealized_today = unrealized_end - previous_position_unrealized.get(symbol, 0.0)
            realized_today = realized_by_symbol[symbol]
            total_today = realized_today + unrealized_today
            day_position_total += total_today
            decision = decisions_by_symbol.get(symbol, {})
            position_rows.append(
                {
                    "date": signal_date,
                    "variant": params.variant_id,
                    "symbol": symbol,
                    "name": decision.get("name", symbol),
                    "bucket": after.get("bucket", before.get("bucket", position.bucket)),
                    "industry": after.get("industry", before.get("industry", position.industry)),
                    "market_regime": regime_name,
                    "shares": after.get("shares", 0.0),
                    "previous_shares": before.get("shares", 0.0),
                    "close": close,
                    "previous_close": prev_close,
                    "market_value": after.get("market_value", 0.0),
                    "previous_market_value": before.get("market_value", 0.0),
                    "position_weight": after.get("weight", 0.0),
                    "average_cost": after.get("avg_cost", 0.0),
                    "cost_basis": after.get("avg_cost", 0.0) * after.get("shares", 0.0),
                    "unrealized_pnl": unrealized_end,
                    "unrealized_pnl_pct": (close / after.get("avg_cost", 0.0) - 1.0) if after.get("avg_cost", 0.0) and close else 0.0,
                    "realized_pnl_today": realized_today,
                    "unrealized_pnl_today": unrealized_today,
                    "total_pnl_today": total_today,
                    "fees_allocated_today": fee_by_symbol[symbol],
                    "tax_allocated_today": tax_by_symbol[symbol],
                    "slippage_allocated_today": slippage_by_symbol[symbol],
                    "entry_date": after.get("entry_date", before.get("entry_date", "")),
                    "holding_days": max(0, index - int(position.entry_index)),
                    "last_buy_date": getattr(positions.get(symbol), "last_buy_date", before.get("last_buy_date", "")),
                    "last_sell_date": fill_date if symbol in traded_symbols and symbol not in positions else "",
                    "entry_signal": after.get("entry_signal", before.get("entry_signal", "")),
                    "latest_signal": decision.get("action_enum", ""),
                    "exit_signal_today": decision.get("action_enum", "") if decision.get("action_enum") in SELL_ACTIONS else "",
                    "replacement_sell_candidate": any(row.get("weakest_holding_symbol") == symbol and row.get("date") == signal_date for row in replacement_rows),
                    "replacement_buy_competitor": any(row.get("candidate_symbol") == symbol and row.get("date") == signal_date for row in replacement_rows),
                    "relative_strength": decision.get("relative_strength", decision.get("rs", "")),
                    "ma20": decision.get("ma20", ""),
                    "ma60": decision.get("ma60", ""),
                    "ma120": decision.get("ma120", ""),
                    "ma250": decision.get("ma250", ""),
                    "ma20_slope_10d": decision.get("ma20_slope_10d", ""),
                    "ma120_slope_20d": decision.get("ma120_slope_20d", ""),
                    "stock_q_blended": decision.get("stock_q_blended", ""),
                    "industry_q_blended": decision.get("industry_q_blended", ""),
                    "expected_edge_score": decision.get("expected_edge_score", ""),
                    "score_components_json": _json(decision.get("score_components") or {}),
                    "thesis_still_valid": not bool(decision.get("fundamental_break", False)) and _safe_float(decision.get("stock_q_blended"), 100.0) <= 60.0,
                    "fundamental_break": bool(decision.get("fundamental_break", False)),
                    "cycle_peak_trap": bool(decision.get("cycle_peak_trap", False)),
                    "costing_method": "FIFO_APPROX_AVG_COST",
                    "allocation_method": "TRADE_SYMBOL_DIRECT",
                    "trace_quality_flag": "PARTIALLY_SUPPORTED_AVG_COST_FIFO_APPROX" if symbol in traded_symbols else "FULLY_SUPPORTED_MARK_TO_MARKET",
                }
            )
        previous_position_unrealized = {symbol: row["unrealized_pnl"] for symbol, row in positions_after_snapshot.items()}

        day_trades = trade_rows[day_trade_rows_before:]
        fees_today = sum(_safe_float(row.get("commission")) for row in day_trades)
        tax_today = sum(_safe_float(row.get("stamp_tax")) for row in day_trades)
        slippage_today = sum(_safe_float(row.get("slippage")) for row in day_trades)
        turnover_today = sum(_safe_float(row.get("trade_value")) for row in day_trades)
        realized_today = sum(realized_by_symbol.values())
        unrealized_today = day_position_total - realized_today
        cash_ratio = cash / max(fill_nav, 1e-9)
        industry_weights: defaultdict[str, float] = defaultdict(float)
        bucket_weights: defaultdict[str, float] = defaultdict(float)
        for snapshot in positions_after_snapshot.values():
            industry_weights[str(snapshot.get("industry", ""))] += snapshot.get("market_value", 0.0) / max(fill_nav, 1e-9)
            bucket_weights[str(snapshot.get("bucket", ""))] += snapshot.get("market_value", 0.0) / max(fill_nav, 1e-9)
        buy_count = sum(1 for row in day_trades if str(row.get("side")) in {"BUY", "REPLACEMENT_BUY"})
        sell_count = sum(1 for row in day_trades if str(row.get("side")) in {"SELL", "SELL_ALL", "REPLACEMENT_SELL"})
        replacement_count = len({row.get("replacement_pair_id") for row in day_trades if row.get("replacement_pair_id")})
        signal_today = [row for row in signal_rows if row.get("date") == signal_date]
        reason_counts = Counter(row.get("primary_failure_reason", "") for row in signal_today if row.get("watch_only"))
        no_trade_reason = _infer_no_trade_reason(signal_today, len(positions), params.max_positions)
        daily_rows.append(
            {
                "date": signal_date,
                "variant": params.variant_id,
                "profile_name": PROFILE_NAME,
                "market_regime": regime_name,
                "nav": fill_nav,
                "previous_nav": previous_nav,
                "daily_return": fill_nav / previous_nav - 1.0 if previous_nav > 0 else None,
                "cumulative_return": fill_nav / params.capital - 1.0,
                "cash": cash,
                "cash_ratio": cash_ratio,
                "reserved_cash": params.cash_reserve_ratio * fill_nav,
                "gross_exposure": max(0.0, fill_nav - cash) / max(fill_nav, 1e-9),
                "net_exposure": max(0.0, fill_nav - cash) / max(fill_nav, 1e-9),
                "positions_count": len(positions),
                "max_positions": params.max_positions,
                "average_position_weight": ((fill_nav - cash) / max(fill_nav, 1e-9) / max(len(positions), 1)) if positions else 0.0,
                "largest_position_weight": max((row.get("weight", 0.0) for row in positions_after_snapshot.values()), default=0.0),
                "industry_count": len([key for key, value in industry_weights.items() if value > 0]),
                "largest_industry_weight": max(industry_weights.values(), default=0.0),
                "defensive_dividend_weight": bucket_weights.get("defensive_dividend", 0.0),
                "cyclical_rotation_weight": bucket_weights.get("cyclical_rotation", 0.0),
                "realized_pnl_today": realized_today,
                "unrealized_pnl_today": unrealized_today,
                "total_pnl_today": fill_nav - previous_nav,
                "fees_today": fees_today,
                "tax_today": tax_today,
                "slippage_today": slippage_today,
                "turnover_today": turnover_today,
                "buy_count_today": buy_count,
                "sell_count_today": sell_count,
                "reduce_count_today": sum(1 for row in day_trades if str(row.get("side")) == "REDUCE"),
                "replacement_count_today": replacement_count,
                "raw_buy_count_today": sum(1 for row in signal_today if row.get("raw_signal_generated")),
                "account_actionable_buy_count_today": sum(1 for row in signal_today if row.get("account_actionable")),
                "executable_buy_count_today": buy_count,
                "watch_only_count_today": sum(1 for row in signal_today if row.get("watch_only")),
                "top_watch_only_reason_today": reason_counts.most_common(1)[0][0] if reason_counts else "",
                "no_trade_reason_today": no_trade_reason if buy_count == 0 else "TRADE_EXECUTED",
                "risk_on_cash_drag_reason": _cash_reason_from_signal(signal_today, cash_ratio, params),
                "trace_quality_flag": "PARTIALLY_SUPPORTED_AVG_COST_FIFO_APPROX" if abs((fill_nav - previous_nav) - day_position_total) > 1.0 else "FULLY_SUPPORTED",
            }
        )
        previous_nav = fill_nav

    daily = pd.DataFrame(daily_rows)
    position = pd.DataFrame(position_rows)
    trades = pd.DataFrame(trade_rows)
    signal = pd.DataFrame(signal_rows)
    exit_trace = pd.DataFrame(exit_rows)
    replacement = pd.DataFrame(replacement_rows)
    drawdown = build_drawdown_attribution_trace(daily, position, exit_trace, replacement)
    risk_cash = build_risk_on_cash_trace(daily, signal, replacement, params)
    no_trade = build_no_trade_interval_trace(daily, signal, replacement)
    missing = build_missing_fields_report(daily, position, trades, signal, exit_trace, replacement, approximate=approximate)
    effective = {
        "profile_name": PROFILE_NAME,
        "variant": params.variant_id,
        "research_only": True,
        "auto_trading_approved": False,
        "broker_integration_enabled": False,
        "llm_decision_allowed": False,
        "writes_real_trades": False,
        "release_profile_replacement": False,
        "execution_mode": "next_bar",
        "costing_method": "FIFO_APPROX_AVG_COST",
        "params": params.__dict__,
    }
    return TraceBundle(daily, position, trades, signal, exit_trace, replacement, drawdown, risk_cash, no_trade, missing, effective)


def _execute_partial_derisk_local(**kwargs: Any) -> tuple[float, dict[str, Position], dict[str, Any] | None]:
    from scripts.run_50k_core_experiments import _execute_partial_derisk

    return _execute_partial_derisk(**kwargs)


def _execute_replacement_local(**kwargs: Any) -> tuple[float, dict[str, Position], list[dict[str, Any]], dict[str, Any] | None]:
    from scripts.run_50k_core_experiments import _execute_replacement

    return _execute_replacement(**kwargs)


def _select_buys_with_trace(
    *,
    signal_date: str,
    buy_decisions: list[dict[str, Any]],
    holding_decisions: list[dict[str, Any]],
    params: CoreParams,
    nav: float,
    cash: float,
    positions: dict[str, Position],
    regime: object,
    current_index: int,
    month_replacement_count: int,
    feature_by_date: dict[str, pd.DataFrame],
    dates: list[str],
    replacement_rows: list[dict[str, Any]],
) -> tuple[list[tuple[dict[str, Any], compact.GateResult]], list[dict[str, Any]], int, list[dict[str, Any]]]:
    selected: list[tuple[dict[str, Any], compact.GateResult]] = []
    watch_records: list[dict[str, Any]] = []
    replacement_plans: list[dict[str, Any]] = []
    new_buys_today = 0
    adds_today = 0
    industry_counts = Counter(position.industry for position in positions.values())
    defensive_count = sum(1 for position in positions.values() if position.bucket == "defensive_dividend")
    cyclical_count = sum(1 for position in positions.values() if position.bucket == "cyclical_rotation")
    scored: list[dict[str, Any]] = []
    for decision in buy_decisions:
        policy = _core_policy(params, nav=nav, regime=regime, industry_counts=industry_counts, cyclical_counts=cyclical_count)
        decision.update(compute_50k_expected_edge_score(decision, policy))
        scored.append(decision)
    ranked = sorted(scored, key=_core_rank_key)
    new_seen = 0
    for decision in ranked:
        action_type = "NEW_BUY" if _safe_int(decision.get("current_position_tranches")) <= 0 and _safe_int(decision.get("current_shares")) <= 0 else "ADD"
        bucket = str(decision.get("bucket", ""))
        reason = ""
        if action_type == "NEW_BUY":
            new_seen += 1
            if new_seen > params.target_universe_size:
                reason = "WATCH_ONLY_CORE_RANK_OUT"
        if not reason and decision.get("structural_lot_block"):
            reason = "WATCH_ONLY_STRUCTURAL_LOT_BLOCK"
        regime_name = _regime_name(regime)
        if not reason and bucket == "cyclical_rotation":
            if not params.cyclical_overlay_enabled or params.cyclical_max_positions <= 0:
                reason = "WATCH_ONLY_CYCLICAL_DISABLED"
            elif regime_name != "risk_on":
                reason = "WATCH_ONLY_CYCLICAL_NOT_RISK_ON"
            elif not decision.get("cyclical_executable", True):
                reason = "WATCH_ONLY_CYCLICAL_TREND_NOT_CONFIRMED"
            elif cyclical_count >= params.cyclical_max_positions:
                reason = "WATCH_ONLY_CYCLICAL_LIMIT"
            elif defensive_count < params.defensive_core_min_positions:
                reason = "WATCH_ONLY_DEFENSIVE_CORE_SHORTFALL"
        gate = None
        if not reason:
            gate = core_account_gate(
                decision,
                params,
                nav=nav,
                cash=cash,
                positions_count=len(positions) + new_buys_today,
                industry_position_count=int(industry_counts.get(str(decision.get("industry", "")), 0)),
                new_buys_today=new_buys_today,
                adds_today=adds_today,
                regime=regime_name,
            )
            if not gate.actionable:
                reason = gate.reason_code
        if reason:
            watch_records.append({"date": signal_date, "symbol": decision.get("symbol"), "reason_code": reason})
            portfolio_full = reason == "WATCH_ONLY_PORTFOLIO_FULL"
            if params.replacement_enabled and portfolio_full:
                replacement = evaluate_50k_core_replacement(
                    holding_decisions,
                    decision,
                    {
                        "enabled": True,
                        "advisory_only_for_live": True,
                        "backtest_switch_plan_enabled": True,
                        "mode": "backtest",
                        "portfolio_full": True,
                        "score_gap_threshold": params.score_gap_threshold,
                        "max_replacements_per_month": params.max_replacements_per_month,
                        "month_replacement_count": month_replacement_count,
                        "min_holding_days_before_replacement": params.min_holding_days_before_replacement,
                        "industry_max_positions": params.industry_max_positions,
                        "industry_position_counts": dict(industry_counts),
                        "account_equity": nav,
                        "max_single_stock_weight": params.max_single_stock_weight,
                        "round_lot": params.round_lot,
                        "commission_rate": params.commission_rate,
                        "stamp_duty_rate_sell": params.stamp_duty_rate_sell,
                    },
                )
                pair_id = f"R{len(replacement_rows)+1:06d}" if replacement.get("triggered") else ""
                replacement_rows.append(
                    _replacement_trace_row(
                        date=signal_date,
                        params=params,
                        candidate=decision,
                        holding_decisions=holding_decisions,
                        replacement=replacement,
                        portfolio_full=True,
                        month_count=month_replacement_count,
                        feature_by_date=feature_by_date,
                        dates=dates,
                        pair_id=pair_id,
                    )
                )
                if replacement.get("triggered"):
                    replacement_plans.append({"date": signal_date, "candidate": decision, "replacement": replacement})
            continue
        assert gate is not None
        selected.append((decision, gate))
        if action_type == "NEW_BUY":
            new_buys_today += 1
            industry_counts[str(decision.get("industry", ""))] += 1
            if bucket == "defensive_dividend":
                defensive_count += 1
            if bucket == "cyclical_rotation":
                cyclical_count += 1
        else:
            adds_today += 1
    return selected, watch_records, len(ranked), replacement_plans


def _infer_no_trade_reason(signal_today: list[dict[str, Any]], positions_count: int, max_positions: int) -> str:
    if not signal_today:
        return "NO_SIGNAL_TRACE"
    raw = [row for row in signal_today if row.get("raw_signal_generated")]
    if not raw:
        return "NO_RAW_SIGNAL"
    failures = Counter(row.get("stage_failed") for row in raw if row.get("stage_failed") != "NONE")
    if positions_count >= max_positions and failures.get("PORTFOLIO_FULL", 0) >= max(1, len(raw) // 2):
        return "PORTFOLIO_FULL"
    return failures.most_common(1)[0][0] if failures else "UNKNOWN"


def _cash_reason_from_signal(signal_today: list[dict[str, Any]], cash_ratio: float, params: CoreParams) -> str:
    if cash_ratio <= params.target_cash_ratio + 1e-12:
        return "CASH_RATIO_WITHIN_TARGET"
    raw = [row for row in signal_today if row.get("raw_signal_generated")]
    if not raw:
        return "NO_RAW_SIGNAL"
    actionable = [row for row in raw if row.get("account_actionable")]
    if not actionable:
        failures = Counter(row.get("stage_failed") for row in raw)
        if failures.get("PORTFOLIO_FULL"):
            return "PORTFOLIO_FULL"
        if failures.get("LOT_FIT_BLOCK") or failures.get("SINGLE_NAME_CAP_BLOCK"):
            return "LOT_FIT_BLOCK"
        if failures.get("INDUSTRY_CONCENTRATION"):
            return "INDUSTRY_CONCENTRATION"
        if failures.get("DAILY_NEW_LIMIT"):
            return "DAILY_NEW_LIMIT"
        if failures.get("MARKET_REGIME_BLOCK"):
            return "CYCLICAL_DISABLED_OR_BLOCKED"
        return "NO_ACCOUNT_ACTIONABLE_SIGNAL"
    return "UNKNOWN"


def build_drawdown_attribution_trace(daily: pd.DataFrame, position: pd.DataFrame, exit_trace: pd.DataFrame, replacement: pd.DataFrame) -> pd.DataFrame:
    if daily.empty:
        return pd.DataFrame()
    nav = pd.to_numeric(daily["nav"], errors="coerce")
    running = nav.cummax()
    dd = nav / running - 1.0
    trough_idx = int(dd.idxmin())
    start_nav = running.iloc[trough_idx]
    nav_to_trough = nav.iloc[: trough_idx + 1]
    start_candidates = nav_to_trough.index[(nav_to_trough >= start_nav - 1e-9)].tolist()
    start_idx = int(start_candidates[-1]) if start_candidates else 0
    recovery_idx = None
    for idx in range(trough_idx + 1, len(daily)):
        if nav.iloc[idx] >= start_nav - 1e-9:
            recovery_idx = idx
            break
    start_date = str(daily.loc[start_idx, "date"])
    trough_date = str(daily.loc[trough_idx, "date"])
    recovery_date = str(daily.loc[recovery_idx, "date"]) if recovery_idx is not None else ""
    interval = daily.iloc[start_idx : trough_idx + 1]
    dates = set(interval["date"].astype(str))
    pos = position[position["date"].astype(str).isin(dates)].copy() if not position.empty else pd.DataFrame()
    rows = []
    if pos.empty:
        return pd.DataFrame(
            [
                {
                    "drawdown_id": 1,
                    "start_date": start_date,
                    "trough_date": trough_date,
                    "recovery_date": recovery_date,
                    "max_drawdown": float(dd.iloc[trough_idx]),
                    "date": "",
                    "symbol": "",
                    "trace_quality_flag": "MISSING_POSITION_PNL",
                }
            ]
        )
    grouped = pos.groupby(["symbol", "bucket", "industry"], dropna=False).agg(
        pnl_contribution_during_drawdown=("total_pnl_today", "sum"),
        realized_pnl_during_drawdown=("realized_pnl_today", "sum"),
        unrealized_pnl_during_drawdown=("unrealized_pnl_today", "sum"),
    )
    exits = exit_trace[exit_trace["date"].astype(str).isin(dates)] if not exit_trace.empty else pd.DataFrame()
    repl = replacement[replacement["date"].astype(str).isin(dates)] if not replacement.empty else pd.DataFrame()
    start_weights = pos[pos["date"].astype(str) == start_date].set_index("symbol").get("position_weight", _empty_series()).to_dict()
    trough_weights = pos[pos["date"].astype(str) == trough_date].set_index("symbol").get("position_weight", _empty_series()).to_dict()
    for (symbol, bucket, industry), agg in grouped.iterrows():
        symbol_exits = exits[exits["symbol"].astype(str) == str(symbol)] if not exits.empty and "symbol" in exits.columns else pd.DataFrame()
        rows.append(
            {
                "drawdown_id": 1,
                "start_date": start_date,
                "trough_date": trough_date,
                "recovery_date": recovery_date,
                "max_drawdown": float(dd.iloc[trough_idx]),
                "date": trough_date,
                "symbol": symbol,
                "bucket": bucket,
                "industry": industry,
                "market_regime": str(interval["market_regime"].mode().iloc[0]) if "market_regime" in interval and not interval.empty else "",
                "position_weight_at_start": start_weights.get(symbol, 0.0),
                "position_weight_at_trough": trough_weights.get(symbol, 0.0),
                "pnl_contribution_during_drawdown": float(agg["pnl_contribution_during_drawdown"]),
                "return_contribution_during_drawdown": float(agg["pnl_contribution_during_drawdown"]) / max(float(daily.loc[start_idx, "nav"]), 1e-9),
                "realized_pnl_during_drawdown": float(agg["realized_pnl_during_drawdown"]),
                "unrealized_pnl_during_drawdown": float(agg["unrealized_pnl_during_drawdown"]),
                "exit_signal_count_during_drawdown": int((symbol_exits.get("selected_exit_action", _empty_series("object")).astype(str) != "HOLD").sum()) if not symbol_exits.empty else 0,
                "exit_triggered_during_drawdown": bool((symbol_exits.get("selected_exit_action", _empty_series("object")).astype(str) != "HOLD").any()) if not symbol_exits.empty else False,
                "replacement_candidate_count_during_drawdown": int(((repl.get("candidate_symbol", _empty_series("object")).astype(str) == str(symbol)) | (repl.get("weakest_holding_symbol", _empty_series("object")).astype(str) == str(symbol))).sum()) if not repl.empty else 0,
                "replacement_triggered_during_drawdown": bool((repl.get("replacement_triggered", _empty_series()).astype(bool)).any()) if not repl.empty else False,
                "missed_exit_candidate": bool(symbol_exits.get("missed_exit_candidate", _empty_series()).astype(bool).any()) if not symbol_exits.empty else False,
                "missed_replacement_candidate": bool((repl.get("replacement_triggered", _empty_series()).astype(bool) == False).any()) if not repl.empty else False,
                "trace_quality_flag": "PARTIALLY_SUPPORTED_AVG_COST_FIFO_APPROX",
            }
        )
    return pd.DataFrame(rows)


def build_risk_on_cash_trace(daily: pd.DataFrame, signal: pd.DataFrame, replacement: pd.DataFrame, params: CoreParams) -> pd.DataFrame:
    if daily.empty:
        return pd.DataFrame()
    rows = []
    for day in daily.to_dict(orient="records"):
        if str(day.get("market_regime")) != "risk_on":
            continue
        date = str(day["date"])
        sig = signal[signal["date"].astype(str) == date] if not signal.empty else pd.DataFrame()
        raw = sig[sig.get("raw_signal_generated", _empty_series()).astype(bool)] if not sig.empty else pd.DataFrame()
        top = raw.sort_values("expected_edge_score", ascending=False).iloc[0].to_dict() if not raw.empty and "expected_edge_score" in raw.columns else {}
        repl = replacement[replacement["date"].astype(str) == date] if not replacement.empty else pd.DataFrame()
        reason = day.get("risk_on_cash_drag_reason", "UNKNOWN")
        reason = reason if reason in CASH_REASON_ENUM else "UNKNOWN"
        rows.append(
            {
                "date": date,
                "variant": day.get("variant"),
                "market_regime": day.get("market_regime"),
                "cash_ratio": day.get("cash_ratio"),
                "gross_exposure": day.get("gross_exposure"),
                "positions_count": day.get("positions_count"),
                "max_positions": day.get("max_positions"),
                "raw_buy_count": len(raw),
                "account_actionable_buy_count": int(raw.get("account_actionable", _empty_series()).astype(bool).sum()) if not raw.empty else 0,
                "portfolio_actionable_buy_count": int(raw.get("portfolio_actionable", _empty_series()).astype(bool).sum()) if not raw.empty else 0,
                "executable_buy_count": int(raw.get("executable", _empty_series()).astype(bool).sum()) if not raw.empty else 0,
                "watch_only_count": int(raw.get("watch_only", _empty_series()).astype(bool).sum()) if not raw.empty else 0,
                "replacement_candidate_count": int(len(repl)),
                "replacement_triggered_count": int(repl.get("replacement_triggered", _empty_series()).astype(bool).sum()) if not repl.empty else 0,
                "top_expected_edge_candidate": top.get("symbol", ""),
                "top_expected_edge_score": top.get("expected_edge_score", ""),
                "top_candidate_failure_reason": top.get("stage_failed", ""),
                "reason_cash_not_deployed": reason,
                "deployable_cash_estimate": max(0.0, _safe_float(day.get("cash")) - params.target_cash_ratio * _safe_float(day.get("nav"))),
                "target_cash_ratio": params.target_cash_ratio,
                "cash_gap_to_target": _safe_float(day.get("cash_ratio")) - params.target_cash_ratio,
                "trace_quality_flag": "FULLY_SUPPORTED_FROM_SIGNAL_TRACE",
            }
        )
    return pd.DataFrame(rows)


def build_no_trade_interval_trace(daily: pd.DataFrame, signal: pd.DataFrame, replacement: pd.DataFrame) -> pd.DataFrame:
    if daily.empty:
        return pd.DataFrame()
    intervals: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []
    interval_id = 1
    for row in daily.to_dict(orient="records"):
        if _safe_int(row.get("buy_count_today")) == 0:
            current.append(row)
            continue
        if current:
            intervals.append(_interval_row(interval_id, current, signal, replacement))
            interval_id += 1
            current = []
    if current:
        intervals.append(_interval_row(interval_id, current, signal, replacement))
    return pd.DataFrame(intervals)


def _interval_row(interval_id: int, rows: list[dict[str, Any]], signal: pd.DataFrame, replacement: pd.DataFrame) -> dict[str, Any]:
    dates = [str(row["date"]) for row in rows]
    sig = signal[signal["date"].astype(str).isin(set(dates))] if not signal.empty else pd.DataFrame()
    raw = sig[sig.get("raw_signal_generated", _empty_series()).astype(bool)] if not sig.empty else pd.DataFrame()
    repl = replacement[replacement["date"].astype(str).isin(set(dates))] if not replacement.empty else pd.DataFrame()
    failures = Counter(raw.get("stage_failed", _empty_series("object")).astype(str).tolist()) if not raw.empty else Counter()
    best = raw.sort_values("expected_edge_score", ascending=False).iloc[0].to_dict() if not raw.empty and "expected_edge_score" in raw.columns else {}
    regimes = Counter(str(row.get("market_regime", "")) for row in rows)
    return {
        "interval_id": interval_id,
        "start_date": dates[0],
        "end_date": dates[-1],
        "trading_days": len(rows),
        "months_covered": len({date[:7] for date in dates}),
        "dominant_market_regime": regimes.most_common(1)[0][0] if regimes else "",
        "avg_cash_ratio": sum(_safe_float(row.get("cash_ratio")) for row in rows) / max(len(rows), 1),
        "avg_exposure": sum(_safe_float(row.get("gross_exposure")) for row in rows) / max(len(rows), 1),
        "avg_positions_count": sum(_safe_float(row.get("positions_count")) for row in rows) / max(len(rows), 1),
        "raw_buy_days": int(raw["date"].nunique()) if not raw.empty else 0,
        "account_actionable_days": int(raw[raw.get("account_actionable", _empty_series()).astype(bool)]["date"].nunique()) if not raw.empty else 0,
        "executable_buy_days": int(raw[raw.get("executable", _empty_series()).astype(bool)]["date"].nunique()) if not raw.empty else 0,
        "watch_only_days": int(raw[raw.get("watch_only", _empty_series()).astype(bool)]["date"].nunique()) if not raw.empty else 0,
        "replacement_candidate_days": int(repl["date"].nunique()) if not repl.empty else 0,
        "top_failure_reasons_json": _json(dict(failures.most_common(8))),
        "best_candidate_symbol_during_interval": best.get("symbol", ""),
        "best_candidate_score_during_interval": best.get("expected_edge_score", ""),
        "reason_no_trade_summary": failures.most_common(1)[0][0] if failures else "NO_RAW_SIGNAL",
        "trace_quality_flag": "FULLY_SUPPORTED_FROM_SIGNAL_TRACE",
    }


def build_missing_fields_report(
    daily: pd.DataFrame,
    position: pd.DataFrame,
    trades: pd.DataFrame,
    signal: pd.DataFrame,
    exit_trace: pd.DataFrame,
    replacement: pd.DataFrame,
    *,
    approximate: bool,
) -> dict[str, Any]:
    missing: dict[str, Any] = {
        "research_only": True,
        "approximate_historical_universe": bool(approximate),
        "critical_missing": [],
        "partial_limitations": [
            "lot_level_cost_basis: unavailable; using FIFO_APPROX_AVG_COST",
            "fee_allocation: allocated directly by trade symbol, not broker lot ledger",
            "thesis_still_valid: heuristic from available fundamental fields",
            "exit_rule_origin: selected action from signal engine plus trace heuristics",
        ],
        "tables": {},
    }
    required = {
        "daily_portfolio_ledger": ["date", "nav", "previous_nav", "daily_return", "cash", "cash_ratio"],
        "daily_position_pnl": ["date", "symbol", "shares", "market_value", "total_pnl_today"],
        "trade_ledger": ["trade_id", "date", "symbol", "side", "shares", "cash_before", "cash_after"],
        "signal_execution_trace": ["date", "symbol", "stage_failed", "raw_signal_generated"],
        "exit_rule_trace": ["date", "symbol", "trend_stop_triggered", "would_have_triggered_trend_stop"],
        "replacement_candidate_trace": ["date", "candidate_symbol", "diagnostic_only"],
    }
    frames = {
        "daily_portfolio_ledger": daily,
        "daily_position_pnl": position,
        "trade_ledger": trades,
        "signal_execution_trace": signal,
        "exit_rule_trace": exit_trace,
        "replacement_candidate_trace": replacement,
    }
    for name, cols in required.items():
        frame = frames[name]
        missing_cols = [col for col in cols if col not in frame.columns]
        missing["tables"][name] = {"rows": int(len(frame)), "missing_columns": missing_cols}
        if missing_cols:
            missing["critical_missing"].extend(f"{name}.{col}" for col in missing_cols)
    return missing


def write_trace_outputs(bundle: TraceBundle, output_dir: str | Path = DEFAULT_OUTPUT_DIR, *, strict: bool = False, allow_missing: bool = True) -> dict[str, Any]:
    out = resolve_path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    if strict and bundle.trace_missing_fields.get("critical_missing"):
        raise RuntimeError(f"strict trace generation failed; missing={bundle.trace_missing_fields['critical_missing']}")
    if bundle.trace_missing_fields.get("critical_missing") and not allow_missing:
        raise RuntimeError("trace generation has missing fields; rerun with --allow-missing or fix instrumentation")
    bundle.daily_portfolio_ledger.to_csv(out / "daily_portfolio_ledger.csv", index=False)
    bundle.daily_position_pnl.to_csv(out / "daily_position_pnl.csv", index=False)
    bundle.trade_ledger.to_csv(out / "trade_ledger.csv", index=False)
    bundle.signal_execution_trace.to_csv(out / "signal_execution_trace.csv", index=False)
    bundle.exit_rule_trace.to_csv(out / "exit_rule_trace.csv", index=False)
    bundle.replacement_candidate_trace.to_csv(out / "replacement_candidate_trace.csv", index=False)
    bundle.drawdown_attribution_trace.to_csv(out / "drawdown_attribution_trace.csv", index=False)
    bundle.risk_on_cash_trace.to_csv(out / "risk_on_cash_trace.csv", index=False)
    bundle.no_trade_interval_trace.to_csv(out / "no_trade_interval_trace.csv", index=False)
    (out / "trace_missing_fields.json").write_text(json.dumps(bundle.trace_missing_fields, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    (out / "trace_effective_config.yml").write_text(yaml.safe_dump(bundle.trace_effective_config, allow_unicode=True, sort_keys=False), encoding="utf-8")
    _write_trace_data_quality(out / "trace_data_quality_report.md", bundle)
    # Placeholder summaries are overwritten by diagnose_50k_core_traces.py, but
    # generation writes auditable files for tests and strict artifact checks.
    _write_basic_trace_report(out / "trace_diagnostic_report.md", bundle)
    _write_drawdown_summary(out / "drawdown_attribution_summary.md", bundle.drawdown_attribution_trace)
    _write_risk_cash_summary(out / "risk_on_cash_trace_summary.md", bundle.risk_on_cash_trace)
    _write_no_trade_summary(out / "no_trade_interval_summary.md", bundle.no_trade_interval_trace)
    missing_outputs = [name for name in REQUIRED_TRACE_OUTPUTS if not (out / name).exists()]
    if missing_outputs:
        raise RuntimeError(f"missing trace outputs: {missing_outputs}")
    return {"output_dir": str(out), "rows": {name: info.get("rows") for name, info in bundle.trace_missing_fields.get("tables", {}).items()}}


def _write_trace_data_quality(path: Path, bundle: TraceBundle) -> None:
    missing = bundle.trace_missing_fields
    lines = [
        "# trace data quality report",
        "",
        "- research_only: true",
        "- auto_trading_approved: false",
        "- broker_integration_enabled: false",
        "- llm_decision_allowed: false",
        "- writes_real_trades: false",
        "- release_profile_replacement: false",
        f"- critical_missing_count: {len(missing.get('critical_missing', []))}",
        "",
        "## limitations",
        "",
    ]
    lines.extend(f"- {item}" for item in missing.get("partial_limitations", []))
    lines.extend(["", "## table coverage", ""])
    for name, info in missing.get("tables", {}).items():
        lines.append(f"- {name}: rows={info.get('rows')} missing_columns={info.get('missing_columns')}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_basic_trace_report(path: Path, bundle: TraceBundle) -> None:
    lines = [
        "# trace diagnostic report",
        "",
        "## Trace coverage summary",
        "",
        f"- daily_portfolio_ledger rows: {len(bundle.daily_portfolio_ledger)}",
        f"- daily_position_pnl rows: {len(bundle.daily_position_pnl)}",
        f"- trade_ledger rows: {len(bundle.trade_ledger)}",
        f"- signal_execution_trace rows: {len(bundle.signal_execution_trace)}",
        f"- exit_rule_trace rows: {len(bundle.exit_rule_trace)}",
        f"- replacement_candidate_trace rows: {len(bundle.replacement_candidate_trace)}",
        "",
        "## Safety statement",
        "",
        "research_only=true; auto_trading_approved=false; broker_integration_enabled=false; llm_decision_allowed=false; writes_real_trades=false; release_profile_replacement=false.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_drawdown_summary(path: Path, drawdown: pd.DataFrame) -> None:
    if drawdown.empty:
        path.write_text("# drawdown attribution summary\n\nNo drawdown trace rows.\n", encoding="utf-8")
        return
    top = drawdown.sort_values("pnl_contribution_during_drawdown").head(10) if "pnl_contribution_during_drawdown" in drawdown.columns else drawdown
    lines = [
        "# drawdown attribution summary",
        "",
        f"- start_date: {drawdown.iloc[0].get('start_date')}",
        f"- trough_date: {drawdown.iloc[0].get('trough_date')}",
        f"- recovery_date: {drawdown.iloc[0].get('recovery_date')}",
        f"- max_drawdown: {_safe_float(drawdown.iloc[0].get('max_drawdown')):.2%}",
        "",
        "## top loss symbols",
        "",
        top.to_markdown(index=False),
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_risk_cash_summary(path: Path, risk_cash: pd.DataFrame) -> None:
    if risk_cash.empty:
        path.write_text("# risk-on cash trace summary\n\nNo risk-on cash rows.\n", encoding="utf-8")
        return
    counts = risk_cash["reason_cash_not_deployed"].value_counts().to_dict()
    lines = [
        "# risk-on cash trace summary",
        "",
        f"- high_cash_risk_on_days: {int((pd.to_numeric(risk_cash['cash_gap_to_target'], errors='coerce') > 0).sum())}",
        f"- reason_counts: {counts}",
        "",
        "NO_RAW_SIGNAL now means no raw buy row was present in signal_execution_trace for that date, not merely a missing funnel field.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_no_trade_summary(path: Path, no_trade: pd.DataFrame) -> None:
    if no_trade.empty:
        path.write_text("# no-trade interval summary\n\nNo no-trade intervals.\n", encoding="utf-8")
        return
    longest = no_trade.sort_values("trading_days", ascending=False).iloc[0]
    lines = [
        "# no-trade interval summary",
        "",
        f"- longest_interval: {longest.get('start_date')} to {longest.get('end_date')}",
        f"- trading_days: {int(longest.get('trading_days'))}",
        f"- dominant_market_regime: {longest.get('dominant_market_regime')}",
        f"- reason_no_trade_summary: {longest.get('reason_no_trade_summary')}",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate research-only combined_v2_50k_core trace ledgers.")
    parser.add_argument("--variant", default=DEFAULT_REPAIR_BEST_VARIANT)
    parser.add_argument("--source", choices=["stage1", "repair"], default="repair")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--allow-missing", action="store_true")
    args = parser.parse_args(argv)
    params = _variant_params(args.source, args.variant)
    bundle = generate_trace_bundle(params)
    result = write_trace_outputs(bundle, args.output_dir, strict=args.strict, allow_missing=args.allow_missing or not args.strict)
    print(json.dumps({"variant": params.variant_id, **result}, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
