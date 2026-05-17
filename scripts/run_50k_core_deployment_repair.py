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
    DEFAULT_EVALUATION,
    PROFILE_NAME,
    SELL_ACTIONS,
    CoreParams,
    _account_cfg,
    _apply_core_buy_selection,
    _attribution,
    _core_policy,
    _execute_partial_derisk,
    _execute_replacement,
    _holding_records,
    _params_from_config,
    _pct,
    _prepare_feature_by_date,
    _ratio_or_none,
    _regime_name,
    _safe_float,
    _safe_int,
    _score_rows,
    _strategy_cfg,
    _target_weight,
    core_account_gate,
    evaluate_hard_conditions,
    evaluate_neighborhood_robustness,
)
from src.execution.partial_derisk import evaluate_partial_derisk
from src.strategy.backtest_engine import BacktestEngine, Position
from src.strategy.deployment_repair import (
    CASH_SLEEVE_ACTION,
    CASH_SLEEVE_LABEL,
    GROUP_CAP_BLOCKED,
    QUALITY_FILL_ACTION,
    REGIME_REVIEW_ACTION,
    WINNER_ADD_ACTION,
    compute_quality_defensive_fill_candidate,
    compute_winner_add_candidate,
    evaluate_cash_sleeve_research,
    evaluate_group_concentration,
    evaluate_market_regime_review_fill,
    quality_fill_sort_key,
)
from src.strategy.regime import determine_market_regime
from src.strategy.score_50k_core import compute_50k_expected_edge_score
from src.strategy.signals import SignalEngine
from src.utils.config import load_yaml, resolve_path


CONFIG_PATH = "config/strategy_v2_50k_core_deployment_repair.yml"
BASE_CORE_CONFIG_PATH = "config/strategy_v2_50k_core.yml"
REPAIR_BEST_PATH = "reports/backtest/50k_core/repair/repair_best_candidate.yml"
PHASE3_TRACE_DIR = "reports/backtest/50k_core/traces"
OUT_DIR = "reports/backtest/50k_core/deployment_repair"
REPAIR_BEST_VARIANT = "mp5_tr1_tu8_cr10_sw18_ind2_def3_cy0_lot100_gap8_rpm1_ro85_ne60_rf25_rep1_cyc1_disable_both_monthly_review"

REQUIRED_OUTPUTS = [
    "deployment_repair_metrics.csv",
    "deployment_repair_report.md",
    "deployment_repair_best_candidate.yml",
    "deployment_repair_observation_candidate.md",
    "deployment_repair_comparison_vs_repair_best.md",
    "deployment_repair_trace_summary.md",
    "deployment_repair_cash_sleeve_feasibility.md",
    "deployment_repair_group_concentration_report.csv",
    "deployment_repair_quality_fill_report.csv",
    "deployment_repair_winner_add_report.csv",
    "deployment_repair_warnings.json",
    "deployment_repair_effective_config.yml",
]

TRACE_OUTPUTS = [
    "daily_portfolio_ledger.csv",
    "daily_position_pnl.csv",
    "trade_ledger.csv",
    "signal_execution_trace.csv",
    "exit_rule_trace.csv",
    "replacement_candidate_trace.csv",
    "deployment_repair_trace_diagnostic_report.md",
]


@dataclass(frozen=True)
class DeploymentRepairVariant:
    name: str
    params: CoreParams
    mechanisms_enabled: tuple[str, ...]
    quality_fill_enabled: bool = False
    quality_profile: str = "strict"
    max_total_fill_positions: int = 1
    winner_add_enabled: bool = False
    winner_max_single_stock_weight: float = 0.16
    financial_group_cap_enabled: bool = False
    financial_max_positions: int = 1
    financial_max_weight: float = 0.30
    utility_max_positions: int = 1
    utility_max_weight: float = 0.20
    market_regime_review_enabled: bool = False
    cash_sleeve_enabled: bool = False
    cash_sleeve_max_weight: float = 0.15
    research_only: bool = True
    auto_trading_approved: bool = False
    broker_integration_enabled: bool = False
    llm_decision_allowed: bool = False
    writes_real_trades: bool = False
    release_profile_replacement: bool = False

    @property
    def stock_only(self) -> bool:
        return not self.cash_sleeve_enabled


def _base_params() -> CoreParams:
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
        monthly_rebalance_review_enabled=True,
        target_cash_ratio=0.35,
        repair_label="monthly_review",
    )


def build_deployment_repair_variants(config: dict[str, Any] | None = None) -> list[DeploymentRepairVariant]:
    cfg = config or load_yaml(CONFIG_PATH)
    limit = int((cfg.get("deployment_repair") or {}).get("max_variants", 24))
    base = _base_params()
    variants: list[DeploymentRepairVariant] = [
        DeploymentRepairVariant("repair_best_baseline", base, ("baseline",)),
    ]
    for profile in ("strict", "balanced"):
        for max_total in (1, 2):
            variants.append(
                DeploymentRepairVariant(
                    f"quality_fill_{profile}_total{max_total}",
                    base,
                    ("quality_defensive_fill",),
                    quality_fill_enabled=True,
                    quality_profile=profile,
                    max_total_fill_positions=max_total,
                )
            )
    for max_weight in (0.16, 0.18):
        variants.append(
            DeploymentRepairVariant(
                f"winner_add_sw{int(max_weight * 100)}",
                base,
                ("winner_add",),
                winner_add_enabled=True,
                winner_max_single_stock_weight=max_weight,
            )
        )
    for profile in ("strict", "balanced"):
        for max_weight in (0.16, 0.18):
            variants.append(
                DeploymentRepairVariant(
                    f"quality_{profile}_winner_sw{int(max_weight * 100)}",
                    base,
                    ("quality_defensive_fill", "winner_add"),
                    quality_fill_enabled=True,
                    quality_profile=profile,
                    winner_add_enabled=True,
                    winner_max_single_stock_weight=max_weight,
                )
            )
    for fin_pos, fin_weight in ((1, 0.30), (1, 0.35), (2, 0.30), (2, 0.35)):
        variants.append(
            DeploymentRepairVariant(
                f"group_cap_fin{fin_pos}_fw{int(fin_weight * 100)}",
                base,
                ("quality_defensive_fill", "financial_group_cap"),
                quality_fill_enabled=True,
                quality_profile="balanced",
                max_total_fill_positions=2,
                financial_group_cap_enabled=True,
                financial_max_positions=fin_pos,
                financial_max_weight=fin_weight,
            )
        )
    for profile, fin_pos in (("strict", 1), ("balanced", 1), ("strict", 2), ("balanced", 2)):
        variants.append(
            DeploymentRepairVariant(
                f"regime_review_{profile}_fin{fin_pos}",
                base,
                ("quality_defensive_fill", "financial_group_cap", "market_regime_block_review"),
                quality_fill_enabled=True,
                quality_profile=profile,
                max_total_fill_positions=2,
                financial_group_cap_enabled=True,
                financial_max_positions=fin_pos,
                market_regime_review_enabled=True,
            )
        )
    for weight, mechanisms in (
        (0.15, ("cash_sleeve_research",)),
        (0.25, ("cash_sleeve_research",)),
        (0.15, ("quality_defensive_fill", "cash_sleeve_research")),
        (0.25, ("quality_defensive_fill", "winner_add", "cash_sleeve_research")),
    ):
        variants.append(
            DeploymentRepairVariant(
                "cash_sleeve_w" + str(int(weight * 100)) + "_" + "_".join(m for m in mechanisms if m != "cash_sleeve_research") or "cash_sleeve",
                base,
                mechanisms,
                quality_fill_enabled="quality_defensive_fill" in mechanisms,
                quality_profile="balanced",
                winner_add_enabled="winner_add" in mechanisms,
                cash_sleeve_enabled=True,
                cash_sleeve_max_weight=weight,
            )
        )
    dedup: list[DeploymentRepairVariant] = []
    seen: set[str] = set()
    for variant in variants:
        if variant.name in seen:
            continue
        dedup.append(variant)
        seen.add(variant.name)
    return dedup[:limit]


