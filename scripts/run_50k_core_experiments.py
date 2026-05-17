#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import itertools
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
from scripts.audit_common import DEFAULT_END_DATE, DEFAULT_START_DATE, V2_HISTORY_DIR, load_audit_configs, load_benchmark_window, load_feature_window
from scripts.report_metadata import config_hash, data_hash, git_branch, git_commit, now_utc_iso, stable_hash
from src.execution.partial_derisk import evaluate_partial_derisk
from src.execution.replacement import evaluate_50k_core_replacement
from src.strategy.backtest_engine import BacktestEngine, Position
from src.strategy.regime import determine_market_regime
from src.strategy.score_50k_core import compute_50k_expected_edge_score
from src.strategy.signals import SignalEngine
from src.utils.config import load_yaml, resolve_path


CONFIG_PATH = "config/strategy_v2_50k_core.yml"
OUT_DIR = "reports/backtest/50k_core"
PROFILE_NAME = "combined_v2_50k_core"
BUY_ACTIONS = {"BUY_1", "BUY_2", "BUY_3"}
SELL_ACTIONS = {"REDUCE", "SELL_ALL"}
WATCH_REASON_RANK_OUT = "WATCH_ONLY_CORE_RANK_OUT"
WATCH_REASON_PORTFOLIO_FULL = "WATCH_ONLY_PORTFOLIO_FULL"
WATCH_REASON_CASH_RESERVED = "WATCH_ONLY_CASH_RESERVED"
WATCH_REASON_LOT_TOO_EXPENSIVE = "WATCH_ONLY_LOT_TOO_EXPENSIVE"
WATCH_REASON_DAILY_NEW_LIMIT = "WATCH_ONLY_DAILY_NEW_LIMIT"
WATCH_REASON_DAILY_ADD_LIMIT = "WATCH_ONLY_DAILY_ADD_LIMIT"
WATCH_REASON_INDUSTRY_CONCENTRATION = "WATCH_ONLY_INDUSTRY_CONCENTRATION"
WATCH_REASON_CYCLICAL_DISABLED = "WATCH_ONLY_CYCLICAL_DISABLED"
WATCH_REASON_CYCLICAL_NOT_RISK_ON = "WATCH_ONLY_CYCLICAL_NOT_RISK_ON"
WATCH_REASON_CYCLICAL_TREND = "WATCH_ONLY_CYCLICAL_TREND_NOT_CONFIRMED"
WATCH_REASON_CYCLICAL_LIMIT = "WATCH_ONLY_CYCLICAL_LIMIT"
WATCH_REASON_DEFENSIVE_CORE_SHORTFALL = "WATCH_ONLY_DEFENSIVE_CORE_SHORTFALL"
WATCH_REASON_STRUCTURAL_LOT_BLOCK = "WATCH_ONLY_STRUCTURAL_LOT_BLOCK"

REQUIRED_OUTPUTS = [
    "core_experiment_metrics.csv",
    "core_experiment_report.md",
    "core_best_candidate.yml",
    "core_observation_candidate.md",
    "core_neighborhood_robustness.md",
    "core_execution_funnel.csv",
    "core_attribution_summary.csv",
    "core_replacement_report.csv",
    "core_effective_config.yml",
    "core_warnings.json",
    "core_module_contribution_report.md",
]

DEFAULT_EVALUATION = {
    "annual_return_min_absolute": 0.05,
    "sharpe_min": 0.75,
    "max_drawdown_floor": -0.12,
    "total_trades_min": 20,
    "total_trades_max": 60,
    "executable_account_actionable_min": 0.80,
    "avg_cash_ratio_max_in_risk_on": 0.35,
    "largest_single_stock_pnl_contribution_max": 0.45,
    "largest_industry_pnl_contribution_max": 0.55,
    "neighboring_pass_count_min_excluding_best": 3,
    "cyclical_bucket_pnl_must_be_non_negative_unless_cyclical_disabled": True,
    "realized_pnl_must_be_materially_positive": True,
}


@dataclass(frozen=True)
class CoreParams:
    max_positions: int
    max_tranches: int
    target_universe_size: int
    cash_reserve_ratio: float
    max_single_stock_weight: float
    max_new_positions_per_day: int
    max_adds_per_day: int
    industry_max_positions: int
    defensive_core_min_positions: int
    cyclical_max_positions: int
    lot_notional_max_ratio_to_target_budget: float
    score_gap_threshold: float
    max_replacements_per_month: int
    risk_on_target_exposure: float
    neutral_target_exposure: float
    risk_off_target_exposure: float
    module_control: str = "current"
    replacement_enabled: bool = True
    cyclical_overlay_enabled: bool = True
    capital: float = 50_000.0
    round_lot: int = 100
    min_trade_value: float = 1_500.0
    commission_rate: float = 0.0003
    stamp_duty_rate_sell: float = 0.0005
    slippage_bps: float = 5.0
    min_holding_days_before_replacement: int = 40
    monthly_rebalance_review_enabled: bool = False
    target_cash_ratio: float = 0.35
    partial_derisk_enabled: bool = False
    single_lot_hold_with_risk_flag: bool = False
    repair_label: str = ""

    @property
    def variant_id(self) -> str:
        reserve = int(round(self.cash_reserve_ratio * 100))
        single = int(round(self.max_single_stock_weight * 100))
        lot = int(round(self.lot_notional_max_ratio_to_target_budget * 100))
        risk_on = int(round(self.risk_on_target_exposure * 100))
        neutral = int(round(self.neutral_target_exposure * 100))
        risk_off = int(round(self.risk_off_target_exposure * 100))
        repl = "rep1" if self.replacement_enabled else "rep0"
        cyc = "cyc1" if self.cyclical_overlay_enabled else "cyc0"
        base = (
            f"mp{self.max_positions}_tr{self.max_tranches}_tu{self.target_universe_size}"
            f"_cr{reserve}_sw{single}_ind{self.industry_max_positions}_def{self.defensive_core_min_positions}"
            f"_cy{self.cyclical_max_positions}_lot{lot}_gap{int(self.score_gap_threshold)}"
            f"_rpm{self.max_replacements_per_month}_ro{risk_on}_ne{neutral}_rf{risk_off}_{repl}_{cyc}_{self.module_control}"
        )
        return f"{base}_{self.repair_label}" if self.repair_label else base


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


def _safe_int(value: object, default: int = 0) -> int:
    return int(_safe_float(value, float(default)))


def _ratio_or_none(numerator: int | float, denominator: int | float) -> float | None:
    denominator = float(denominator)
    if denominator == 0:
        return None
    return float(numerator) / denominator


def _pct(value: Any) -> str:
    try:
        if value is None or pd.isna(value):
            return "None"
        return f"{float(value):.2%}"
    except (TypeError, ValueError):
        return "None"


def _out_path(name: str) -> Path:
    return resolve_path(Path(OUT_DIR) / name)


def _regime_name(regime: object) -> str:
    if isinstance(regime, dict):
        return str(regime.get("regime", ""))
    return str(regime)


def _regime_target_exposure(params: CoreParams, regime: object) -> float:
    name = _regime_name(regime)
    if name == "risk_on":
        return params.risk_on_target_exposure
    if name == "neutral":
        return params.neutral_target_exposure
    return params.risk_off_target_exposure


def _target_weight(params: CoreParams, regime: object) -> float:
    regime_cap = _regime_target_exposure(params, regime) / max(params.max_positions, 1)
    account_cap = (1.0 - params.cash_reserve_ratio) / max(params.max_positions, 1)
    return round(max(0.0, min(params.max_single_stock_weight, regime_cap, account_cap)), 6)