def _quality_cfg(config: dict[str, Any], variant: DeploymentRepairVariant) -> dict[str, Any]:
    raw = ((config.get("deployment_repair") or {}).get("quality_defensive_fill") or {})
    return {
        "enabled": variant.quality_fill_enabled,
        "threshold_profile": variant.quality_profile,
        "thresholds": raw.get("thresholds_grid", {}),
        "required": raw.get("required", {}),
    }


def _winner_cfg(variant: DeploymentRepairVariant) -> dict[str, Any]:
    return {
        "enabled": variant.winner_add_enabled,
        "max_single_stock_weight": variant.winner_max_single_stock_weight,
        "max_extra_lots_per_symbol": 1,
        "max_adds_per_month": 1,
    }


def _group_cfg(config: dict[str, Any], variant: DeploymentRepairVariant) -> dict[str, Any]:
    raw = ((config.get("deployment_repair") or {}).get("financial_group_cap") or {})
    return {
        "enabled": variant.financial_group_cap_enabled,
        "group_definitions": raw.get("group_definitions"),
        "financial_max_positions": variant.financial_max_positions,
        "financial_max_weight": variant.financial_max_weight,
        "utility_max_positions": variant.utility_max_positions,
        "utility_max_weight": variant.utility_max_weight,
    }


def _portfolio_positions_for_group(positions: dict[str, Position], price_frame: pd.DataFrame, nav: float) -> list[dict[str, Any]]:
    rows = []
    for symbol, position in positions.items():
        price = _safe_float(price_frame.loc[symbol, "close"]) if symbol in price_frame.index and "close" in price_frame.columns else position.last_fill_price
        rows.append(
            {
                "symbol": symbol,
                "industry": position.industry,
                "bucket": position.bucket,
                "weight": position.shares * price / max(nav, 1e-9),
            }
        )
    return rows


def _overlay_trace_row(date: str, variant: str, decision: dict[str, Any], action: str, status: str, reason: str = "") -> dict[str, Any]:
    return {
        "date": date,
        "variant": variant,
        "symbol": decision.get("symbol"),
        "bucket": decision.get("bucket"),
        "industry": decision.get("industry"),
        "overlay_action": action,
        "execution_status": status,
        "reason_code": reason,
        "future_return_used": False,
        "trace_quality_flag": "DEPLOYMENT_REPAIR_RESEARCH_ONLY",
    }


def _candidate_quality_fields(decision: dict[str, Any]) -> dict[str, Any]:
    enriched = copy.deepcopy(decision)
    enriched["quality_pass"] = bool(enriched.get("quality_pass", _safe_float(enriched.get("final_score", enriched.get("universe_final_score"))) >= 55.0))
    enriched["core_fields_complete"] = _safe_float(enriched.get("close")) > 0 and (
        "final_score" in enriched or "universe_final_score" in enriched
    )
    return enriched


def _apply_group_cap_to_selected(
    *,
    selected: list[tuple[dict[str, Any], compact.GateResult]],
    signal_date: str,
    variant: DeploymentRepairVariant,
    config: dict[str, Any],
    positions: dict[str, Position],
    price_today: pd.DataFrame,
    nav: float,
    group_rows: list[dict[str, Any]],
    signal_trace_rows: list[dict[str, Any]],
) -> list[tuple[dict[str, Any], compact.GateResult]]:
    if not variant.financial_group_cap_enabled:
        return selected
    group_cfg = _group_cfg(config, variant)
    portfolio_state = {"positions": _portfolio_positions_for_group(positions, price_today, nav)}
    kept: list[tuple[dict[str, Any], compact.GateResult]] = []
    for decision, gate in selected:
        cap = evaluate_group_concentration(portfolio_state, {**decision, "weight_after_buy": gate.target_weight}, group_cfg)
        group_rows.append({"date": signal_date, "variant": variant.name, "symbol": decision.get("symbol"), **cap})
        if cap.get("allowed"):
            kept.append((decision, gate))
        else:
            signal_trace_rows.append(_overlay_trace_row(signal_date, variant.name, decision, str(decision.get("action_enum")), "WATCH_ONLY", GROUP_CAP_BLOCKED))
    return kept


def _select_quality_fill(
    *,
    signal_date: str,
    variant: DeploymentRepairVariant,
    config: dict[str, Any],
    decisions: list[dict[str, Any]],
    params: CoreParams,
    nav: float,
    cash: float,
    positions: dict[str, Position],
    price_today: pd.DataFrame,
    regime: object,
    total_quality_fills: int,
    month_quality_fills: int,
    quality_rows: list[dict[str, Any]],
    group_rows: list[dict[str, Any]],
    signal_trace_rows: list[dict[str, Any]],
) -> tuple[list[tuple[dict[str, Any], compact.GateResult]], int, int]:
    if not variant.quality_fill_enabled or total_quality_fills >= variant.max_total_fill_positions or month_quality_fills >= 1:
        return [], total_quality_fills, month_quality_fills
    cash_ratio = cash / max(nav, 1e-9)
    policy = _core_policy(
        params,
        nav=nav,
        regime=regime,
        industry_counts=Counter(position.industry for position in positions.values()),
        cyclical_counts=sum(1 for position in positions.values() if position.bucket == "cyclical_rotation"),
    )
    candidates = []
    quality_cfg = _quality_cfg(config, variant)
    for raw in decisions:
        if str(raw.get("symbol")) in positions:
            continue
        if not bool(raw.get("in_effective_universe", True)):
            continue
        decision = _candidate_quality_fields(raw)
        decision.update(compute_50k_expected_edge_score(decision, policy))
        decision.update({"market_regime": _regime_name(regime), "cash_ratio": cash_ratio, "has_executable_stock_buy": False})
        result = compute_quality_defensive_fill_candidate(decision, {"market_regime": _regime_name(regime), "cash_ratio": cash_ratio, "has_executable_stock_buy": False, "positions": _portfolio_positions_for_group(positions, price_today, nav)}, quality_cfg)
        row = {"date": signal_date, "variant": variant.name, "symbol": decision.get("symbol"), "threshold_profile": variant.quality_profile, **result}
        quality_rows.append(row)
        if result["eligible"]:
            candidates.append({"decision": decision, "result": result})
    selected: list[tuple[dict[str, Any], compact.GateResult]] = []
    group_cfg = _group_cfg(config, variant)
    for item in sorted(candidates, key=quality_fill_sort_key):
        decision = copy.deepcopy(item["decision"])
        decision["action_enum"] = QUALITY_FILL_ACTION
        decision["signal_level"] = QUALITY_FILL_ACTION
        gate = core_account_gate(
            decision,
            params,
            nav=nav,
            cash=cash,
            positions_count=len(positions),
            industry_position_count=sum(1 for position in positions.values() if position.industry == str(decision.get("industry"))),
            new_buys_today=0,
            adds_today=0,
            regime=_regime_name(regime),
        )
        if not gate.actionable:
            signal_trace_rows.append(_overlay_trace_row(signal_date, variant.name, decision, QUALITY_FILL_ACTION, "WATCH_ONLY", gate.reason_code))
            continue
        if variant.financial_group_cap_enabled:
            cap = evaluate_group_concentration({"positions": _portfolio_positions_for_group(positions, price_today, nav)}, {**decision, "weight_after_buy": gate.target_weight}, group_cfg)
            group_rows.append({"date": signal_date, "variant": variant.name, "symbol": decision.get("symbol"), **cap})
            if not cap.get("allowed"):
                signal_trace_rows.append(_overlay_trace_row(signal_date, variant.name, decision, QUALITY_FILL_ACTION, "WATCH_ONLY", GROUP_CAP_BLOCKED))
                continue
        selected.append((decision, gate))
        signal_trace_rows.append(_overlay_trace_row(signal_date, variant.name, decision, QUALITY_FILL_ACTION, "SELECTED", ""))
        total_quality_fills += 1
        month_quality_fills += 1
        break
    return selected, total_quality_fills, month_quality_fills