def _strategy_cfg(base: dict[str, Any], params: CoreParams) -> dict[str, Any]:
    strategy = copy.deepcopy(base)
    strategy["profile"] = PROFILE_NAME
    strategy["profile_name"] = PROFILE_NAME
    strategy["research_only"] = True
    controls = strategy.setdefault("control_overrides", {})
    controls["disable_high_dividend_supplement"] = params.module_control in {"disable_high_dividend_supplement", "disable_both"}
    controls["disable_trend_stop"] = params.module_control in {"disable_trend_stop", "disable_both"}
    strategy.setdefault("market_regime", {}).setdefault("max_total_position", {}).update(
        {
            "risk_on": params.risk_on_target_exposure,
            "neutral": params.neutral_target_exposure,
            "risk_off": params.risk_off_target_exposure,
        }
    )
    execution = strategy.setdefault("execution", {})
    execution.update(
        {
            "max_positions": 999,
            "equal_weight_target_universe_size": params.max_positions,
            "max_new_positions_per_day": 999,
            "max_adds_per_day": 999,
            "lot_aware_sizing": False,
            "pending_add_state": False,
            "duplicate_blocked_signal_suppression": False,
            "round_lot": 1,
            "min_trade_value": 0,
        }
    )
    tranche_weights = {1: _target_weight(params, "risk_on")}
    for bucket_cfg in strategy.get("buckets", {}).values():
        if isinstance(bucket_cfg, dict):
            bucket_cfg["tranche_weights"] = tranche_weights
            bucket_cfg["max_single_name_weight"] = params.max_single_stock_weight
    return strategy


def _account_cfg(base: dict[str, Any], params: CoreParams) -> dict[str, Any]:
    account = copy.deepcopy(base)
    account["profile_name"] = PROFILE_NAME
    account["account_profile"] = PROFILE_NAME
    account["research_only"] = True
    account["candidate_default"] = False
    account.setdefault("account", {}).update(
        {
            "initial_capital": params.capital,
            "current_cash": params.capital,
            "reserved_cash": 0,
            "latest_total_equity": params.capital,
        }
    )
    account.setdefault("execution", {}).update(
        {
            "round_lot": params.round_lot,
            "commission_rate": params.commission_rate,
            "stamp_duty_rate_sell": params.stamp_duty_rate_sell,
            "slippage_bps": params.slippage_bps,
            "execution_mode": "next_bar",
        }
    )
    account.setdefault("position_sizing", {}).update(
        {
            "max_tranches_per_stock": params.max_tranches,
            "tranche_weights": {1: _target_weight(params, "risk_on")},
            "max_single_stock_weight": params.max_single_stock_weight,
            "min_trade_value": params.min_trade_value,
        }
    )
    account.setdefault("portfolio_execution", {}).update(
        {
            "cash_reserve_ratio": params.cash_reserve_ratio,
            "industry_max_positions": params.industry_max_positions,
            "replacement": {
                "enabled": params.replacement_enabled,
                "score_threshold": params.score_gap_threshold,
                "advisory_only": True,
            },
        }
    )
    return account


def _core_policy(
    params: CoreParams,
    *,
    nav: float,
    regime: object,
    industry_counts: Counter[str],
    cyclical_counts: int = 0,
) -> dict[str, Any]:
    return {
        "account_equity": nav,
        "capital": params.capital,
        "cash_reserve_ratio": params.cash_reserve_ratio,
        "max_positions": params.max_positions,
        "round_lot": params.round_lot,
        "max_single_stock_weight": params.max_single_stock_weight,
        "lot_notional_max_ratio_to_target_budget": params.lot_notional_max_ratio_to_target_budget,
        "industry_max_positions": params.industry_max_positions,
        "industry_position_counts": dict(industry_counts),
        "market_regime": _regime_name(regime),
        "cyclical_max_positions": params.cyclical_max_positions if params.cyclical_overlay_enabled else 0,
        "cyclical_position_count": cyclical_counts,
    }


def core_account_gate(
    decision: dict[str, Any],
    params: CoreParams,
    *,
    nav: float,
    cash: float,
    positions_count: int,
    industry_position_count: int,
    new_buys_today: int,
    adds_today: int,
    regime: object,
) -> compact.GateResult:
    current_tranches = _safe_int(decision.get("current_position_tranches"))
    current_shares = _safe_int(decision.get("current_shares"))
    price = _safe_float(decision.get("close"))
    action_type = "NEW_BUY" if current_tranches <= 0 and current_shares <= 0 else "ADD"
    lot_notional = price * params.round_lot
    regime_name = _regime_name(regime)
    target_weight = _target_weight(params, regime_name)
    current_value = current_shares * price
    target_value = target_weight * nav
    target_order_value = max(0.0, target_value - current_value)
    investable_cash = max(0.0, cash - params.cash_reserve_ratio * nav)

    if action_type == "ADD" and params.max_adds_per_day <= 0:
        return compact.GateResult(False, WATCH_REASON_DAILY_ADD_LIMIT, target_weight, target_order_value, lot_notional, action_type)
    if action_type == "NEW_BUY" and positions_count >= params.max_positions:
        return compact.GateResult(False, WATCH_REASON_PORTFOLIO_FULL, target_weight, target_order_value, lot_notional, action_type)
    daily_new_limit = params.max_new_positions_per_day
    if (
        params.monthly_rebalance_review_enabled
        and regime_name == "risk_on"
        and nav > 0
        and cash / nav > params.target_cash_ratio + 1e-12
    ):
        daily_new_limit += 1
    if action_type == "NEW_BUY" and new_buys_today >= daily_new_limit:
        return compact.GateResult(False, WATCH_REASON_DAILY_NEW_LIMIT, target_weight, target_order_value, lot_notional, action_type)
    if action_type == "ADD" and adds_today >= params.max_adds_per_day:
        return compact.GateResult(False, WATCH_REASON_DAILY_ADD_LIMIT, target_weight, target_order_value, lot_notional, action_type)
    if action_type == "NEW_BUY" and industry_position_count >= params.industry_max_positions:
        return compact.GateResult(False, WATCH_REASON_INDUSTRY_CONCENTRATION, target_weight, target_order_value, lot_notional, action_type)
    if price <= 0 or lot_notional <= 0:
        return compact.GateResult(False, "WATCH_ONLY_ACCOUNT_INFEASIBLE", target_weight, target_order_value, lot_notional, action_type)
    if lot_notional > nav * params.max_single_stock_weight + 1e-9:
        return compact.GateResult(False, WATCH_REASON_STRUCTURAL_LOT_BLOCK, target_weight, target_order_value, lot_notional, action_type)
    if lot_notional > target_order_value + 1e-9:
        return compact.GateResult(False, WATCH_REASON_LOT_TOO_EXPENSIVE, target_weight, target_order_value, lot_notional, action_type)
    if lot_notional * (1.0 + params.commission_rate) > investable_cash + 1e-9:
        return compact.GateResult(False, WATCH_REASON_CASH_RESERVED, target_weight, target_order_value, lot_notional, action_type)
    return compact.GateResult(True, "", target_weight, target_order_value, lot_notional, action_type)


def _watch_record(date: str, decision: dict[str, Any], reason_code: str, gate: compact.GateResult | None = None) -> dict[str, Any]:
    components = decision.get("score_components") or {}
    return {
        "date": date,
        "variant": decision.get("variant"),
        "symbol": decision.get("symbol"),
        "ts_code": decision.get("symbol"),
        "name": decision.get("name"),
        "bucket": decision.get("bucket"),
        "industry": decision.get("industry"),
        "intended_action": decision.get("action_enum"),
        "intended_signal_level": decision.get("signal_level", decision.get("action_enum")),
        "reason_code": reason_code,
        "expected_edge_score": decision.get("expected_edge_score"),
        "lot_fit_status": decision.get("lot_fit_status"),
        "lot_notional": decision.get("lot_notional", gate.lot_notional if gate else 0.0),
        "target_position_budget": decision.get("target_position_budget"),
        "structural_lot_block": decision.get("structural_lot_block", False),
        "score_components": json.dumps(components, ensure_ascii=False, sort_keys=True),
        "target_weight": gate.target_weight if gate else 0.0,
        "target_order_value": gate.target_order_value if gate else 0.0,
    }


def _core_rank_key(decision: dict[str, Any]) -> tuple:
    action_type = "NEW_BUY" if _safe_int(decision.get("current_position_tranches")) <= 0 and _safe_int(decision.get("current_shares")) <= 0 else "ADD"
    held_priority = 0 if action_type == "ADD" else 1
    structural = 1 if decision.get("structural_lot_block") else 0
    cyclical = 1 if str(decision.get("bucket")) == "cyclical_rotation" else 0
    return (
        held_priority,
        structural,
        cyclical,
        -_safe_float(decision.get("expected_edge_score")),
        compact._stock_quantile(decision),
        str(decision.get("industry", "")),
        str(decision.get("symbol", "")),
    )