def _select_winner_add(
    *,
    signal_date: str,
    variant: DeploymentRepairVariant,
    config: dict[str, Any],
    holding_decisions: list[dict[str, Any]],
    params: CoreParams,
    nav: float,
    cash: float,
    positions: dict[str, Position],
    price_today: pd.DataFrame,
    regime: object,
    month_winner_adds: int,
    winner_rows: list[dict[str, Any]],
    group_rows: list[dict[str, Any]],
    signal_trace_rows: list[dict[str, Any]],
) -> tuple[list[tuple[dict[str, Any], compact.GateResult]], int]:
    if not variant.winner_add_enabled or month_winner_adds >= 1:
        return [], month_winner_adds
    cash_ratio = cash / max(nav, 1e-9)
    ranked = sorted(holding_decisions, key=lambda row: (-_safe_float(row.get("unrealized_pnl_pct")), -_safe_float(row.get("expected_edge_score")), str(row.get("symbol"))))
    for holding in ranked:
        symbol = str(holding.get("symbol"))
        if symbol not in positions:
            continue
        price = _safe_float(holding.get("close"))
        position = positions[symbol]
        current_weight = position.shares * price / max(nav, 1e-9) if price > 0 else _safe_float(holding.get("current_weight"))
        state = {
            "market_regime": _regime_name(regime),
            "cash_ratio": cash_ratio,
            "positions_count": len(positions),
            "winner_adds_this_month": month_winner_adds,
        }
        if variant.financial_group_cap_enabled:
            cap_probe = evaluate_group_concentration(
                {"positions": _portfolio_positions_for_group(positions, price_today, nav)},
                {**holding, "weight_after_buy": min(variant.winner_max_single_stock_weight, current_weight + price * params.round_lot / max(nav, 1e-9))},
                _group_cfg(config, variant),
            )
            state["group_cap_result"] = cap_probe
            group_rows.append({"date": signal_date, "variant": variant.name, "symbol": symbol, **cap_probe})
        result = compute_winner_add_candidate({**holding, "shares": position.shares, "current_weight": current_weight}, state, _winner_cfg(variant))
        winner_rows.append({"date": signal_date, "variant": variant.name, "symbol": symbol, **result})
        if not result["eligible"]:
            continue
        target_weight = min(variant.winner_max_single_stock_weight, current_weight + price * params.round_lot / max(nav, 1e-9))
        decision = copy.deepcopy(holding)
        decision["action_enum"] = WINNER_ADD_ACTION
        decision["signal_level"] = WINNER_ADD_ACTION
        gate = compact.GateResult(True, "", target_weight, max(0.0, target_weight * nav - position.shares * price), price * params.round_lot, "ADD")
        signal_trace_rows.append(_overlay_trace_row(signal_date, variant.name, decision, WINNER_ADD_ACTION, "SELECTED", ""))
        return [(decision, gate)], month_winner_adds + 1
    return [], month_winner_adds


def _load_cash_sleeve_market_data(feature_by_date: dict[str, pd.DataFrame], instruments: list[str]) -> dict[str, pd.DataFrame]:
    wanted = set(instruments) | {f"{item}.sh" for item in instruments} | {f"{item}.sz" for item in instruments}
    rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for date, frame in feature_by_date.items():
        if "symbol" not in frame.columns:
            continue
        subset = frame[frame["symbol"].astype(str).isin(wanted)]
        for row in subset.to_dict(orient="records"):
            symbol = str(row.get("symbol", ""))
            rows[symbol.replace(".sh", "").replace(".sz", "")].append({"date": date, "close": row.get("close"), "open": row.get("open")})
    return {symbol: pd.DataFrame(items) for symbol, items in rows.items() if items}