def _holding_records(
    *,
    positions: dict[str, Position],
    decisions: list[dict[str, Any]],
    price_frame: pd.DataFrame,
    current_index: int,
) -> list[dict[str, Any]]:
    by_symbol = {str(item.get("symbol")): item for item in decisions}
    rows: list[dict[str, Any]] = []
    for symbol, position in positions.items():
        row = copy.deepcopy(by_symbol.get(symbol, {}))
        price = _safe_float(price_frame.loc[symbol, "close"]) if symbol in price_frame.index and "close" in price_frame.columns else position.last_fill_price
        row.update(
            {
                "symbol": symbol,
                "industry": position.industry,
                "bucket": position.bucket,
                "shares": position.shares,
                "avg_cost": position.avg_cost,
                "close": price,
                "holding_days": max(0, current_index - position.entry_index),
                "unrealized_pnl_pct": (price / position.avg_cost - 1.0) if position.avg_cost > 0 and price > 0 else 0.0,
                "thesis_still_valid": not bool(row.get("fundamental_break", False)) and _safe_float(row.get("stock_q_blended"), 100.0) <= 60.0,
            }
        )
        if "expected_edge_score" not in row:
            row["expected_edge_score"] = _safe_float(row.get("priority_score", row.get("final_score")), 0.0)
        rows.append(row)
    return rows