def run_deployment_repair_backtest(
    variant: DeploymentRepairVariant,
    *,
    feature_by_date: dict[str, pd.DataFrame],
    benchmark: pd.DataFrame,
    configs: dict[str, Any],
    deployment_config: dict[str, Any],
    cash_sleeve_market_data: dict[str, pd.DataFrame] | None = None,
    trace_reason_counts: dict[str, int] | None = None,
) -> dict[str, Any]:
    params = variant.params
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
    position_rows: list[dict[str, Any]] = []
    replacement_rows: list[dict[str, Any]] = []
    quality_rows: list[dict[str, Any]] = []
    winner_rows: list[dict[str, Any]] = []
    group_rows: list[dict[str, Any]] = []
    signal_trace_rows: list[dict[str, Any]] = []
    cash_sleeve_rows: list[dict[str, Any]] = []
    month_replacements: Counter[str] = Counter()
    month_quality_fills: Counter[str] = Counter()
    month_winner_adds: Counter[str] = Counter()
    total_quality_fills = 0

    compact_params = compact.CompactParams(
        max_positions=params.max_positions,
        max_tranches=params.max_tranches,
        target_universe_size=params.target_universe_size,
        cash_reserve_ratio=params.cash_reserve_ratio,
        max_new_positions_per_day=params.max_new_positions_per_day,
        max_adds_per_day=1,
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
        month = signal_date[:7]
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
        replacement_trades_today: list[dict[str, Any]] = []

        if params.partial_derisk_enabled:
            for symbol in list(positions.keys()):
                if symbol not in price_today.index:
                    continue
                row = price_today.loc[symbol].to_dict()
                position = positions[symbol]
                row.update({"symbol": symbol, "shares": position.shares, "round_lot": params.round_lot, "unrealized_pnl_pct": (_safe_float(row.get("close")) / position.avg_cost - 1.0) if position.avg_cost > 0 else 0.0})
                derisk = evaluate_partial_derisk(row, {"round_lot": params.round_lot, "single_lot_hold_with_risk_flag": params.single_lot_hold_with_risk_flag})
                if derisk.get("action") in {"REDUCE", "SELL_ALL"}:
                    cash, positions, derisk_trade = _execute_partial_derisk(signal_date=signal_date, fill_date=fill_date, symbol=symbol, derisk=derisk, params=params, price_frame=next_day, positions=positions, cash=cash)
                    if derisk_trade:
                        derisk_trade["variant"] = variant.name
                        trades.append(derisk_trade)

        for decision in decisions:
            if decision.get("action_enum") not in SELL_ACTIONS:
                continue
            cash, positions, trade = compact._execute_sell(fill_date=fill_date, decision=decision, params=compact_params, price_frame=next_day, positions=positions, cash=cash, nav=nav)
            if trade:
                trade["variant"] = variant.name
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
            month_replacement_count=month_replacements[month],
        )
        selected = _apply_group_cap_to_selected(
            selected=selected,
            signal_date=signal_date,
            variant=variant,
            config=deployment_config,
            positions=positions,
            price_today=price_today,
            nav=nav,
            group_rows=group_rows,
            signal_trace_rows=signal_trace_rows,
        )
        watch_records.extend(day_watch)

        has_stock_buy = bool(selected or replacement_plans[:1])
        q_selected: list[tuple[dict[str, Any], compact.GateResult]] = []
        if not has_stock_buy:
            if variant.market_regime_review_enabled and _regime_name(regime) in {"neutral", "risk_on"}:
                review_decisions = []
                for item in decisions:
                    if str(item.get("symbol")) in positions or str(item.get("bucket")) == "cyclical_rotation":
                        continue
                    enriched = _candidate_quality_fields(item)
                    policy = _core_policy(params, nav=nav, regime=regime, industry_counts=Counter(position.industry for position in positions.values()))
                    enriched.update(compute_50k_expected_edge_score(enriched, policy))
                    enriched.update({"market_regime": _regime_name(regime), "cash_ratio": cash / max(nav, 1e-9), "is_quality_defensive_fill": True})
                    review = evaluate_market_regime_review_fill(enriched, {})
                    if review["allowed"]:
                        review_decisions.append((enriched, review))
                if review_decisions:
                    chosen = sorted(review_decisions, key=lambda pair: (-_safe_float(pair[0].get("expected_edge_score")), str(pair[0].get("symbol"))))[0][0]
                    chosen["action_enum"] = REGIME_REVIEW_ACTION
                    chosen["signal_level"] = REGIME_REVIEW_ACTION
                    gate = core_account_gate(chosen, params, nav=nav, cash=cash, positions_count=len(positions), industry_position_count=sum(1 for position in positions.values() if position.industry == str(chosen.get("industry"))), new_buys_today=0, adds_today=0, regime=_regime_name(regime))
                    if gate.actionable:
                        q_selected.append((chosen, gate))
                        signal_trace_rows.append(_overlay_trace_row(signal_date, variant.name, chosen, REGIME_REVIEW_ACTION, "SELECTED", ""))
            if not q_selected:
                q_selected, total_quality_fills, month_quality_fills[month] = _select_quality_fill(
                    signal_date=signal_date,
                    variant=variant,
                    config=deployment_config,
                    decisions=decisions,
                    params=params,
                    nav=nav,
                    cash=cash,
                    positions=positions,
                    price_today=price_today,
                    regime=regime,
                    total_quality_fills=total_quality_fills,
                    month_quality_fills=month_quality_fills[month],
                    quality_rows=quality_rows,
                    group_rows=group_rows,
                    signal_trace_rows=signal_trace_rows,
                )
        selected.extend(q_selected)

        w_selected: list[tuple[dict[str, Any], compact.GateResult]] = []
        if not selected and not replacement_plans[:1]:
            w_selected, month_winner_adds[month] = _select_winner_add(
                signal_date=signal_date,
                variant=variant,
                config=deployment_config,
                holding_decisions=holding_decisions,
                params=params,
                nav=nav,
                cash=cash,
                positions=positions,
                price_today=price_today,
                regime=regime,
                month_winner_adds=month_winner_adds[month],
                winner_rows=winner_rows,
                group_rows=group_rows,
                signal_trace_rows=signal_trace_rows,
            )
        selected.extend(w_selected)

        for plan in replacement_plans[:1]:
            cash, positions, replacement_trades, replacement_report = _execute_replacement(signal_date=signal_date, fill_date=fill_date, plan=plan, params=params, price_frame=next_day, positions=positions, cash=cash, nav=nav)
            if replacement_trades:
                for trade in replacement_trades:
                    trade["variant"] = variant.name
                trades.extend(replacement_trades)
                replacement_trades_today.extend(replacement_trades)
                month_replacements[month] += 1
            if replacement_report:
                replacement_report["variant"] = variant.name
                replacement_rows.append(replacement_report)

        for decision, gate in selected:
            cash, positions, trade, watch = compact._execute_buy(signal_date=signal_date, fill_date=fill_date, decision=decision, gate=gate, params=compact_params, price_frame=next_day, positions=positions, cash=cash, nav=nav)
            if trade:
                trade["variant"] = variant.name
                if decision.get("action_enum") == QUALITY_FILL_ACTION:
                    trade["deployment_repair_overlay"] = "quality_defensive_fill"
                elif decision.get("action_enum") == WINNER_ADD_ACTION:
                    trade["deployment_repair_overlay"] = "winner_add"
                elif decision.get("action_enum") == REGIME_REVIEW_ACTION:
                    trade["deployment_repair_overlay"] = "market_regime_review"
                trades.append(trade)
            if watch:
                watch["variant"] = variant.name
                watch_records.append(watch)

        cash_context = {
            "market_regime": _regime_name(regime),
            "cash_ratio": cash / max(compact._portfolio_value(cash, positions, next_day), 1e-9),
            "no_executable_stock_buy": len(trades) == day_trades_before,
            "no_quality_defensive_fill": not q_selected,
            "no_winner_add": not w_selected,
            "cash": cash,
            "nav": compact._portfolio_value(cash, positions, next_day),
        }
        cash_eval = evaluate_cash_sleeve_research(cash_context, cash_sleeve_market_data or {}, {"max_weight_risk_on": variant.cash_sleeve_max_weight, "cash": cash, "nav": cash_context["nav"], "round_lot": params.round_lot}) if variant.cash_sleeve_enabled else {"cash_sleeve_data_available": bool(cash_sleeve_market_data), "cash_sleeve_trades": [], "cash_sleeve_trades_count": 0, "cash_sleeve_pnl": 0.0, "feasibility_only": not bool(cash_sleeve_market_data)}
        cash_sleeve_rows.append({"date": signal_date, "variant": variant.name, **{key: value for key, value in cash_eval.items() if key != "cash_sleeve_trades"}})
        for trade in cash_eval.get("cash_sleeve_trades", []):
            cash_trade = {
                "date": fill_date,
                "signal_date": signal_date,
                "variant": variant.name,
                "symbol": trade["symbol"],
                "ts_code": trade["symbol"],
                "name": trade["symbol"],
                "industry": "cash_sleeve",
                "bucket": "cash_sleeve_research",
                "side": "BUY",
                "action": CASH_SLEEVE_ACTION,
                "signal_level": CASH_SLEEVE_LABEL,
                "shares": trade["shares"],
                "price": trade["price"],
                "amount": trade["amount"],
                "fee": 0.0,
                "tax": 0.0,
                "cash_before": cash,
                "cash_after": cash - trade["amount"],
                "target_weight": variant.cash_sleeve_max_weight,
                "realized_pnl": 0.0,
                "execution_mode": "next_bar",
                "deployment_repair_overlay": "cash_sleeve_research",
            }
            if trade["amount"] <= cash:
                cash -= trade["amount"]
                trades.append(cash_trade)

        fill_nav = compact._portfolio_value(cash, positions, next_day)
        invested = max(0.0, fill_nav - cash)
        executed_today = trades[day_trades_before:]
        daily_rows.append(
            {
                "date": signal_date,
                "variant": variant.name,
                "market_regime": _regime_name(regime),
                "raw_buy_signal_count": raw_buy_count,
                "account_actionable_buy_count": len(selected) + len(replacement_plans[:1]),
                "watch_only_count": len(day_watch),
                "executable_buy_count": sum(1 for item in executed_today if item.get("side") == "BUY" and item.get("bucket") != "cash_sleeve_research"),
                "holdings_count": len(positions),
                "cash": cash,
                "nav": fill_nav,
                "cash_ratio": cash / max(fill_nav, 1e-9),
                "exposure": invested / max(fill_nav, 1e-9),
                "quality_defensive_fill_executed_today": sum(1 for item in executed_today if item.get("deployment_repair_overlay") == "quality_defensive_fill"),
                "winner_add_executed_today": sum(1 for item in executed_today if item.get("deployment_repair_overlay") == "winner_add"),
                "market_regime_review_fills_today": sum(1 for item in executed_today if item.get("deployment_repair_overlay") == "market_regime_review"),
                "cash_sleeve_trades_today": sum(1 for item in executed_today if item.get("deployment_repair_overlay") == "cash_sleeve_research"),
                "replacement_count": len(replacement_trades_today) // 2,
            }
        )
        nav_records.append({"date": fill_date, "nav": fill_nav, "cash": cash, "exposure": invested / max(fill_nav, 1e-9), "holdings_count": len(positions)})
        for symbol, position in positions.items():
            price = _safe_float(next_day.loc[symbol, "close"]) if symbol in next_day.index and "close" in next_day.columns else position.last_fill_price
            position_rows.append(
                {
                    "date": signal_date,
                    "variant": variant.name,
                    "symbol": symbol,
                    "bucket": position.bucket,
                    "industry": position.industry,
                    "shares": position.shares,
                    "close": price,
                    "market_value": position.shares * price,
                    "position_weight": position.shares * price / max(fill_nav, 1e-9),
                    "unrealized_pnl": (price - position.avg_cost) * position.shares,
                    "future_return_used": False,
                }
            )

    nav_frame = pd.DataFrame(nav_records)
    trade_frame = pd.DataFrame(trades)
    daily = pd.DataFrame(daily_rows)
    watch = pd.DataFrame(watch_records)
    metrics = compact._metrics(nav_frame, trade_frame, params.capital)
    final_prices = feature_by_date[dates[-1]].set_index("symbol")
    attribution = _attribution(trades=trade_frame, positions=positions, price_frame=final_prices)
    reason_counts = Counter(watch.get("reason_code", pd.Series(dtype=str)).dropna().astype(str).tolist()) if not watch.empty else Counter()
    risk_on_daily = daily[daily.get("market_regime", pd.Series(dtype=str)) == "risk_on"] if not daily.empty else pd.DataFrame()
    executable_buy_count = int(metrics.get("buy_trades", 0)) - int(sum(1 for item in trades if item.get("bucket") == "cash_sleeve_research"))
    account_actionable = int(daily.get("account_actionable_buy_count", pd.Series(dtype=int)).sum()) if not daily.empty else 0
    q_executed = int(daily.get("quality_defensive_fill_executed_today", pd.Series(dtype=int)).sum()) if not daily.empty else 0
    w_executed = int(daily.get("winner_add_executed_today", pd.Series(dtype=int)).sum()) if not daily.empty else 0
    review_fills = int(daily.get("market_regime_review_fills_today", pd.Series(dtype=int)).sum()) if not daily.empty else 0
    cash_sleeve_trades = int(daily.get("cash_sleeve_trades_today", pd.Series(dtype=int)).sum()) if not daily.empty else 0
    base_reasons = trace_reason_counts or {}
    payload = {
        "variant": variant.name,
        "base_repair_variant": REPAIR_BEST_VARIANT,
        "profile": PROFILE_NAME,
        "research_only": True,
        "stock_only": variant.stock_only,
        "mechanisms_enabled": ",".join(variant.mechanisms_enabled),
        "capital": params.capital,
        "round_lot": params.round_lot,
        "max_positions": params.max_positions,
        "max_single_stock_weight": params.max_single_stock_weight,
        "cyclical_max_positions": 0,
        "annual_return": metrics.get("annual_return", 0.0),
        "cumulative_return": metrics.get("cumulative_return", 0.0),
        "max_drawdown": metrics.get("max_drawdown", 0.0),
        "sharpe": metrics.get("sharpe", 0.0),
        "total_trades": metrics.get("total_trades", 0),
        "buy_trades": metrics.get("buy_trades", 0),
        "sell_trades": metrics.get("sell_trades", 0),
        "average_exposure": metrics.get("avg_daily_exposure", 0.0),
        "avg_cash_ratio_in_risk_on": float(risk_on_daily.get("cash_ratio", pd.Series(dtype=float)).mean()) if not risk_on_daily.empty else metrics.get("average_cash_ratio", 1.0),
        **{key: value for key, value in attribution.items() if not isinstance(value, dict)},
        "quality_defensive_fill_candidates": int(sum(1 for row in quality_rows if row.get("eligible"))),
        "quality_defensive_fill_executed": q_executed,
        "winner_add_candidates": int(sum(1 for row in winner_rows if row.get("eligible"))),
        "winner_add_executed": w_executed,
        "financial_group_cap_blocks": int(sum(1 for row in group_rows if not row.get("allowed", True))),
        "market_regime_review_fills": review_fills,
        "cash_sleeve_trades": cash_sleeve_trades,
        "cash_sleeve_pnl": 0.0,
        "cash_sleeve_data_available": bool(cash_sleeve_market_data),
        "no_raw_signal_risk_on_days": max(0, int(base_reasons.get("NO_RAW_SIGNAL", 0)) - q_executed),
        "cyclical_disabled_or_blocked_days": int(base_reasons.get("CYCLICAL_DISABLED_OR_BLOCKED", 0)),
        "executable_account_actionable_ratio": _ratio_or_none(executable_buy_count, account_actionable),
        "replacement_count": int(len(replacement_rows)),
        "top_watch_only_reasons": dict(reason_counts.most_common(5)),
        "auto_trading_approved": False,
        "broker_integration_enabled": False,
        "llm_decision_allowed": False,
        "writes_real_trades": False,
        "release_profile_replacement": False,
        "_daily_rows": daily_rows,
        "_position_rows": position_rows,
        "_trade_rows": trades,
        "_signal_trace_rows": signal_trace_rows,
        "_exit_trace_rows": [],
        "_replacement_rows": replacement_rows,
        "_quality_rows": quality_rows,
        "_winner_rows": winner_rows,
        "_group_rows": group_rows,
        "_cash_sleeve_rows": cash_sleeve_rows,
        "_attribution_detail": attribution,
    }
    flags = []
    if q_executed > 0 and _safe_float(payload["max_drawdown"]) < -0.16:
        flags.append("QUALITY_FILL_OVERTRADING_OR_LOW_EDGE")
    if w_executed > 0 and _safe_float(payload["largest_single_stock_pnl_contribution"]) > 0.45:
        flags.append("WINNER_ADD_CONCENTRATION_RISK")
    if variant.financial_group_cap_enabled and _safe_float(payload["annual_return"]) < 0.08 and _safe_float(payload["max_drawdown"]) > -0.16:
        flags.append("GROUP_CAP_RETURN_TRADEOFF")
    payload["risk_flags"] = ",".join(flags)
    return payload


def _trace_reason_counts(trace_dir: str | Path = PHASE3_TRACE_DIR) -> dict[str, int]:
    path = resolve_path(Path(trace_dir) / "risk_on_cash_trace.csv")
    if not path.exists():
        return {}
    frame = pd.read_csv(path)
    if "reason_cash_not_deployed" not in frame.columns:
        return {}
    return {str(key): int(value) for key, value in frame["reason_cash_not_deployed"].value_counts(dropna=False).to_dict().items()}


def _repair_best_metrics() -> dict[str, Any]:
    path = resolve_path(REPAIR_BEST_PATH)
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data.get("closest_attempt") or data


def _public_row(row: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if not key.startswith("_")}


def _evaluation(config: dict[str, Any] | None) -> dict[str, Any]:
    config = config or {}
    return {**DEFAULT_EVALUATION, **(((config.get("evaluation") or {}).get("hard_conditions")) or {})}


def _distance_to_pass(row: dict[str, Any], evaluation: dict[str, Any]) -> float:
    distance = 0.0
    distance += max(0.0, _safe_float(evaluation["annual_return_min_absolute"]) - _safe_float(row.get("annual_return"))) * 8
    distance += max(0.0, _safe_float(evaluation["sharpe_min"]) - _safe_float(row.get("sharpe"))) * 1.5
    distance += max(0.0, _safe_float(evaluation["max_drawdown_floor"]) - _safe_float(row.get("max_drawdown"))) * 6
    distance += max(0.0, _safe_int(evaluation["total_trades_min"]) - _safe_int(row.get("total_trades"))) / 50
    distance += max(0.0, _safe_float(row.get("avg_cash_ratio_in_risk_on"), 1.0) - _safe_float(evaluation["avg_cash_ratio_max_in_risk_on"])) * 4
    return round(float(distance), 6)