def _apply_core_buy_selection(
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
        score = compute_50k_expected_edge_score(decision, policy)
        decision.update(score)
        scored.append(decision)
    ranked = sorted(scored, key=_core_rank_key)
    new_seen = 0
    for decision in ranked:
        action_type = "NEW_BUY" if _safe_int(decision.get("current_position_tranches")) <= 0 and _safe_int(decision.get("current_shares")) <= 0 else "ADD"
        bucket = str(decision.get("bucket", ""))
        if action_type == "NEW_BUY":
            new_seen += 1
            if new_seen > params.target_universe_size:
                watch_records.append(_watch_record(signal_date, decision, WATCH_REASON_RANK_OUT))
                continue
        if decision.get("structural_lot_block"):
            watch_records.append(_watch_record(signal_date, decision, WATCH_REASON_STRUCTURAL_LOT_BLOCK))
            continue
        regime_name = _regime_name(regime)
        if bucket == "cyclical_rotation":
            if not params.cyclical_overlay_enabled or params.cyclical_max_positions <= 0:
                watch_records.append(_watch_record(signal_date, decision, WATCH_REASON_CYCLICAL_DISABLED))
                continue
            if regime_name != "risk_on":
                watch_records.append(_watch_record(signal_date, decision, WATCH_REASON_CYCLICAL_NOT_RISK_ON))
                continue
            if not decision.get("cyclical_executable", True):
                watch_records.append(_watch_record(signal_date, decision, WATCH_REASON_CYCLICAL_TREND))
                continue
            if cyclical_count >= params.cyclical_max_positions:
                watch_records.append(_watch_record(signal_date, decision, WATCH_REASON_CYCLICAL_LIMIT))
                continue
            if defensive_count < params.defensive_core_min_positions:
                watch_records.append(_watch_record(signal_date, decision, WATCH_REASON_DEFENSIVE_CORE_SHORTFALL))
                continue
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
            watch_records.append(_watch_record(signal_date, decision, gate.reason_code, gate))
            if gate.reason_code == WATCH_REASON_PORTFOLIO_FULL and params.replacement_enabled:
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
                if replacement.get("triggered"):
                    replacement_plans.append({"date": signal_date, "candidate": decision, "replacement": replacement})
            continue
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


def _prepare_feature_by_date(features: pd.DataFrame, configs: dict[str, Any]) -> tuple[dict[str, pd.DataFrame], bool]:
    return compact._prepare_feature_by_date(features, configs)


def _execute_replacement(
    *,
    signal_date: str,
    fill_date: str,
    plan: dict[str, Any],
    params: CoreParams,
    price_frame: pd.DataFrame,
    positions: dict[str, Position],
    cash: float,
    nav: float,
) -> tuple[float, dict[str, Position], list[dict[str, Any]], dict[str, Any] | None]:
    replacement = plan["replacement"]
    sell_symbol = str(replacement.get("simulated_sell_symbol"))
    buy_decision = plan["candidate"]
    if sell_symbol not in positions:
        return cash, positions, [], None
    sell_decision = {
        "date": signal_date,
        "symbol": sell_symbol,
        "name": sell_symbol,
        "industry": positions[sell_symbol].industry,
        "bucket": positions[sell_symbol].bucket,
        "action_enum": "SELL_ALL",
        "signal_level": "SELL_ALL",
    }
    trades: list[dict[str, Any]] = []
    cash, positions, sell_trade = compact._execute_sell(
        fill_date=fill_date,
        decision=sell_decision,
        params=compact.CompactParams(
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
        ),
        price_frame=price_frame,
        positions=positions,
        cash=cash,
        nav=nav,
    )
    if sell_trade:
        sell_trade["replacement_simulated"] = True
        trades.append(sell_trade)
    gate = core_account_gate(
        buy_decision,
        params,
        nav=nav,
        cash=cash,
        positions_count=len(positions),
        industry_position_count=sum(1 for item in positions.values() if item.industry == str(buy_decision.get("industry"))),
        new_buys_today=0,
        adds_today=0,
        regime="risk_on",
    )
    cash, positions, buy_trade, _watch = compact._execute_buy(
        signal_date=signal_date,
        fill_date=fill_date,
        decision=buy_decision,
        gate=gate,
        params=compact.CompactParams(
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
        ),
        price_frame=price_frame,
        positions=positions,
        cash=cash,
        nav=nav,
    )
    if buy_trade:
        buy_trade["replacement_simulated"] = True
        trades.append(buy_trade)
    report = {
        "date": signal_date,
        "sell_symbol": sell_symbol,
        "buy_symbol": buy_decision.get("symbol"),
        "sell_industry": replacement.get("sell_industry"),
        "buy_industry": replacement.get("buy_industry"),
        "weakest_holding_score": replacement.get("weakest_holding_score"),
        "candidate_score": replacement.get("candidate_score"),
        "score_gap": replacement.get("score_gap"),
        "sell_reason": replacement.get("sell_reason"),
        "buy_reason": replacement.get("buy_reason"),
        "realized_pnl_from_sell": sell_trade.get("realized_pnl", 0.0) if sell_trade else 0.0,
        "estimated_cost": replacement.get("estimated_cost"),
        "portfolio_positions_before": len(positions) + (1 if buy_trade else 0),
        "portfolio_positions_after": len(positions),
    }
    return cash, positions, trades, report


def _execute_partial_derisk(
    *,
    signal_date: str,
    fill_date: str,
    symbol: str,
    derisk: dict[str, Any],
    params: CoreParams,
    price_frame: pd.DataFrame,
    positions: dict[str, Position],
    cash: float,
) -> tuple[float, dict[str, Position], dict[str, Any] | None]:
    if symbol not in positions or symbol not in price_frame.index:
        return cash, positions, None
    position = positions[symbol]
    sell_shares = float(derisk.get("sell_shares", 0.0))
    if str(derisk.get("action")) == "SELL_ALL":
        sell_shares = position.shares
    sell_shares = compact._round_down_lot(min(position.shares, sell_shares), params.round_lot)
    if sell_shares <= 0:
        return cash, positions, None
    fill_price, field = compact._fill_price(price_frame, symbol, params.slippage_bps / 10_000.0, "SELL")
    trade_value = sell_shares * fill_price
    fee = trade_value * params.commission_rate
    tax = trade_value * params.stamp_duty_rate_sell
    cash_before = cash
    cash += trade_value - fee - tax
    realized_pnl = trade_value - position.avg_cost * sell_shares - fee - tax
    position.shares -= sell_shares
    if position.shares <= 1e-9 or str(derisk.get("action")) == "SELL_ALL":
        positions.pop(symbol, None)
    else:
        position.current_shares = int(round(position.shares))
        position.last_fill_price = fill_price
        positions[symbol] = position
    return cash, positions, {
        "date": fill_date,
        "signal_date": signal_date,
        "symbol": symbol,
        "ts_code": symbol,
        "name": symbol,
        "industry": position.industry,
        "bucket": position.bucket,
        "side": "SELL",
        "action": derisk.get("action"),
        "signal_level": "PARTIAL_DERISK",
        "shares": sell_shares,
        "price": fill_price,
        "amount": trade_value,
        "fee": fee,
        "tax": tax,
        "cash_before": cash_before,
        "cash_after": cash,
        "target_weight": 0.0,
        "realized_pnl": realized_pnl,
        "fill_price_field": field,
        "execution_mode": "next_bar",
        "partial_derisk": True,
        "partial_derisk_reason": derisk.get("reason"),
    }


def _contribution_ratio(values: dict[str, float]) -> float:
    if not values:
        return 0.0
    denominator = sum(abs(value) for value in values.values())
    if denominator <= 0:
        return 0.0
    return max(abs(value) for value in values.values()) / denominator


def _attribution(
    *,
    trades: pd.DataFrame,
    positions: dict[str, Position],
    price_frame: pd.DataFrame,
) -> dict[str, Any]:
    symbol_pnl: dict[str, float] = defaultdict(float)
    industry_pnl: dict[str, float] = defaultdict(float)
    bucket_pnl: dict[str, float] = defaultdict(float)
    realized = 0.0
    if not trades.empty:
        for row in trades.to_dict(orient="records"):
            pnl = _safe_float(row.get("realized_pnl"))
            realized += pnl
            symbol_pnl[str(row.get("symbol"))] += pnl
            industry_pnl[str(row.get("industry"))] += pnl
            bucket_pnl[str(row.get("bucket"))] += pnl
    unrealized = 0.0
    for symbol, position in positions.items():
        price = _safe_float(price_frame.loc[symbol, "close"]) if symbol in price_frame.index and "close" in price_frame.columns else position.last_fill_price
        pnl = (price - position.avg_cost) * position.shares
        unrealized += pnl
        symbol_pnl[symbol] += pnl
        industry_pnl[position.industry] += pnl
        bucket_pnl[position.bucket] += pnl
    return {
        "largest_single_stock_pnl_contribution": _contribution_ratio(symbol_pnl),
        "largest_industry_pnl_contribution": _contribution_ratio(industry_pnl),
        "defensive_dividend_pnl": float(bucket_pnl.get("defensive_dividend", 0.0)),
        "cyclical_rotation_pnl": float(bucket_pnl.get("cyclical_rotation", 0.0)),
        "realized_pnl": float(realized),
        "unrealized_pnl": float(unrealized),
        "symbol_pnl": dict(symbol_pnl),
        "industry_pnl": dict(industry_pnl),
        "bucket_pnl": dict(bucket_pnl),
    }


def run_core_backtest(
    params: CoreParams,
    *,
    feature_by_date: dict[str, pd.DataFrame],
    benchmark: pd.DataFrame,
    configs: dict[str, Any],
) -> dict[str, Any]:
    strategy = _strategy_cfg(configs["v2_strategy"], params)
    account = _account_cfg(configs["account"], params)
    signal_engine = SignalEngine(strategy, configs["v2_universe"], account)
    dates = sorted(feature_by_date)
    cash = params.capital
    positions: dict[str, Position] = {}
    nav_records: list[dict[str, Any]] = []
    trades: list[dict[str, Any]] = []
    watch_records: list[dict[str, Any]] = []
    daily_rows: list[dict[str, Any]] = []
    replacement_rows: list[dict[str, Any]] = []
    month_replacements: Counter[str] = Counter()

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
        positions_df = compact._positions_frame(positions, index, signal_date)
        todays = BacktestEngine._apply_positions_to_features(todays, positions_df)
        todays = BacktestEngine._apply_v2_holding_state(todays)
        price_today = todays.set_index("symbol")
        nav = compact._portfolio_value(cash, positions, price_today)
        decision_scope = todays[todays["in_effective_universe"].astype(bool) | todays["symbol"].astype(str).isin(set(positions.keys()))].copy()
        regime = determine_market_regime(benchmark[benchmark["date"] <= signal_date], strategy)
        decisions = signal_engine.generate(
            decision_scope,
            positions_df,
            regime,
            safe_mode=False,
            account_state={
                "orders_degraded": False,
                "current_cash": params.capital * 100,
                "reserved_cash": 0.0,
                "latest_total_equity": max(nav, params.capital),
                "current_invested_value": max(0.0, nav - cash),
                "holdings_count": len(positions),
            },
        )
        next_day = feature_by_date[fill_date].set_index("symbol")
        day_trades_before = len(trades)

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
                derisk = evaluate_partial_derisk(
                    row,
                    {
                        "round_lot": params.round_lot,
                        "single_lot_hold_with_risk_flag": params.single_lot_hold_with_risk_flag,
                    },
                )
                if derisk.get("action") in {"REDUCE", "SELL_ALL"}:
                    cash, positions, derisk_trade = _execute_partial_derisk(
                        signal_date=signal_date,
                        fill_date=fill_date,
                        symbol=symbol,
                        derisk=derisk,
                        params=params,
                        price_frame=next_day,
                        positions=positions,
                        cash=cash,
                    )
                    if derisk_trade:
                        trades.append(derisk_trade)

        for decision in decisions:
            if decision.get("action_enum") not in SELL_ACTIONS:
                continue
            cash, positions, trade = compact._execute_sell(
                fill_date=fill_date,
                decision=decision,
                params=compact_params,
                price_frame=next_day,
                positions=positions,
                cash=cash,
                nav=nav,
            )
            if trade:
                trades.append(trade)

        holding_decisions = _holding_records(positions=positions, decisions=decisions, price_frame=price_today, current_index=index)
        selected, day_watch, raw_buy_count, replacement_plans = _apply_core_buy_selection(
            signal_date=signal_date,
            buy_decisions=[item for item in decisions if item.get("action_enum") in BUY_ACTIONS],
            holding_decisions=holding_decisions,
            params=params,
            nav=nav,
            cash=cash,
            positions=positions,
            regime=regime,
            current_index=index,
            month_replacement_count=month_replacements[signal_date[:7]],
        )
        watch_records.extend(day_watch)
        for plan in replacement_plans[:1]:
            cash, positions, replacement_trades, replacement_report = _execute_replacement(
                signal_date=signal_date,
                fill_date=fill_date,
                plan=plan,
                params=params,
                price_frame=next_day,
                positions=positions,
                cash=cash,
                nav=nav,
            )
            if replacement_trades:
                trades.extend(replacement_trades)
                month_replacements[signal_date[:7]] += 1
            if replacement_report:
                replacement_report["variant"] = params.variant_id
                replacement_rows.append(replacement_report)

        for decision, gate in selected:
            cash, positions, trade, watch = compact._execute_buy(
                signal_date=signal_date,
                fill_date=fill_date,
                decision=decision,
                gate=gate,
                params=compact_params,
                price_frame=next_day,
                positions=positions,
                cash=cash,
                nav=nav,
            )
            if trade:
                trades.append(trade)
            if watch:
                watch["variant"] = params.variant_id
                watch_records.append(watch)

        fill_nav = compact._portfolio_value(cash, positions, next_day)
        invested = max(0.0, fill_nav - cash)
        executed_today = trades[day_trades_before:]
        daily_rows.append(
            {
                "date": signal_date,
                "variant": params.variant_id,
                "market_regime": _regime_name(regime),
                "raw_buy_signal_count": raw_buy_count,
                "account_actionable_buy_count": len(selected) + len(replacement_plans[:1]),
                "watch_only_count": len(day_watch),
                "executable_buy_count": sum(1 for item in executed_today if item.get("side") == "BUY"),
                "cyclical_candidates": sum(1 for item in decisions if item.get("action_enum") in BUY_ACTIONS and item.get("bucket") == "cyclical_rotation"),
                "cyclical_executed_buys": sum(1 for item in executed_today if item.get("side") == "BUY" and item.get("bucket") == "cyclical_rotation"),
                "holdings_count": len(positions),
                "cash": cash,
                "nav": fill_nav,
                "cash_ratio": cash / max(fill_nav, 1e-9),
                "exposure": invested / max(fill_nav, 1e-9),
                "replacement_count": len(replacement_trades) // 2 if "replacement_trades" in locals() else 0,
            }
        )
        nav_records.append({"date": fill_date, "nav": fill_nav, "cash": cash, "exposure": invested / max(fill_nav, 1e-9), "holdings_count": len(positions)})

    nav_frame = pd.DataFrame(nav_records)
    trade_frame = pd.DataFrame(trades)
    daily = pd.DataFrame(daily_rows)
    watch = pd.DataFrame(watch_records)
    metrics = compact._metrics(nav_frame, trade_frame, params.capital)
    final_prices = feature_by_date[dates[-1]].set_index("symbol")
    attribution = _attribution(trades=trade_frame, positions=positions, price_frame=final_prices)
    reason_counts = Counter(watch.get("reason_code", pd.Series(dtype=str)).dropna().astype(str).tolist()) if not watch.empty else Counter()
    risk_on_daily = daily[daily.get("market_regime", pd.Series(dtype=str)) == "risk_on"] if not daily.empty else pd.DataFrame()
    executable_buy_count = int(metrics.get("buy_trades", 0))
    account_actionable = int(daily.get("account_actionable_buy_count", pd.Series(dtype=int)).sum()) if not daily.empty else 0
    payload = {
        "variant": params.variant_id,
        "profile": PROFILE_NAME,
        "research_only": True,
        "capital": params.capital,
        "round_lot": params.round_lot,
        "min_trade_value": params.min_trade_value,
        "max_positions": params.max_positions,
        "max_tranches": params.max_tranches,
        "target_universe_size": params.target_universe_size,
        "cash_reserve_ratio": params.cash_reserve_ratio,
        "max_single_stock_weight": params.max_single_stock_weight,
        "max_new_positions_per_day": params.max_new_positions_per_day,
        "max_adds_per_day": params.max_adds_per_day,
        "industry_max_positions": params.industry_max_positions,
        "cyclical_max_positions": params.cyclical_max_positions if params.cyclical_overlay_enabled else 0,
        "defensive_core_min_positions": params.defensive_core_min_positions,
        "lot_notional_max_ratio_to_target_budget": params.lot_notional_max_ratio_to_target_budget,
        "score_gap_threshold": params.score_gap_threshold,
        "max_replacements_per_month": params.max_replacements_per_month,
        "risk_on_target_exposure": params.risk_on_target_exposure,
        "neutral_target_exposure": params.neutral_target_exposure,
        "risk_off_target_exposure": params.risk_off_target_exposure,
        "module_control": params.module_control,
        "replacement_enabled": params.replacement_enabled,
        "cyclical_overlay_enabled": params.cyclical_overlay_enabled,
        "annual_return": metrics.get("annual_return", 0.0),
        "cumulative_return": metrics.get("cumulative_return", 0.0),
        "max_drawdown": metrics.get("max_drawdown", 0.0),
        "sharpe": metrics.get("sharpe", 0.0),
        "total_trades": metrics.get("total_trades", 0),
        "buy_trades": metrics.get("buy_trades", 0),
        "sell_trades": metrics.get("sell_trades", 0),
        "executable_buy_count": executable_buy_count,
        "account_actionable_buy_count": account_actionable,
        "executable_account_actionable_ratio": _ratio_or_none(executable_buy_count, account_actionable),
        "raw_buy_signal_count": int(daily.get("raw_buy_signal_count", pd.Series(dtype=int)).sum()) if not daily.empty else 0,
        "watch_only_count": int(daily.get("watch_only_count", pd.Series(dtype=int)).sum()) if not daily.empty else 0,
        "top_watch_only_reasons": dict(reason_counts.most_common(5)),
        "average_exposure": metrics.get("avg_daily_exposure", 0.0),
        "max_exposure": metrics.get("max_exposure", 0.0),
        "average_cash_ratio": metrics.get("average_cash_ratio", 1.0),
        "avg_cash_ratio_in_risk_on": float(risk_on_daily.get("cash_ratio", pd.Series(dtype=float)).mean()) if not risk_on_daily.empty else metrics.get("average_cash_ratio", 1.0),
        "average_positions": metrics.get("average_positions", 0.0),
        "max_positions_seen": metrics.get("max_positions_used", 0),
        **{key: value for key, value in attribution.items() if not isinstance(value, dict)},
        "replacement_count": int(len(replacement_rows)),
        "replacement_realized_pnl": float(pd.DataFrame(replacement_rows).get("realized_pnl_from_sell", pd.Series(dtype=float)).sum()) if replacement_rows else 0.0,
        "auto_trading_approved": False,
        "broker_integration_enabled": False,
        "llm_decision_allowed": False,
        "_daily_rows": daily_rows,
        "_watch_records": watch_records,
        "_replacement_rows": replacement_rows,
        "_attribution_detail": attribution,
    }
    return payload


def evaluate_hard_conditions(row: dict[str, Any], evaluation: dict[str, Any] | None = None) -> dict[str, Any]:
    evaluation = {**DEFAULT_EVALUATION, **(evaluation or {})}
    failures: list[str] = []
    ratio = row.get("executable_account_actionable_ratio")
    if ratio is None or (isinstance(ratio, float) and pd.isna(ratio)):
        ratio = _ratio_or_none(_safe_float(row.get("executable_buy_count")), _safe_float(row.get("account_actionable_buy_count")))
    if _safe_float(row.get("annual_return")) < _safe_float(evaluation["annual_return_min_absolute"]):
        failures.append("annual_return")
    if _safe_float(row.get("sharpe")) < _safe_float(evaluation["sharpe_min"]):
        failures.append("sharpe")
    if _safe_float(row.get("max_drawdown")) < _safe_float(evaluation["max_drawdown_floor"]):
        failures.append("max_drawdown")
    if _safe_int(row.get("total_trades")) < _safe_int(evaluation["total_trades_min"]) or _safe_int(row.get("total_trades")) > _safe_int(evaluation["total_trades_max"]):
        failures.append("total_trades")
    if ratio is None or pd.isna(ratio) or _safe_float(ratio) < _safe_float(evaluation["executable_account_actionable_min"]):
        failures.append("executable_account_actionable_ratio")
    if _safe_float(row.get("avg_cash_ratio_in_risk_on"), 1.0) > _safe_float(evaluation["avg_cash_ratio_max_in_risk_on"]):
        failures.append("avg_cash_ratio_in_risk_on")
    if _safe_float(row.get("largest_single_stock_pnl_contribution")) > _safe_float(evaluation["largest_single_stock_pnl_contribution_max"]):
        failures.append("largest_single_stock_pnl_contribution")
    if _safe_float(row.get("largest_industry_pnl_contribution")) > _safe_float(evaluation["largest_industry_pnl_contribution_max"]):
        failures.append("largest_industry_pnl_contribution")
    if bool(evaluation.get("realized_pnl_must_be_materially_positive", True)) and _safe_float(row.get("realized_pnl")) <= 0:
        failures.append("realized_pnl")
    if (
        bool(evaluation.get("cyclical_bucket_pnl_must_be_non_negative_unless_cyclical_disabled", True))
        and _safe_int(row.get("cyclical_max_positions")) > 0
        and _safe_float(row.get("cyclical_rotation_pnl")) < 0
    ):
        failures.append("cyclical_rotation_pnl")
    return {"pass_hard_conditions": not failures, "fail_reasons": ",".join(failures)}


def _normalized(value: float, values: list[float], reverse: bool = False) -> float:
    if not values:
        return 0.0
    lo = min(values)
    hi = max(values)
    if abs(hi - lo) < 1e-12:
        return 1.0
    score = (value - lo) / (hi - lo)
    return 1.0 - score if reverse else score


def _score_rows(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    annuals = frame["annual_return"].astype(float).tolist()
    sharpes = frame["sharpe"].astype(float).tolist()
    drawdowns = frame["max_drawdown"].astype(float).tolist()
    rows = []
    for row in frame.to_dict(orient="records"):
        execution_quality = _safe_float(row.get("executable_account_actionable_ratio"), 0.0)
        diversification_quality = 1.0 - max(_safe_float(row.get("largest_single_stock_pnl_contribution")), _safe_float(row.get("largest_industry_pnl_contribution")))
        realized_quality = 1.0 if _safe_float(row.get("realized_pnl")) > 0 else 0.0
        score = (
            0.30 * _normalized(_safe_float(row.get("annual_return")), annuals)
            + 0.25 * _normalized(_safe_float(row.get("sharpe")), sharpes)
            + 0.20 * _normalized(_safe_float(row.get("max_drawdown")), drawdowns)
            + 0.10 * execution_quality
            + 0.10 * max(0.0, diversification_quality)
            + 0.05 * realized_quality
        )
        row["selection_score"] = round(score, 6)
        rows.append(row)
    return pd.DataFrame(rows)


def evaluate_neighborhood_robustness(best: dict[str, Any], neighbors: list[dict[str, Any]], evaluation: dict[str, Any] | None = None) -> dict[str, Any]:
    evaluation = {**DEFAULT_EVALUATION, **(evaluation or {})}
    checked = []
    for row in neighbors:
        result = evaluate_hard_conditions(row, evaluation)
        checked.append({**row, **result})
    support = [row for row in checked if row.get("variant") != best.get("variant") and row.get("pass_hard_conditions")]
    support_count = len(support)
    if support_count >= 5:
        status = "ROBUST"
    elif support_count >= int(evaluation.get("neighboring_pass_count_min_excluding_best", 3)):
        status = "ACCEPTABLE"
    else:
        status = "FRAGILE"
    return {
        "status": status,
        "neighbor_count": len(checked),
        "support_count_excluding_best": support_count,
        "neighbors": checked,
    }


def _select_neighbors(frame: pd.DataFrame, best: dict[str, Any]) -> list[dict[str, Any]]:
    if frame.empty or not best:
        return []
    keys = [
        "max_positions",
        "target_universe_size",
        "cash_reserve_ratio",
        "max_single_stock_weight",
        "industry_max_positions",
        "cyclical_max_positions",
        "defensive_core_min_positions",
        "lot_notional_max_ratio_to_target_budget",
        "score_gap_threshold",
    ]
    rows = []
    for row in frame.to_dict(orient="records"):
        if row.get("variant") == best.get("variant"):
            continue
        distance = 0.0
        for key in keys:
            distance += abs(_safe_float(row.get(key)) - _safe_float(best.get(key)))
        row["_distance_to_best"] = distance
        rows.append(row)
    rows = sorted(rows, key=lambda item: (item["_distance_to_best"], -_safe_float(item.get("selection_score")), str(item.get("variant"))))
    return rows[: max(8, min(len(rows), 20))]


def _write_table(lines: list[str], frame: pd.DataFrame) -> None:
    cols = [
        "variant",
        "annual_return",
        "cumulative_return",
        "max_drawdown",
        "sharpe",
        "total_trades",
        "executable_account_actionable_ratio",
        "average_exposure",
        "avg_cash_ratio_in_risk_on",
        "largest_single_stock_pnl_contribution",
        "largest_industry_pnl_contribution",
        "defensive_dividend_pnl",
        "cyclical_rotation_pnl",
        "replacement_count",
        "pass_hard_conditions",
        "fail_reasons",
    ]
    lines.append("| " + " | ".join(cols) + " |")
    lines.append("|" + "|".join(["---"] * len(cols)) + "|")
    for row in frame.head(20).to_dict(orient="records"):
        values = []
        for col in cols:
            value = row.get(col, "")
            if isinstance(value, float) and col not in {"defensive_dividend_pnl", "cyclical_rotation_pnl"}:
                value = _pct(value) if abs(value) < 2 else f"{value:.2f}"
            values.append(str(value))
        lines.append("| " + " | ".join(values) + " |")


def _failure_distribution(frame: pd.DataFrame) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for item in frame.get("fail_reasons", pd.Series(dtype=str)).dropna().astype(str):
        for reason in item.split(","):
            if reason:
                counter[reason] += 1
    return dict(counter)


def _write_module_report(frame: pd.DataFrame, best: dict[str, Any] | None, out_dir: Path) -> None:
    lines = ["# 50k core module contribution", "", "- research_only: true", "- auto_trading_approved: false", ""]
    if frame.empty:
        lines.extend(["No experiment rows were available; module classifications are INCONCLUSIVE."])
        out_dir.joinpath("core_module_contribution_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        return
    if not best:
        lines.append("- no_hard_condition_candidate: true")
        lines.append("- reference: best ranked current research row; classifications are still human-review-required.")
        lines.append("")
    current_rows = frame[frame.get("module_control", pd.Series(dtype=str)).astype(str) == "current"] if "module_control" in frame.columns else frame
    default_base = (current_rows.iloc[0] if not current_rows.empty else frame.iloc[0]).to_dict()
    control_map = {
        "high_dividend_supplement": "disable_high_dividend_supplement",
        "trend_stop": "disable_trend_stop",
        "market/regime exposure": "",
        "replacement": "replacement_disabled",
        "cyclical overlay": "cyclical_disabled",
    }
    lines.append("| module | annual_delta | max_drawdown_delta | sharpe_delta | realized_pnl_delta | total_trades_delta | replacement_count_delta | classification | human_review_required |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---|---|")
    for module, control_name in control_map.items():
        base = dict(default_base)
        comparable_rows = frame[frame["module_control"].astype(str) == control_name] if control_name and "module_control" in frame.columns else pd.DataFrame()
        comparable = comparable_rows.iloc[0].to_dict() if not comparable_rows.empty else {}
        if comparable and not current_rows.empty:
            keys = [
                "max_positions",
                "target_universe_size",
                "cash_reserve_ratio",
                "max_single_stock_weight",
                "industry_max_positions",
                "defensive_core_min_positions",
                "cyclical_max_positions",
                "lot_notional_max_ratio_to_target_budget",
                "score_gap_threshold",
                "max_replacements_per_month",
                "risk_on_target_exposure",
                "neutral_target_exposure",
                "risk_off_target_exposure",
            ]
            matched = current_rows.copy()
            for key in keys:
                if key in matched.columns and key in comparable:
                    matched = matched[matched[key].astype(str) == str(comparable[key])]
            if not matched.empty:
                base = matched.iloc[0].to_dict()
        annual_delta = _safe_float(comparable.get("annual_return")) - _safe_float(base.get("annual_return"))
        dd_delta = _safe_float(comparable.get("max_drawdown")) - _safe_float(base.get("max_drawdown"))
        sharpe_delta = _safe_float(comparable.get("sharpe")) - _safe_float(base.get("sharpe"))
        realized_delta = _safe_float(comparable.get("realized_pnl")) - _safe_float(base.get("realized_pnl"))
        trades_delta = _safe_int(comparable.get("total_trades")) - _safe_int(base.get("total_trades"))
        replacement_delta = _safe_int(comparable.get("replacement_count")) - _safe_int(base.get("replacement_count"))
        if not comparable or min(_safe_int(base.get("total_trades")), _safe_int(comparable.get("total_trades"))) < 10:
            classification = "INCONCLUSIVE"
        elif annual_delta > 0 and sharpe_delta > 0 and dd_delta > -0.02:
            classification = "POSSIBLE_DRAG"
        elif annual_delta < 0 and dd_delta > 0.02:
            classification = "RISK_REDUCER"
        elif annual_delta > 0:
            classification = "RETURN_ENHANCER"
        else:
            classification = "INCONCLUSIVE"
        lines.append(
            f"| {module} | {_pct(annual_delta)} | {_pct(dd_delta)} | {sharpe_delta:.4f} | {realized_delta:.2f} | {trades_delta} | {replacement_delta} | {classification} | true |"
        )
    out_dir.joinpath("core_module_contribution_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_core_report(frame: pd.DataFrame, summary: dict[str, Any], robustness: dict[str, Any], out_dir: Path) -> None:
    best = summary.get("best_candidate") or {}
    lines = [
        "# combined_v2_50k_core research report",
        "",
        "## 1. 摘要",
        "",
        f"- status: {summary['status']}",
        "- candidate_is_research_only: true",
        "- auto_trading_allowed: false",
        "- release_replacement: false",
        f"- experiment_count: {summary['experiment_count']}",
        f"- hard_condition_pass_count: {summary['hard_condition_pass_count']}",
        "",
        "## 2. 为什么原 50k 表现差",
        "",
        "- raw buy 到 executable buy 漏斗显示，信号不是完全缺失，主要损耗发生在组合满仓、现金不足和一手金额过高。",
        "- 小账户下 100 股整手导致目标仓位金额与真实可买单位错配，高现金拖累会持续存在。",
        "- 原多档加仓结构会把现金切碎，增加 `LOT_SIZE_ACCUMULATION_REQUIRED` 类 watch-only 或 pending 信号。",
        "- 持仓数量过多时，单票贡献和行业贡献更容易集中，替换机制需要只在 research backtest 中模拟。",
        "",
        "## 3. 50k core 的设计逻辑",
        "",
        "- 少持仓、单档、不加仓，降低整手执行碎片化。",
        "- 单票上限提高到 14%-18% 网格，但一手金额超过单票上限时仍结构性阻断。",
        "- defensive dividend 作为核心，周期股作为 risk-on opportunity sleeve，且不能挤占 defensive core。",
        "- replacement / switch plan 只在回测中 research-only 模拟，live/manual 仍 advisory only。",
        "- lot-fit 进入排序和审计输出，而不是事后解释。",
        "",
        "## 4. top 20 变体表",
        "",
    ]
    _write_table(lines, frame)
    lines.extend(["", "## 5. best candidate", ""])
    if best:
        lines.extend(
            [
                f"- variant: {best.get('variant')}",
                f"- annual_return: {_pct(best.get('annual_return'))}",
                f"- cumulative_return: {_pct(best.get('cumulative_return'))}",
                f"- max_drawdown: {_pct(best.get('max_drawdown'))}",
                f"- sharpe: {float(best.get('sharpe', 0.0)):.4f}",
                f"- executable_account_actionable_ratio: {_pct(best.get('executable_account_actionable_ratio'))}",
                f"- selected because: hard conditions passed first, then composite score ranked highest.",
                "- risks: still research-only; paper fills and future signal funnel must be observed before any manual use.",
            ]
        )
    else:
        lines.append("- 没有候选通过硬条件。失败分布如下：")
        for key, value in summary["failure_distribution"].items():
            lines.append(f"  - {key}: {value}")
    lines.extend(
        [
            "",
            "## 6. neighborhood robustness",
            "",
            f"- judgement: {robustness.get('status', 'FRAGILE')}",
            f"- neighbor_count: {robustness.get('neighbor_count', 0)}",
            f"- supporting_neighbors_excluding_best: {robustness.get('support_count_excluding_best', 0)}",
            "- rule: excluding best, >=3 hard-condition neighbors is ACCEPTABLE; >=5 is ROBUST; otherwise FRAGILE.",
            "",
            "## 7. attribution",
            "",
            f"- largest_single_stock_pnl_contribution: {_pct(best.get('largest_single_stock_pnl_contribution', 0.0) if best else 0.0)}",
            f"- largest_industry_pnl_contribution: {_pct(best.get('largest_industry_pnl_contribution', 0.0) if best else 0.0)}",
            f"- defensive_dividend_pnl: {float(best.get('defensive_dividend_pnl', 0.0) if best else 0.0):.2f}",
            f"- cyclical_rotation_pnl: {float(best.get('cyclical_rotation_pnl', 0.0) if best else 0.0):.2f}",
            f"- realized_pnl: {float(best.get('realized_pnl', 0.0) if best else 0.0):.2f}",
            f"- unrealized_pnl: {float(best.get('unrealized_pnl', 0.0) if best else 0.0):.2f}",
            "",
            "## 8. execution audit",
            "",
            f"- executable_account_actionable_ratio: {_pct(best.get('executable_account_actionable_ratio', 0.0) if best else 0.0)}",
            f"- raw_buy_signal_count: {int(best.get('raw_buy_signal_count', 0) if best else 0)}",
            f"- watch_only_count: {int(best.get('watch_only_count', 0) if best else 0)}",
            f"- top_watch_only_reasons: {best.get('top_watch_only_reasons', {}) if best else {}}",
            f"- replacement_count: {int(best.get('replacement_count', 0) if best else 0)}",
            f"- average_cash_ratio: {_pct(best.get('average_cash_ratio', 0.0) if best else 0.0)}",
            "",
            "## 9. module contribution",
            "",
            "- See `core_module_contribution_report.md`. Controls are research-only and do not delete modules automatically.",
            "",
            "## 10. 结论",
            "",
            "- This profile is paper trading / observation only.",
            "- It does not allow automatic live trading.",
            "- It does not replace the default release profile.",
            "- Daily monitoring should track generated signals, executable buys, watch-only reasons, current exposure, cash ratio, industry concentration, paper fill slippage, and manual overrides.",
            "",
            "## cash_sleeve note",
            "",
            "- 50k low return still has cash drag. `cash_sleeve` is a future research interface, disabled by default, with no ETF result fabricated in this run.",
        ]
    )
    out_dir.joinpath("core_experiment_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_observation_candidate(best: dict[str, Any] | None, robustness: dict[str, Any], out_dir: Path) -> None:
    lines = ["# 50k core observation candidate", ""]
    if best:
        lines.extend(
            [
                f"- candidate_variant: {best.get('variant')}",
                "- frozen_for: paper_trading_observation_only",
                "- research_only: true",
                "- auto_trading_approved: false",
                "- broker_integration_enabled: false",
                "- llm_decision_allowed: false",
                f"- neighborhood_robustness: {robustness.get('status')}",
                "",
                "## selected metrics",
                "",
                f"- annual_return: {_pct(best.get('annual_return'))}",
                f"- cumulative_return: {_pct(best.get('cumulative_return'))}",
                f"- max_drawdown: {_pct(best.get('max_drawdown'))}",
                f"- sharpe: {float(best.get('sharpe', 0.0)):.4f}",
                f"- total_trades: {int(best.get('total_trades', 0))}",
                f"- executable_account_actionable_ratio: {_pct(best.get('executable_account_actionable_ratio'))}",
                "",
                "## why selected",
                "",
                "- Passed hard conditions before ranking.",
                "- Composite score balances return, Sharpe, drawdown safety, execution quality, diversification, and realized PnL.",
                "",
                "## risks",
                "",
                "- Research-only sample; paper slippage and watch-only funnel need daily observation.",
                "- No cash sleeve or ETF substitute is enabled.",
            ]
        )
    else:
        lines.extend(["- candidate_variant: none", "- reason: no variant passed hard conditions", "- research_only: true"])
    lines.extend(
        [
            "",
            "## daily monitoring metrics",
            "",
            "- `generated_signal_count`",
            "- `account_actionable_buy_count`",
            "- `watch_only_count`",
            "- `executable_buy_count`",
            "- `top_watch_only_reasons`",
            "- `current_positions_count`",
            "- `current_exposure`",
            "- `current_cash_ratio`",
            "- `industry_concentration`",
            "- `skipped_signal_reason`",
            "- `replacement_candidate_count`",
            "- `replacement_pair_suggestions`",
            "- `actual_paper_fill_price`",
            "- `paper_slippage_vs_next_open`",
            "- `manual_override_flag`",
            "- `manual_override_reason`",
        ]
    )
    out_dir.joinpath("core_observation_candidate.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_core_outputs(rows: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    out_dir = resolve_path(OUT_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    evaluation = {**DEFAULT_EVALUATION, **(config.get("evaluation") or {})}
    public_rows = []
    daily_rows: list[dict[str, Any]] = []
    watch_rows: list[dict[str, Any]] = []
    replacement_rows: list[dict[str, Any]] = []
    attribution_rows: list[dict[str, Any]] = []
    for row in rows:
        public = {key: value for key, value in row.items() if not key.startswith("_")}
        public.update(evaluate_hard_conditions(public, evaluation))
        public_rows.append(public)
        daily_rows.extend(row.get("_daily_rows", []))
        watch_rows.extend(row.get("_watch_records", []))
        replacement_rows.extend(row.get("_replacement_rows", []))
        detail = row.get("_attribution_detail", {})
        attribution_rows.append(
            {
                "variant": row.get("variant"),
                "symbol_pnl": json.dumps(detail.get("symbol_pnl", {}), ensure_ascii=False, sort_keys=True),
                "industry_pnl": json.dumps(detail.get("industry_pnl", {}), ensure_ascii=False, sort_keys=True),
                "bucket_pnl": json.dumps(detail.get("bucket_pnl", {}), ensure_ascii=False, sort_keys=True),
                "largest_single_stock_pnl_contribution": row.get("largest_single_stock_pnl_contribution", 0.0),
                "largest_industry_pnl_contribution": row.get("largest_industry_pnl_contribution", 0.0),
            }
        )
    frame = pd.DataFrame(public_rows)
    if not frame.empty:
        frame = _score_rows(frame)
        frame = frame.sort_values(
            ["pass_hard_conditions", "selection_score", "annual_return", "max_drawdown"],
            ascending=[False, False, False, False],
            na_position="last",
        ).reset_index(drop=True)
    frame.to_csv(out_dir / "core_experiment_metrics.csv", index=False)
    candidates = frame[frame["pass_hard_conditions"].astype(bool)] if not frame.empty else pd.DataFrame()
    best = candidates.iloc[0].to_dict() if not candidates.empty else None
    neighbors = _select_neighbors(frame, best) if best else []
    robustness = evaluate_neighborhood_robustness(best or {}, neighbors, evaluation) if best else {"status": "FRAGILE", "neighbor_count": 0, "support_count_excluding_best": 0, "neighbors": []}
    failure_distribution = _failure_distribution(frame) if not frame.empty else {}
    summary = {
        "generated_at": now_utc_iso(),
        "git_commit": git_commit(),
        "branch": git_branch(),
        "status": "HAS_50K_CORE_CANDIDATE" if best else "NO_50K_CORE_CANDIDATE",
        "profile": PROFILE_NAME,
        "research_only": True,
        "default_release_profile_unchanged": True,
        "release_profile_replacement": False,
        "execution_mode": "next_bar",
        "pit": True,
        "config_hash": config_hash([CONFIG_PATH]) if resolve_path(CONFIG_PATH).exists() else "",
        "data_hash": data_hash(),
        "experiment_count": int(len(frame)),
        "hard_condition_pass_count": int(len(candidates)),
        "failure_distribution": failure_distribution,
        "best_candidate": best or {},
        "rows_hash": stable_hash(frame.to_dict(orient="records")) if not frame.empty else "",
        "auto_trading_approved": False,
        "broker_integration_enabled": False,
        "llm_decision_allowed": False,
    }
    (out_dir / "core_best_candidate.yml").write_text(yaml.safe_dump(best or {"status": "NO_50K_CORE_CANDIDATE"}, allow_unicode=True, sort_keys=False), encoding="utf-8")
    (out_dir / "core_effective_config.yml").write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")
    pd.DataFrame(daily_rows or [{"variant": "", "raw_buy_signal_count": 0, "account_actionable_buy_count": 0, "watch_only_count": 0, "executable_buy_count": 0}]).to_csv(out_dir / "core_execution_funnel.csv", index=False)
    pd.DataFrame(attribution_rows or [{"variant": "", "symbol_pnl": "{}", "industry_pnl": "{}", "bucket_pnl": "{}"}]).to_csv(out_dir / "core_attribution_summary.csv", index=False)
    pd.DataFrame(replacement_rows or [{"date": "", "sell_symbol": "", "buy_symbol": "", "sell_industry": "", "buy_industry": "", "weakest_holding_score": 0, "candidate_score": 0, "score_gap": 0, "sell_reason": "", "buy_reason": "", "realized_pnl_from_sell": 0, "estimated_cost": 0, "portfolio_positions_before": 0, "portfolio_positions_after": 0}]).to_csv(out_dir / "core_replacement_report.csv", index=False)
    robustness_lines = ["# 50k core neighborhood robustness", "", f"- status: {robustness['status']}", f"- neighbor_count: {robustness['neighbor_count']}", f"- support_count_excluding_best: {robustness['support_count_excluding_best']}", ""]
    robustness_lines.extend(f"- {row.get('variant')}: pass={row.get('pass_hard_conditions')} fail={row.get('fail_reasons', '')}" for row in robustness.get("neighbors", []))
    (out_dir / "core_neighborhood_robustness.md").write_text("\n".join(robustness_lines) + "\n", encoding="utf-8")
    warnings = {
        "status": summary["status"],
        "failure_distribution": failure_distribution,
        "cash_sleeve": "disabled; research interface only; no ETF data or fabricated ETF result used",
        "watch_only_reasons": dict(Counter(row.get("reason_code", "") for row in watch_rows if row.get("reason_code"))),
        "auto_trading_approved": False,
    }
    (out_dir / "core_warnings.json").write_text(json.dumps(warnings, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    _write_core_report(frame, summary, robustness, out_dir)
    _write_observation_candidate(best, robustness, out_dir)
    _write_module_report(frame, best, out_dir)
    missing = [name for name in REQUIRED_OUTPUTS if not (out_dir / name).exists()]
    if missing:
        raise RuntimeError(f"missing required 50k core outputs: {missing}")
    return summary


def _params_from_config(config: dict[str, Any]) -> list[CoreParams]:
    portfolio = config["portfolio"]
    account = config["account"]
    lot_fit = config["lot_fit"]
    bucket = config["bucket_policy"]
    replacement = config["replacement"]
    risk = config["risk_exposure"]
    params: list[CoreParams] = []
    for values in itertools.product(
        portfolio["max_positions_grid"],
        portfolio["max_tranches_grid"],
        portfolio["target_universe_size_grid"],
        portfolio["cash_reserve_ratio_grid"],
        portfolio["max_single_stock_weight_grid"],
        portfolio["max_new_positions_per_day_grid"],
        portfolio["max_adds_per_day_grid"],
        portfolio["industry_max_positions_grid"],
        bucket["defensive_core_min_positions_grid"],
        bucket["cyclical_max_positions_grid"],
        lot_fit["lot_notional_max_ratio_to_target_budget_grid"],
        replacement["score_gap_threshold_grid"],
        replacement["max_replacements_per_month_grid"],
        risk["risk_on_target_exposure_grid"],
        risk["neutral_target_exposure_grid"],
        risk["risk_off_target_exposure_grid"],
    ):
        params.append(
            CoreParams(
                max_positions=int(values[0]),
                max_tranches=int(values[1]),
                target_universe_size=int(values[2]),
                cash_reserve_ratio=float(values[3]),
                max_single_stock_weight=float(values[4]),
                max_new_positions_per_day=int(values[5]),
                max_adds_per_day=int(values[6]),
                industry_max_positions=int(values[7]),
                defensive_core_min_positions=int(values[8]),
                cyclical_max_positions=int(values[9]),
                lot_notional_max_ratio_to_target_budget=float(values[10]),
                score_gap_threshold=float(values[11]),
                max_replacements_per_month=int(values[12]),
                risk_on_target_exposure=float(values[13]),
                neutral_target_exposure=float(values[14]),
                risk_off_target_exposure=float(values[15]),
                capital=float(account["capital"]),
                round_lot=int(account["round_lot"]),
                min_trade_value=float(account["min_trade_value"]),
            )
        )
    base = params[0] if params else None
    if base:
        params.extend(
            [
                CoreParams(**{**base.__dict__, "module_control": "disable_high_dividend_supplement"}),
                CoreParams(**{**base.__dict__, "module_control": "disable_trend_stop"}),
                CoreParams(**{**base.__dict__, "module_control": "disable_both"}),
                CoreParams(**{**base.__dict__, "replacement_enabled": False, "module_control": "replacement_disabled"}),
                CoreParams(**{**base.__dict__, "cyclical_overlay_enabled": False, "cyclical_max_positions": 0, "module_control": "cyclical_disabled"}),
            ]
        )
    return params


def run_experiments(max_variants: int | None = None) -> dict[str, Any]:
    config = load_yaml(CONFIG_PATH)
    configs = load_audit_configs()
    features = load_feature_window(DEFAULT_START_DATE, DEFAULT_END_DATE)
    benchmark = load_benchmark_window(DEFAULT_START_DATE, DEFAULT_END_DATE)
    feature_by_date, approximate = _prepare_feature_by_date(features, configs)
    config = copy.deepcopy(config)
    config["approximate_backtest"] = bool(approximate)
    rows: list[dict[str, Any]] = []
    params = _params_from_config(config)
    if max_variants is not None:
        config["max_variants_run"] = int(max_variants)
        params = params[: int(max_variants)]
    config["experiment_matrix_size"] = len(_params_from_config(config))
    for idx, item in enumerate(params, start=1):
        print(f"[50k_core] {idx:05d}/{len(params):05d} {item.variant_id}", flush=True)
        rows.append(run_core_backtest(item, feature_by_date=feature_by_date, benchmark=benchmark, configs=configs))
    return write_core_outputs(rows, config)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run research-only combined_v2_50k_core experiment matrix.")
    parser.add_argument("--max-variants", type=int, default=None, help="Limit variants for local smoke runs; omitted means full matrix.")
    args = parser.parse_args()
    run_experiments(max_variants=args.max_variants)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