def _score_deployment_rows(rows: list[dict[str, Any]], config: dict[str, Any] | None) -> pd.DataFrame:
    evaluation = _evaluation(config)
    public = []
    for row in rows:
        payload = _public_row(row)
        payload.setdefault("stock_only", "cash_sleeve_research" not in str(payload.get("mechanisms_enabled", "")))
        payload.update(evaluate_hard_conditions(payload, evaluation))
        payload["distance_to_pass"] = _distance_to_pass(payload, evaluation)
        public.append(payload)
    frame = pd.DataFrame(public)
    if frame.empty:
        return frame
    frame = _score_rows(frame)
    frame = frame.sort_values(["pass_hard_conditions", "stock_only", "distance_to_pass", "selection_score", "annual_return"], ascending=[False, False, True, False, False]).reset_index(drop=True)
    return frame


def is_stock_only_pass(row: dict[str, Any]) -> bool:
    return bool(row.get("pass_hard_conditions")) and bool(row.get("stock_only", True)) and "cash_sleeve_research" not in str(row.get("mechanisms_enabled", ""))


def _write_report(path: Path, frame: pd.DataFrame, summary: dict[str, Any]) -> None:
    lines = [
        "# combined_v2_50k_core phase4 deployment repair report",
        "",
        "- research_only: true",
        "- auto_trading_approved: false",
        "- broker_integration_enabled: false",
        "- llm_decision_allowed: false",
        "- writes_real_trades: false",
        "- release_profile_replacement: false",
        "",
        "## 本轮定位",
        "",
        "本轮不是继续调参，也不是扩展参数网格；它只基于 phase3 trace 结论测试小规模机制修复。",
        "",
        "## phase3 trace 结论摘要",
        "",
        "- risk-on cash 主要来自 NO_RAW_SIGNAL 与 CYCLICAL_DISABLED_OR_BLOCKED；phase2 的 PORTFOLIO_FULL 判断已被修正，真正满仓高现金只有 2 天。",
        "- 2025-03 最大回撤集中在 defensive_dividend，行业集中于银行、非银金融和公用事业。",
        "- 回撤期间平均 exposure 43.70%，不是仓位过高导致。",
        "- exit/replacement 没有明确滞后或应触发未触发证据。",
        "- 2023-05-12 到 2024-10-29 长期无买入主要来自 MARKET_REGIME_BLOCK，其次 DAILY_ADD_LIMIT。",
        "",
        "## 本轮机制",
        "",
        "- quality_defensive_fill: 只在 risk_on、高现金且无股票可执行买入时，从 effective universe 补充非周期高质量防御候选。",
        "- winner_add: 只加已有盈利持仓，禁止补亏损，限制单票权重和每月次数。",
        "- financial_group_cap: 银行+非银金融合并限额，公用事业单独限额，只阻断新增，不强制卖出。",
        "- market_regime_block_review: 不取消 regime block，只允许 neutral/risk_on 下严格复核的 quality defensive fill。",
        "- cash_sleeve_research: 只在仓库有真实 ETF/现金替代行情时研究；无数据时仅输出 feasibility。",
        "",
        "## top variants",
        "",
    ]
    cols = [
        "variant",
        "mechanisms_enabled",
        "annual_return",
        "max_drawdown",
        "sharpe",
        "total_trades",
        "avg_cash_ratio_in_risk_on",
        "quality_defensive_fill_executed",
        "winner_add_executed",
        "financial_group_cap_blocks",
        "market_regime_review_fills",
        "cash_sleeve_trades",
        "pass_hard_conditions",
        "fail_reasons",
    ]
    if frame.empty:
        lines.append("No variants were run.")
    else:
        lines.append(frame[[col for col in cols if col in frame.columns]].head(24).to_markdown(index=False))
    lines.extend(
        [
            "",
            "## hard condition result",
            "",
            f"- variant_count: {summary['variant_count']}",
            f"- hard_condition_pass_count: {summary['hard_condition_pass_count']}",
            f"- stock_only_pass_count: {summary['stock_only_pass_count']}",
            f"- cash_sleeve_overlay_pass_count: {summary['cash_sleeve_overlay_pass_count']}",
            f"- closest_to_pass_variant: {summary.get('closest_to_pass_variant', {}).get('variant', 'none')}",
            "",
            "## stock-only vs cash sleeve",
            "",
            "- cash sleeve PnL is reported separately and is not counted as stock alpha.",
            "- If cash sleeve is the only pass, stock-only 50k core is still treated as not passed.",
            "",
            "## trace questions",
            "",
            build_deployment_trace_diagnostic_report(summary),
            "",
            "## conclusion",
            "",
            f"- stock_only_candidate_passed: {str(summary['stock_only_pass_count'] > 0).lower()}",
            f"- cash_sleeve_overlay_candidate_passed: {str(summary['cash_sleeve_overlay_pass_count'] > 0).lower()}",
            "- cyclical bucket remains watch-only.",
            "- This does not allow automatic live trading.",
            "- This does not replace the default release profile.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_observation(path: Path, summary: dict[str, Any], robustness: dict[str, Any]) -> None:
    best = summary.get("best_candidate") or {}
    if best and best.get("pass_hard_conditions") and robustness.get("status") != "FRAGILE":
        lines = [
            "# deployment repair observation candidate",
            "",
            f"- candidate_variant: {best.get('variant')}",
            f"- cash_sleeve_research_overlay: {str(not bool(best.get('stock_only'))).lower()}",
            "- research_only: true",
            "- auto_trading_approved: false",
            "- release_profile_replacement: false",
            f"- robustness: {robustness.get('status')}",
        ]
    else:
        reason = "no hard-condition pass" if not best or not best.get("pass_hard_conditions") else "hard pass is FRAGILE"
        lines = [
            "# deployment repair observation note",
            "",
            "- formal_observation_candidate: false",
            f"- reason: {reason}",
            "- research_only: true",
            "- auto_trading_approved: false",
            "- release_profile_replacement: false",
            "- do_not_market_as_candidate: true",
        ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_comparison(path: Path, best: dict[str, Any], repair_best: dict[str, Any]) -> None:
    lines = ["# deployment repair comparison vs repair best", ""]
    if not best:
        lines.append("- best_variant: none")
    else:
        for key in ["variant", "annual_return", "cumulative_return", "max_drawdown", "sharpe", "total_trades", "avg_cash_ratio_in_risk_on"]:
            current = best.get(key)
            base = repair_best.get(key)
            if isinstance(current, float) or isinstance(base, float):
                lines.append(f"- {key}: deployment={_pct(current)} repair_best={_pct(base)}")
            else:
                lines.append(f"- {key}: deployment={current} repair_best={base}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_cash_feasibility(path: Path, rows: list[dict[str, Any]], cash_available: bool) -> None:
    lines = [
        "# deployment repair cash sleeve feasibility",
        "",
        f"- cash_sleeve_data_available: {str(cash_available).lower()}",
        "- research_only: true",
        "- live_approval: false",
    ]
    if not cash_available:
        lines.extend(
            [
                "- result: feasibility_only",
                "- reason: no real historical data for 510300/510050/510880/511880 was found in the existing backtest feature window.",
                "- cash_sleeve_trades: 0",
                "- no ETF prices were fabricated and no index proxy was substituted.",
            ]
        )
    else:
        trades = sum(int(row.get("cash_sleeve_trades_count", 0)) for row in rows)
        lines.extend([f"- cash_sleeve_trades: {trades}", "- cash_sleeve_pnl is reported separately from stock sleeve PnL."])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _compact_quality_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    compact_rows = []
    for row in rows:
        trace = row.get("trace_fields") or {}
        fail = row.get("fail_reasons") or []
        if isinstance(fail, list):
            fail_text = ",".join(str(item) for item in fail)
        else:
            fail_text = str(fail)
        compact_rows.append(
            {
                "date": row.get("date"),
                "variant": row.get("variant"),
                "symbol": row.get("symbol") or trace.get("symbol"),
                "bucket": trace.get("bucket"),
                "industry": trace.get("industry"),
                "threshold_profile": row.get("threshold_profile"),
                "eligible": bool(row.get("eligible")),
                "action_label": row.get("action_label"),
                "fill_score": row.get("fill_score"),
                "fail_reasons": fail_text,
                "lot_notional": trace.get("lot_notional"),
                "stock_q_blended": trace.get("stock_q_blended"),
                "dv_ttm": trace.get("dv_ttm"),
                "future_return_used": bool(trace.get("future_return_used", False)),
            }
        )
    return compact_rows


def _compact_winner_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    compact_rows = []
    for row in rows:
        trace = row.get("trace_fields") or {}
        fail = row.get("fail_reasons") or []
        if isinstance(fail, list):
            fail_text = ",".join(str(item) for item in fail)
        else:
            fail_text = str(fail)
        compact_rows.append(
            {
                "date": row.get("date"),
                "variant": row.get("variant"),
                "symbol": row.get("symbol") or trace.get("symbol"),
                "eligible": bool(row.get("eligible")),
                "action_label": row.get("action_label"),
                "fail_reasons": fail_text,
                "extra_lots": row.get("extra_lots"),
                "unrealized_pnl_pct": trace.get("unrealized_pnl_pct"),
                "current_weight": trace.get("current_weight"),
                "max_single_stock_weight": trace.get("max_single_stock_weight"),
                "future_return_used": bool(trace.get("future_return_used", False)),
            }
        )
    return compact_rows


def select_trace_variants(rows: list[dict[str, Any]]) -> list[str]:
    selected: list[str] = []

    def add(name: str | None) -> None:
        if name and name not in selected and len(selected) < 4:
            selected.append(name)

    add("repair_best_baseline")
    stock_pass = sorted([row for row in rows if is_stock_only_pass(row)], key=lambda row: -_safe_float(row.get("selection_score")))
    add(stock_pass[0]["variant"] if stock_pass else None)
    cash_rows = sorted([row for row in rows if not row.get("stock_only", True) and row.get("cash_sleeve_data_available")], key=lambda row: -_safe_float(row.get("selection_score")))
    add(cash_rows[0]["variant"] if cash_rows else None)
    closest = sorted(rows, key=lambda row: (_safe_float(row.get("distance_to_pass"), 999), -_safe_float(row.get("selection_score"))))
    add(closest[0]["variant"] if closest else None)
    return selected[:4]


def build_deployment_trace_diagnostic_report(summary: dict[str, Any]) -> str:
    q_exec = int(_safe_float(summary.get("quality_defensive_fill_executed", 0)))
    w_exec = int(_safe_float(summary.get("winner_add_executed", 0)))
    group_blocks = int(_safe_float(summary.get("financial_group_cap_blocks", 0)))
    review = int(_safe_float(summary.get("market_regime_review_fills", 0)))
    cash_available = bool(summary.get("cash_sleeve_data_available", False))
    flags = summary.get("overtrading_flags") or summary.get("risk_flags") or []
    if isinstance(flags, str):
        flags = [item for item in flags.split(",") if item]
    lines = [
        "1. quality_defensive_fill: " + ("减少了部分 NO_RAW_SIGNAL 高现金日。" if q_exec else "未形成可执行填补，NO_RAW_SIGNAL 未实质减少。"),
        "2. winner_add: " + ("产生加仓并降低部分 risk-on cash。" if w_exec else "未形成可执行加仓，risk-on cash 改善有限。"),
        "3. financial_group_cap: " + (f"阻断 {group_blocks} 个金融/公用事业集中新增，属于诊断性降集中。" if group_blocks else "没有新增阻断，2025-03 类似集中暴露未被显著改变。"),
        "4. market_regime_review: " + (f"产生 {review} 笔严格复核 fill，对 2023-05 到 2024-10 无买入区间有局部改善。" if review else "没有产生 fill，长期无买入未被实质修复。"),
        "5. cash sleeve: " + ("有真实数据，可单独归因；需防止掩盖股票策略不足。" if cash_available else "没有真实 ETF 数据，只能输出 feasibility，不能掩盖股票策略不足。"),
        "6. 过度交易或集中度恶化: " + (",".join(flags) if flags else "未发现新增标记。"),
    ]
    return "\n".join(lines)


def _write_trace_outputs(rows: list[dict[str, Any]], frame: pd.DataFrame, summary: dict[str, Any], out_dir: Path) -> None:
    trace_dir = out_dir / "traces"
    trace_dir.mkdir(parents=True, exist_ok=True)
    selected = set(select_trace_variants(frame.to_dict(orient="records") if not frame.empty else []))
    chosen_rows = [row for row in rows if row.get("variant") in selected]
    daily = []
    position = []
    trades = []
    signal = []
    exits = []
    replacement = []
    for row in chosen_rows:
        daily.extend(row.get("_daily_rows", []))
        position.extend(row.get("_position_rows", []))
        trades.extend(row.get("_trade_rows", []))
        signal.extend(row.get("_signal_trace_rows", []))
        exits.extend(row.get("_exit_trace_rows", []))
        replacement.extend(row.get("_replacement_rows", []))
    pd.DataFrame(daily or [{"variant": "", "date": "", "future_return_used": False}]).to_csv(trace_dir / "daily_portfolio_ledger.csv", index=False)
    pd.DataFrame(position or [{"variant": "", "date": "", "symbol": "", "future_return_used": False}]).to_csv(trace_dir / "daily_position_pnl.csv", index=False)
    pd.DataFrame(trades or [{"variant": "", "date": "", "symbol": "", "side": "", "future_return_used": False}]).to_csv(trace_dir / "trade_ledger.csv", index=False)
    pd.DataFrame(signal or [{"variant": "", "date": "", "symbol": "", "future_return_used": False}]).to_csv(trace_dir / "signal_execution_trace.csv", index=False)
    pd.DataFrame(exits or [{"variant": "", "date": "", "symbol": "", "future_return_used": False}]).to_csv(trace_dir / "exit_rule_trace.csv", index=False)
    pd.DataFrame(replacement or [{"variant": "", "date": "", "candidate_symbol": "", "future_return_used": False}]).to_csv(trace_dir / "replacement_candidate_trace.csv", index=False)
    (trace_dir / "deployment_repair_trace_diagnostic_report.md").write_text(
        "# deployment repair trace diagnostic report\n\n" + build_deployment_trace_diagnostic_report(summary) + "\n\n- trace_variant_count: " + str(len(selected)) + "\n",
        encoding="utf-8",
    )


def write_deployment_repair_outputs(rows: list[dict[str, Any]], effective_config: dict[str, Any] | None = None, output_dir: str | Path | None = None) -> dict[str, Any]:
    out_dir = resolve_path(output_dir or OUT_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    frame = _score_deployment_rows(rows, effective_config)
    frame.to_csv(out_dir / "deployment_repair_metrics.csv", index=False)
    candidates = frame[frame["pass_hard_conditions"].astype(bool)] if not frame.empty else pd.DataFrame()
    stock_candidates = candidates[candidates.apply(lambda row: is_stock_only_pass(row.to_dict()), axis=1)] if not candidates.empty else pd.DataFrame()
    cash_candidates = candidates[(~candidates.get("stock_only", pd.Series(dtype=bool)).astype(bool))] if not candidates.empty and "stock_only" in candidates.columns else pd.DataFrame()
    best = (stock_candidates.iloc[0].to_dict() if not stock_candidates.empty else (candidates.iloc[0].to_dict() if not candidates.empty else (frame.iloc[0].to_dict() if not frame.empty else {})))
    robustness = evaluate_neighborhood_robustness(best, frame.to_dict(orient="records")[:8], _evaluation(effective_config)) if best and best.get("pass_hard_conditions") else {"status": "FRAGILE", "neighbor_count": 0, "support_count_excluding_best": 0}
    summary = {
        "variant_count": int(len(frame)),
        "hard_condition_pass_count": int(len(candidates)),
        "stock_only_pass_count": int(len(stock_candidates)),
        "cash_sleeve_overlay_pass_count": int(len(cash_candidates)),
        "best_candidate": best if best and best.get("pass_hard_conditions") else {},
        "closest_to_pass_variant": best,
        "robustness": robustness.get("status"),
        "quality_defensive_fill_executed": int(frame.get("quality_defensive_fill_executed", pd.Series(dtype=int)).max() if not frame.empty else 0),
        "winner_add_executed": int(frame.get("winner_add_executed", pd.Series(dtype=int)).max() if not frame.empty else 0),
        "financial_group_cap_blocks": int(frame.get("financial_group_cap_blocks", pd.Series(dtype=int)).max() if not frame.empty else 0),
        "market_regime_review_fills": int(frame.get("market_regime_review_fills", pd.Series(dtype=int)).max() if not frame.empty else 0),
        "cash_sleeve_data_available": bool(frame.get("cash_sleeve_data_available", pd.Series(dtype=bool)).any() if not frame.empty else False),
        "overtrading_flags": sorted({flag for item in frame.get("risk_flags", pd.Series(dtype=str)).dropna().astype(str) for flag in item.split(",") if flag}) if not frame.empty and "risk_flags" in frame.columns else [],
        "research_only": True,
        "auto_trading_approved": False,
        "broker_integration_enabled": False,
        "llm_decision_allowed": False,
        "writes_real_trades": False,
        "release_profile_replacement": False,
    }
    (out_dir / "deployment_repair_best_candidate.yml").write_text(
        yaml.safe_dump(summary["best_candidate"] or {"status": "NO_DEPLOYMENT_REPAIR_CANDIDATE", "closest_to_pass_variant": summary["closest_to_pass_variant"]}, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    _write_report(out_dir / "deployment_repair_report.md", frame, summary)
    _write_observation(out_dir / "deployment_repair_observation_candidate.md", summary, robustness)
    _write_comparison(out_dir / "deployment_repair_comparison_vs_repair_best.md", summary["closest_to_pass_variant"], _repair_best_metrics())
    (out_dir / "deployment_repair_trace_summary.md").write_text("# deployment repair trace summary\n\n" + build_deployment_trace_diagnostic_report(summary) + "\n", encoding="utf-8")

    quality_rows = [item for row in rows for item in row.get("_quality_rows", [])]
    winner_rows = [item for row in rows for item in row.get("_winner_rows", [])]
    group_rows = [item for row in rows for item in row.get("_group_rows", [])]
    cash_rows = [item for row in rows for item in row.get("_cash_sleeve_rows", [])]
    pd.DataFrame(group_rows or [{"date": "", "variant": "", "symbol": "", "allowed": True, "blocked_reason": ""}]).to_csv(out_dir / "deployment_repair_group_concentration_report.csv", index=False)
    pd.DataFrame(_compact_quality_rows(quality_rows) or [{"date": "", "variant": "", "symbol": "", "eligible": False, "fill_score": 0.0, "future_return_used": False}]).to_csv(out_dir / "deployment_repair_quality_fill_report.csv", index=False)
    pd.DataFrame(_compact_winner_rows(winner_rows) or [{"date": "", "variant": "", "symbol": "", "eligible": False, "future_return_used": False}]).to_csv(out_dir / "deployment_repair_winner_add_report.csv", index=False)
    _write_cash_feasibility(out_dir / "deployment_repair_cash_sleeve_feasibility.md", cash_rows, summary["cash_sleeve_data_available"])
    warnings = {
        "research_only": True,
        "release_profile_replacement": False,
        "variant_count": summary["variant_count"],
        "hard_condition_pass_count": summary["hard_condition_pass_count"],
        "risk_flags": summary["overtrading_flags"],
        "notes": [
            "hard conditions are unchanged",
            "cyclical bucket remains watch-only",
            "cash sleeve is separated from stock sleeve attribution",
        ],
    }
    (out_dir / "deployment_repair_warnings.json").write_text(json.dumps(warnings, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    (out_dir / "deployment_repair_effective_config.yml").write_text(yaml.safe_dump(effective_config or {}, allow_unicode=True, sort_keys=False), encoding="utf-8")
    _write_trace_outputs(rows, frame, summary, out_dir)
    missing = [name for name in REQUIRED_OUTPUTS if not (out_dir / name).exists()]
    trace_missing = [name for name in TRACE_OUTPUTS if not (out_dir / "traces" / name).exists()]
    if missing or trace_missing:
        raise RuntimeError(f"missing deployment repair outputs: {missing}; trace_missing={trace_missing}")
    return summary


def run_experiments(max_variants: int | None = None) -> dict[str, Any]:
    config = load_yaml(CONFIG_PATH)
    base_config = load_yaml(BASE_CORE_CONFIG_PATH)
    configs = load_audit_configs()
    features = load_feature_window(DEFAULT_START_DATE, DEFAULT_END_DATE)
    benchmark = load_benchmark_window(DEFAULT_START_DATE, DEFAULT_END_DATE)
    feature_by_date, approximate = _prepare_feature_by_date(features, configs)
    config = copy.deepcopy(config)
    config["base_50k_core_effective_config"] = base_config
    config["approximate_backtest"] = bool(approximate)
    config["experiment_design"] = "phase4_layered_trace_driven_max_24"
    instruments = (((config.get("deployment_repair") or {}).get("cash_sleeve_research") or {}).get("candidate_instruments")) or []
    cash_sleeve_market_data = _load_cash_sleeve_market_data(feature_by_date, [str(item) for item in instruments])
    reason_counts = _trace_reason_counts((config.get("deployment_repair") or {}).get("source_diagnostics", {}).get("trace_dir", PHASE3_TRACE_DIR))
    variants = build_deployment_repair_variants(config)
    if max_variants is not None:
        variants = variants[: int(max_variants)]
    config["deployment_repair"]["actual_variants_run"] = len(variants)
    config["deployment_repair"]["cash_sleeve_data_available"] = bool(cash_sleeve_market_data)
    rows = []
    for idx, variant in enumerate(variants, start=1):
        print(f"[deployment_repair] {idx:02d}/{len(variants):02d} {variant.name}", flush=True)
        rows.append(
            run_deployment_repair_backtest(
                variant,
                feature_by_date=feature_by_date,
                benchmark=benchmark,
                configs=configs,
                deployment_config=config,
                cash_sleeve_market_data=cash_sleeve_market_data,
                trace_reason_counts=reason_counts,
            )
        )
    return write_deployment_repair_outputs(rows, config)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run phase4 research-only 50k core deployment repair experiments.")
    parser.add_argument("--max-variants", type=int, default=None)
    args = parser.parse_args()
    summary = run_experiments(max_variants=args.max_variants)
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
