#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import itertools
import json
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.audit_common import (
    DEFAULT_END_DATE,
    DEFAULT_START_DATE,
    V2_HISTORY_DIR,
    load_audit_configs,
    load_benchmark_window,
    load_feature_window,
)
from scripts.report_metadata import config_hash, data_hash, git_branch, git_commit, now_utc_iso, stable_hash
from src.strategy.backtest_engine import BacktestEngine, Position
from src.strategy.regime import determine_market_regime
from src.strategy.signals import SignalEngine
from src.utils.config import load_yaml, resolve_path


CONFIG_PATH = "config/strategy_v2_50k_compact.yml"
OUT_DIR = "reports/backtest/50k_compact"
OUT_CSV = f"{OUT_DIR}/compact_experiment_metrics.csv"
OUT_MD = f"{OUT_DIR}/compact_experiment_report.md"
OUT_JSON = f"{OUT_DIR}/compact_experiment_summary.json"
ROBUSTNESS_CSV = f"{OUT_DIR}/compact_neighborhood_robustness.csv"
ROBUSTNESS_MD = f"{OUT_DIR}/compact_neighborhood_robustness.md"
ROBUSTNESS_JSON = f"{OUT_DIR}/compact_neighborhood_robustness.json"
OBSERVATION_CANDIDATE_MD = f"{OUT_DIR}/compact_observation_candidate.md"
OBSERVATION_CANDIDATE_JSON = f"{OUT_DIR}/compact_observation_candidate.json"
OBSERVATION_CANDIDATE_VARIANT = "mp6_tr1_tu8_cr15_add0"
ROBUSTNESS_STATUSES = {"ROBUST", "FRAGILE", "INCONCLUSIVE"}
BUY_ACTIONS = {"BUY_1", "BUY_2", "BUY_3"}
SELL_ACTIONS = {"REDUCE", "SELL_ALL"}
WATCH_REASON_ACCOUNT_INFEASIBLE = "WATCH_ONLY_ACCOUNT_INFEASIBLE"
WATCH_REASON_PORTFOLIO_FULL = "WATCH_ONLY_PORTFOLIO_FULL"
WATCH_REASON_CASH_RESERVED = "WATCH_ONLY_CASH_RESERVED"
WATCH_REASON_LOT_TOO_EXPENSIVE = "WATCH_ONLY_LOT_TOO_EXPENSIVE"
WATCH_REASON_DAILY_NEW_LIMIT = "WATCH_ONLY_DAILY_NEW_LIMIT"
WATCH_REASON_DAILY_ADD_LIMIT = "WATCH_ONLY_DAILY_ADD_LIMIT"
WATCH_REASON_RANK_OUT = "WATCH_ONLY_COMPACT_RANK_OUT"
WATCH_REASON_MAX_TRANCHES = "WATCH_ONLY_MAX_TRANCHES"
WATCH_REASON_INDUSTRY_CONCENTRATION = "WATCH_ONLY_INDUSTRY_CONCENTRATION"


@dataclass(frozen=True)
class CompactParams:
    max_positions: int
    max_tranches: int
    target_universe_size: int
    cash_reserve_ratio: float
    max_new_positions_per_day: int = 1
    max_adds_per_day: int = 1
    capital: float = 50_000.0
    round_lot: int = 100
    min_trade_value: float = 0.0
    commission_rate: float = 0.0003
    stamp_duty_rate_sell: float = 0.0005
    slippage_bps: float = 5.0
    industry_max_positions: int = 2

    @property
    def variant_id(self) -> str:
        reserve = int(round(self.cash_reserve_ratio * 100))
        return (
            f"mp{self.max_positions}_tr{self.max_tranches}_tu{self.target_universe_size}"
            f"_cr{reserve}_add{self.max_adds_per_day}"
        )


@dataclass(frozen=True)
class GateResult:
    actionable: bool
    reason_code: str = ""
    target_weight: float = 0.0
    target_order_value: float = 0.0
    lot_notional: float = 0.0
    action_type: str = "NEW_BUY"


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        if value is None or pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: object, default: int = 0) -> int:
    return int(_safe_float(value, float(default)))


def _ratio_or_none(numerator: int | float, denominator: int | float) -> float | None:
    denominator = float(denominator)
    if denominator == 0:
        return None
    return float(numerator) / denominator


def _target_weight(params: CompactParams, target_tranches: int) -> float:
    final_weight = max(0.0, (1.0 - params.cash_reserve_ratio) / max(params.max_positions, 1))
    tranche = min(max(1, int(target_tranches)), params.max_tranches)
    return round(final_weight * tranche / max(params.max_tranches, 1), 6)


def compact_account_gate(
    decision: dict[str, Any],
    params: CompactParams,
    *,
    nav: float,
    cash: float,
    positions_count: int,
    industry_position_count: int = 0,
    new_buys_today: int = 0,
    adds_today: int = 0,
) -> GateResult:
    current_tranches = _safe_int(decision.get("current_position_tranches"))
    current_shares = _safe_int(decision.get("current_shares"))
    target_tranches = min(_safe_int(decision.get("desired_target_tranches", decision.get("target_position_tranches", 1)), 1), params.max_tranches)
    raw_target_tranches = _safe_int(decision.get("desired_target_tranches", decision.get("target_position_tranches", target_tranches)), target_tranches)
    price = _safe_float(decision.get("close"))
    action_type = "NEW_BUY" if current_tranches <= 0 and current_shares <= 0 else "ADD"
    lot_notional = price * params.round_lot
    target_weight = _target_weight(params, target_tranches)
    current_value = current_shares * price
    target_value = target_weight * nav
    target_order_value = max(0.0, target_value - current_value)
    investable_cash = max(0.0, cash - params.cash_reserve_ratio * nav)

    if raw_target_tranches > params.max_tranches:
        return GateResult(False, WATCH_REASON_MAX_TRANCHES, target_weight, target_order_value, lot_notional, action_type)
    if action_type == "NEW_BUY" and positions_count >= params.max_positions:
        return GateResult(False, WATCH_REASON_PORTFOLIO_FULL, target_weight, target_order_value, lot_notional, action_type)
    if action_type == "NEW_BUY" and new_buys_today >= params.max_new_positions_per_day:
        return GateResult(False, WATCH_REASON_DAILY_NEW_LIMIT, target_weight, target_order_value, lot_notional, action_type)
    if action_type == "ADD" and adds_today >= params.max_adds_per_day:
        return GateResult(False, WATCH_REASON_DAILY_ADD_LIMIT, target_weight, target_order_value, lot_notional, action_type)
    if action_type == "ADD" and params.max_tranches <= 1:
        return GateResult(False, WATCH_REASON_MAX_TRANCHES, target_weight, target_order_value, lot_notional, action_type)
    if action_type == "NEW_BUY" and industry_position_count >= params.industry_max_positions:
        return GateResult(False, WATCH_REASON_INDUSTRY_CONCENTRATION, target_weight, target_order_value, lot_notional, action_type)
    if price <= 0 or lot_notional <= 0:
        return GateResult(False, WATCH_REASON_ACCOUNT_INFEASIBLE, target_weight, target_order_value, lot_notional, action_type)
    if lot_notional > target_order_value + 1e-9:
        return GateResult(False, WATCH_REASON_LOT_TOO_EXPENSIVE, target_weight, target_order_value, lot_notional, action_type)
    if lot_notional * (1.0 + params.commission_rate) > investable_cash + 1e-9:
        return GateResult(False, WATCH_REASON_CASH_RESERVED, target_weight, target_order_value, lot_notional, action_type)
    return GateResult(True, "", target_weight, target_order_value, lot_notional, action_type)


def _stock_quantile(decision: dict[str, Any]) -> float:
    for field in ("stock_valuation_quantile", "stock_q_blended", "stock_pb_q_blended", "stock_pe_ttm_q_blended"):
        if field in decision:
            return _safe_float(decision.get(field), 100.0)
    return 100.0


def _rank_key(decision: dict[str, Any], params: CompactParams) -> tuple:
    close = _safe_float(decision.get("close"))
    lot_notional = close * params.round_lot
    final_score = _safe_float(decision.get("universe_final_score", decision.get("final_score")))
    stock_q = _stock_quantile(decision)
    dividend = _safe_float(decision.get("dv_ttm")) if str(decision.get("bucket")) == "defensive_dividend" else 0.0
    lot_budget = params.capital * (1.0 - params.cash_reserve_ratio) / max(params.max_positions, 1)
    lot_fit = 0 if lot_notional <= lot_budget + 1e-9 else 1
    held_priority = 0 if _safe_int(decision.get("current_position_tranches")) > 0 else 1
    return (held_priority, lot_fit, -final_score, stock_q, -dividend, str(decision.get("industry", "")), str(decision.get("symbol", "")))


def _compact_strategy_cfg(base: dict[str, Any], params: CompactParams) -> dict[str, Any]:
    strategy = copy.deepcopy(base)
    strategy["profile"] = "combined_v2_50k_compact"
    strategy["profile_name"] = "combined_v2_50k_compact"
    strategy["research_only"] = True
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
    final_weight = (1.0 - params.cash_reserve_ratio) / max(params.max_positions, 1)
    tranche_weights = {idx: round(final_weight * idx / max(params.max_tranches, 1), 6) for idx in range(1, params.max_tranches + 1)}
    for bucket_cfg in strategy.get("buckets", {}).values():
        if isinstance(bucket_cfg, dict):
            bucket_cfg["tranche_weights"] = tranche_weights
            bucket_cfg["max_single_name_weight"] = round(final_weight, 6)
    return strategy


def _compact_account_cfg(base: dict[str, Any], params: CompactParams, *, signal_only: bool = False) -> dict[str, Any]:
    account = copy.deepcopy(base)
    account["profile_name"] = "combined_v2_50k_compact"
    account["account_profile"] = "combined_v2_50k_compact"
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
            "round_lot": 1 if signal_only else params.round_lot,
            "commission_rate": params.commission_rate,
            "stamp_duty_rate_sell": params.stamp_duty_rate_sell,
            "slippage_bps": params.slippage_bps,
        }
    )
    account.setdefault("position_sizing", {}).update(
        {
            "max_tranches_per_stock": params.max_tranches,
            "tranche_weights": {idx: _target_weight(params, idx) for idx in range(1, params.max_tranches + 1)},
            "max_single_stock_weight": _target_weight(params, params.max_tranches),
            "min_trade_value": 0 if signal_only else params.min_trade_value,
        }
    )
    return account


def _prepare_feature_by_date(features: pd.DataFrame, configs: dict[str, Any]) -> tuple[dict[str, pd.DataFrame], bool]:
    utility = BacktestEngine(configs["v2_strategy"], configs["v2_universe"], configs["account"], historical_universe_dir=V2_HISTORY_DIR, execution_mode="next_bar")
    prepared = utility._prepare_backtest_features(features.sort_values(["date", "symbol"]).copy())
    prepared, approximate = utility._overlay_historical_universe(prepared)
    return {date: frame.copy() for date, frame in prepared.groupby("date", sort=True)}, approximate


def _positions_frame(positions: dict[str, Position], current_index: int, current_date: str) -> pd.DataFrame:
    return BacktestEngine._positions_frame(positions, current_index=current_index, current_date=current_date)


def _portfolio_value(cash: float, positions: dict[str, Position], price_frame: pd.DataFrame, mark_field: str = "close") -> float:
    value = cash
    for symbol, position in positions.items():
        if symbol in price_frame.index and mark_field in price_frame.columns:
            value += position.shares * _safe_float(price_frame.loc[symbol, mark_field])
    return float(value)


def _round_down_lot(shares: float, lot: int) -> float:
    return float(int(max(0.0, shares)) // max(1, lot) * max(1, lot))


def _fill_price(price_frame: pd.DataFrame, symbol: str, slippage_rate: float, side: str) -> tuple[float, str]:
    raw = _safe_float(price_frame.loc[symbol, "open"] if "open" in price_frame.columns else 0.0)
    field = "open"
    if raw <= 0:
        raw = _safe_float(price_frame.loc[symbol, "close"])
        field = "close"
    return raw * (1.0 + slippage_rate if side == "BUY" else 1.0 - slippage_rate), field


def _watch_record(date: str, decision: dict[str, Any], gate: GateResult) -> dict[str, Any]:
    return {
        "date": date,
        "symbol": decision.get("symbol"),
        "ts_code": decision.get("symbol"),
        "name": decision.get("name"),
        "bucket": decision.get("bucket"),
        "industry": decision.get("industry"),
        "intended_action": decision.get("action_enum"),
        "intended_signal_level": decision.get("signal_level", decision.get("action_enum")),
        "reason_code": gate.reason_code,
        "action_enum": "HOLD",
        "reason_codes": [gate.reason_code],
        "target_weight": 0.0,
        "target_order_value": 0.0,
        "lot_notional": gate.lot_notional,
        "target_action_budget": gate.target_order_value,
        "final_score": decision.get("universe_final_score", decision.get("final_score")),
        "stock_valuation_quantile": _stock_quantile(decision),
    }


def _execute_buy(
    *,
    signal_date: str,
    fill_date: str,
    decision: dict[str, Any],
    gate: GateResult,
    params: CompactParams,
    price_frame: pd.DataFrame,
    positions: dict[str, Position],
    cash: float,
    nav: float,
) -> tuple[float, dict[str, Position], dict[str, Any] | None, dict[str, Any] | None]:
    symbol = str(decision.get("symbol"))
    if symbol not in price_frame.index:
        return cash, positions, None, _watch_record(signal_date, decision, GateResult(False, "MISSING_FILL_PRICE", gate.target_weight, gate.target_order_value, gate.lot_notional, gate.action_type))
    fill_price, field = _fill_price(price_frame, symbol, params.slippage_bps / 10_000.0, "BUY")
    current = positions.get(symbol)
    current_shares = float(current.shares) if current else 0.0
    current_value = current_shares * fill_price
    target_value = gate.target_weight * nav
    delta_shares = _round_down_lot(max(0.0, (target_value - current_value) / max(fill_price, 1e-9)), params.round_lot)
    if delta_shares <= 0:
        return cash, positions, None, _watch_record(signal_date, decision, GateResult(False, WATCH_REASON_LOT_TOO_EXPENSIVE, gate.target_weight, gate.target_order_value, gate.lot_notional, gate.action_type))
    trade_value = delta_shares * fill_price
    fee = trade_value * params.commission_rate
    reserve_cash = params.cash_reserve_ratio * nav
    if trade_value + fee > max(0.0, cash - reserve_cash) + 1e-9:
        return cash, positions, None, _watch_record(signal_date, decision, GateResult(False, WATCH_REASON_CASH_RESERVED, gate.target_weight, gate.target_order_value, gate.lot_notional, gate.action_type))
    cash_before = cash
    cash -= trade_value + fee
    position = current or Position(
        symbol=symbol,
        industry=str(decision.get("industry", "")),
        bucket=str(decision.get("bucket", "")),
        entry_date=fill_date,
        entry_index=0,
        entry_reason=str(decision.get("action_reason", "")),
        last_buy_date=fill_date,
        last_buy_index=0,
    )
    total_cost = position.avg_cost * position.shares + trade_value
    position.shares += delta_shares
    position.avg_cost = total_cost / position.shares if position.shares else 0.0
    position.current_position_tranches = min(_safe_int(decision.get("desired_target_tranches", 1), 1), params.max_tranches)
    position.current_weight = (position.shares * fill_price) / max(nav, 1e-9)
    position.last_fill_price = fill_price
    position.last_buy_date = fill_date
    position.current_shares = int(round(position.shares))
    positions[symbol] = position
    trade = {
        "date": fill_date,
        "signal_date": signal_date,
        "symbol": symbol,
        "ts_code": symbol,
        "name": decision.get("name"),
        "industry": decision.get("industry"),
        "bucket": decision.get("bucket"),
        "side": "BUY",
        "action": decision.get("action_enum"),
        "signal_level": decision.get("signal_level", decision.get("action_enum")),
        "shares": delta_shares,
        "price": fill_price,
        "amount": trade_value,
        "fee": fee,
        "tax": 0.0,
        "cash_before": cash_before,
        "cash_after": cash,
        "target_weight": gate.target_weight,
        "realized_pnl": 0.0,
        "fill_price_field": field,
        "execution_mode": "next_bar",
    }
    return cash, positions, trade, None


def _execute_sell(
    *,
    fill_date: str,
    decision: dict[str, Any],
    params: CompactParams,
    price_frame: pd.DataFrame,
    positions: dict[str, Position],
    cash: float,
    nav: float,
) -> tuple[float, dict[str, Position], dict[str, Any] | None]:
    symbol = str(decision.get("symbol"))
    if symbol not in positions or symbol not in price_frame.index:
        return cash, positions, None
    position = positions[symbol]
    fill_price, field = _fill_price(price_frame, symbol, params.slippage_bps / 10_000.0, "SELL")
    if str(decision.get("action_enum")) == "SELL_ALL":
        shares = _round_down_lot(position.shares, params.round_lot)
        target_tranches = 0
    else:
        target_weight = min(position.current_weight, _target_weight(params, max(0, position.current_position_tranches - 1)))
        target_shares = _round_down_lot((target_weight * nav) / max(fill_price, 1e-9), params.round_lot)
        shares = max(0.0, _round_down_lot(position.shares - target_shares, params.round_lot))
        target_tranches = max(0, position.current_position_tranches - 1)
    if shares <= 0:
        return cash, positions, None
    trade_value = shares * fill_price
    fee = trade_value * params.commission_rate
    tax = trade_value * params.stamp_duty_rate_sell
    cash_before = cash
    cash += trade_value - fee - tax
    realized_pnl = trade_value - position.avg_cost * shares - fee - tax
    position.shares -= shares
    if position.shares <= 1e-9 or target_tranches == 0:
        positions.pop(symbol, None)
    else:
        position.current_position_tranches = target_tranches
        position.current_weight = (position.shares * fill_price) / max(nav, 1e-9)
        position.current_shares = int(round(position.shares))
        positions[symbol] = position
    return cash, positions, {
        "date": fill_date,
        "signal_date": decision.get("date"),
        "symbol": symbol,
        "ts_code": symbol,
        "name": decision.get("name"),
        "industry": decision.get("industry"),
        "bucket": decision.get("bucket"),
        "side": "SELL",
        "action": decision.get("action_enum"),
        "signal_level": decision.get("signal_level", decision.get("action_enum")),
        "shares": shares,
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
    }


def _apply_compact_buy_selection(
    *,
    signal_date: str,
    buy_decisions: list[dict[str, Any]],
    params: CompactParams,
    nav: float,
    cash: float,
    positions: dict[str, Position],
) -> tuple[list[tuple[dict[str, Any], GateResult]], list[dict[str, Any]], int]:
    selected: list[tuple[dict[str, Any], GateResult]] = []
    watch_records: list[dict[str, Any]] = []
    new_buys_today = 0
    adds_today = 0
    industry_counts = Counter(position.industry for position in positions.values())
    ranked = sorted(buy_decisions, key=lambda item: _rank_key(item, params))
    new_seen = 0
    for decision in ranked:
        current_tranches = _safe_int(decision.get("current_position_tranches"))
        current_shares = _safe_int(decision.get("current_shares"))
        action_type = "NEW_BUY" if current_tranches <= 0 and current_shares <= 0 else "ADD"
        if action_type == "NEW_BUY":
            new_seen += 1
            if new_seen > params.target_universe_size:
                gate = GateResult(False, WATCH_REASON_RANK_OUT, _target_weight(params, 1), 0.0, _safe_float(decision.get("close")) * params.round_lot, action_type)
                watch_records.append(_watch_record(signal_date, decision, gate))
                continue
        gate = compact_account_gate(
            decision,
            params,
            nav=nav,
            cash=cash,
            positions_count=len(positions) + new_buys_today,
            industry_position_count=int(industry_counts.get(str(decision.get("industry", "")), 0)),
            new_buys_today=new_buys_today,
            adds_today=adds_today,
        )
        if not gate.actionable:
            watch_records.append(_watch_record(signal_date, decision, gate))
            continue
        selected.append((decision, gate))
        if gate.action_type == "NEW_BUY":
            new_buys_today += 1
            industry_counts[str(decision.get("industry", ""))] += 1
        else:
            adds_today += 1
    return selected, watch_records, len(ranked)


def _metrics(nav_frame: pd.DataFrame, trades: pd.DataFrame, initial_cash: float) -> dict[str, Any]:
    if nav_frame.empty:
        return {"annual_return": 0.0, "cumulative_return": 0.0, "max_drawdown": 0.0}
    nav = nav_frame["nav"].astype(float)
    returns = nav.pct_change().dropna()
    years = max(len(nav_frame) / 252, 1 / 252)
    cumulative = nav.iloc[-1] / initial_cash - 1.0
    annual = (nav.iloc[-1] / initial_cash) ** (1 / years) - 1.0
    drawdown = nav / nav.cummax() - 1.0
    exposure = pd.to_numeric(nav_frame.get("exposure", pd.Series(dtype=float)), errors="coerce")
    holdings = pd.to_numeric(nav_frame.get("holdings_count", pd.Series(dtype=float)), errors="coerce")
    cash_ratio = pd.to_numeric(nav_frame.get("cash", pd.Series(dtype=float)), errors="coerce") / nav
    return {
        "annual_return": float(annual),
        "cumulative_return": float(cumulative),
        "max_drawdown": float(drawdown.min()),
        "sharpe": float(returns.mean() / returns.std(ddof=0) * (252**0.5)) if not returns.empty and returns.std(ddof=0) > 0 else 0.0,
        "total_trades": int(len(trades)),
        "buy_trades": int((trades.get("side", pd.Series(dtype=str)) == "BUY").sum()) if not trades.empty else 0,
        "sell_trades": int((trades.get("side", pd.Series(dtype=str)) == "SELL").sum()) if not trades.empty else 0,
        "average_cash_ratio": float(cash_ratio.mean()) if not cash_ratio.empty else 1.0,
        "avg_daily_exposure": float(exposure.mean()) if not exposure.empty else 0.0,
        "max_exposure": float(exposure.max()) if not exposure.empty else 0.0,
        "average_positions": float(holdings.mean()) if not holdings.empty else 0.0,
        "max_positions_used": int(holdings.max()) if not holdings.empty else 0,
        "turnover": float(trades.get("amount", pd.Series(dtype=float)).abs().sum() / max(initial_cash, 1e-9)) if not trades.empty else 0.0,
        "total_fees": float(trades.get("fee", pd.Series(dtype=float)).sum()) if not trades.empty else 0.0,
        "total_tax": float(trades.get("tax", pd.Series(dtype=float)).sum()) if not trades.empty else 0.0,
        "realized_pnl": float(trades.get("realized_pnl", pd.Series(dtype=float)).sum()) if not trades.empty else 0.0,
    }


def run_compact_backtest(
    params: CompactParams,
    *,
    feature_by_date: dict[str, pd.DataFrame],
    benchmark: pd.DataFrame,
    configs: dict[str, Any],
) -> dict[str, Any]:
    strategy = _compact_strategy_cfg(configs["v2_strategy"], params)
    signal_account = _compact_account_cfg(configs["account"], params, signal_only=True)
    signal_engine = SignalEngine(strategy, configs["v2_universe"], signal_account)
    dates = sorted(feature_by_date)
    cash = params.capital
    positions: dict[str, Position] = {}
    nav_records: list[dict[str, Any]] = []
    trades: list[dict[str, Any]] = []
    watch_records: list[dict[str, Any]] = []
    daily_rows: list[dict[str, Any]] = []
    industry_concentration_values: list[float] = []

    for index in range(len(dates) - 1):
        signal_date = dates[index]
        fill_date = dates[index + 1]
        todays = feature_by_date[signal_date].copy()
        positions_df = _positions_frame(positions, index, signal_date)
        todays = BacktestEngine._apply_positions_to_features(todays, positions_df)
        todays = BacktestEngine._apply_v2_holding_state(todays)
        price_today = todays.set_index("symbol")
        nav = _portfolio_value(cash, positions, price_today)
        decision_scope = todays[todays["in_effective_universe"].astype(bool) | todays["symbol"].astype(str).isin(set(positions.keys()))].copy()
        benchmark_until_today = benchmark[benchmark["date"] <= signal_date]
        regime = determine_market_regime(benchmark_until_today, strategy)
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

        for decision in decisions:
            if decision.get("action_enum") not in SELL_ACTIONS:
                continue
            cash, positions, trade = _execute_sell(
                fill_date=fill_date,
                decision=decision,
                params=params,
                price_frame=next_day,
                positions=positions,
                cash=cash,
                nav=nav,
            )
            if trade:
                trades.append(trade)

        buy_decisions = [item for item in decisions if item.get("action_enum") in BUY_ACTIONS]
        selected, day_watch, strategy_eligible = _apply_compact_buy_selection(
            signal_date=signal_date,
            buy_decisions=buy_decisions,
            params=params,
            nav=nav,
            cash=cash,
            positions=positions,
        )
        watch_records.extend(day_watch)
        account_actionable = len(selected)
        for decision, gate in selected:
            cash, positions, trade, watch = _execute_buy(
                signal_date=signal_date,
                fill_date=fill_date,
                decision=decision,
                gate=gate,
                params=params,
                price_frame=next_day,
                positions=positions,
                cash=cash,
                nav=nav,
            )
            if trade:
                trades.append(trade)
            if watch:
                watch_records.append(watch)

        fill_nav = _portfolio_value(cash, positions, next_day)
        invested = max(0.0, fill_nav - cash)
        industry_counts = Counter(position.industry for position in positions.values())
        industry_concentration = max(industry_counts.values()) / max(len(positions), 1) if positions else 0.0
        industry_concentration_values.append(industry_concentration)
        executed_today = trades[day_trades_before:]
        daily_rows.append(
            {
                "date": signal_date,
                "strategy_eligible_count": strategy_eligible,
                "account_actionable_buy_count": account_actionable,
                "watch_only_count": len(day_watch) + max(0, len(selected) - sum(1 for item in executed_today if item.get("side") == "BUY")),
                "executable_buy_count": sum(1 for item in executed_today if item.get("side") == "BUY"),
                "holdings_count": len(positions),
                "cash": cash,
                "nav": fill_nav,
                "exposure": invested / max(fill_nav, 1e-9),
                "industry_concentration": industry_concentration,
            }
        )
        nav_records.append({"date": fill_date, "nav": fill_nav, "cash": cash, "exposure": invested / max(fill_nav, 1e-9), "holdings_count": len(positions)})

    nav_frame = pd.DataFrame(nav_records)
    trade_frame = pd.DataFrame(trades)
    daily = pd.DataFrame(daily_rows)
    watch = pd.DataFrame(watch_records)
    metrics = _metrics(nav_frame, trade_frame, params.capital)
    strategy_eligible_count = int(daily.get("strategy_eligible_count", pd.Series(dtype=int)).sum()) if not daily.empty else 0
    account_actionable_buy_count = int(daily.get("account_actionable_buy_count", pd.Series(dtype=int)).sum()) if not daily.empty else 0
    watch_only_count = int(daily.get("watch_only_count", pd.Series(dtype=int)).sum()) if not daily.empty else 0
    executable_buy_count = int(metrics.get("buy_trades", 0))
    reason_counts = Counter(watch.get("reason_code", pd.Series(dtype=str)).dropna().astype(str).tolist()) if not watch.empty else Counter()
    payload = {
        "variant": params.variant_id,
        "profile": "combined_v2_50k_compact",
        "research_only": True,
        "capital": params.capital,
        "round_lot": params.round_lot,
        "max_positions": params.max_positions,
        "max_tranches": params.max_tranches,
        "target_universe_size": params.target_universe_size,
        "cash_reserve_ratio": params.cash_reserve_ratio,
        "max_new_positions_per_day": params.max_new_positions_per_day,
        "max_adds_per_day": params.max_adds_per_day,
        **metrics,
        "executable_buy_count": executable_buy_count,
        "strategy_eligible_count": strategy_eligible_count,
        "account_actionable_buy_count": account_actionable_buy_count,
        "watch_only_count": watch_only_count,
        "executable_account_actionable_ratio": _ratio_or_none(executable_buy_count, account_actionable_buy_count),
        "executable_strategy_eligible_ratio": _ratio_or_none(executable_buy_count, strategy_eligible_count),
        "industry_concentration_max": max(industry_concentration_values) if industry_concentration_values else 0.0,
        "top_block_or_watch_reasons": dict(reason_counts.most_common(5)),
        "auto_trading_approved": False,
        "broker_integration_enabled": False,
        "llm_decision_allowed": False,
    }
    return payload


def _params_from_config(config: dict[str, Any]) -> list[CompactParams]:
    grid = config["experiment_grid"]
    capital = float(config["account"]["capital"])
    round_lot = int(config["account"]["round_lot"])
    if max(grid["max_positions"]) > int(config["compact_rules"]["max_positions_upper_bound"]):
        raise ValueError("50k compact max_positions cannot exceed 8")
    params: list[CompactParams] = []
    for max_positions, max_tranches, target_universe_size, cash_reserve_ratio, max_adds_per_day in itertools.product(
        grid["max_positions"],
        grid["max_tranches"],
        grid["target_universe_size"],
        grid["cash_reserve_ratio"],
        grid["max_adds_per_day"],
    ):
        params.append(
            CompactParams(
                max_positions=int(max_positions),
                max_tranches=int(max_tranches),
                target_universe_size=int(target_universe_size),
                cash_reserve_ratio=float(cash_reserve_ratio),
                max_new_positions_per_day=1,
                max_adds_per_day=int(max_adds_per_day),
                capital=capital,
                round_lot=round_lot,
                industry_max_positions=int(config["compact_rules"]["ranking"].get("industry_max_positions", 2)),
            )
        )
    return params


def _passes_hard_conditions(row: dict[str, Any], config: dict[str, Any]) -> bool:
    evaluation = config["evaluation"]
    default_dd = float(evaluation["default_50k_max_drawdown_reference"])
    tolerance = float(evaluation["max_drawdown_not_significantly_worse_than_default_tolerance"])
    ratio = row.get("executable_account_actionable_ratio")
    return (
        float(row["capital"]) == 50_000.0
        and int(row["round_lot"]) == 100
        and int(row["max_positions"]) <= int(evaluation["max_positions_max"])
        and float(row["max_exposure"]) <= float(evaluation["max_exposure_max"]) + 1e-12
        and float(row["max_drawdown"]) >= default_dd - tolerance
        and ratio is not None
        and float(ratio) >= float(evaluation["executable_account_actionable_min"])
    )


def _write_reports(rows: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    out_dir = resolve_path(OUT_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(rows)
    frame["passes_hard_conditions"] = [
        _passes_hard_conditions(row, config) for row in frame.to_dict(orient="records")
    ]
    frame = frame.sort_values(
        ["passes_hard_conditions", "executable_account_actionable_ratio", "annual_return", "max_drawdown"],
        ascending=[False, False, False, False],
        na_position="last",
    )
    frame.to_csv(resolve_path(OUT_CSV), index=False)
    candidates = frame[frame["passes_hard_conditions"]].copy()
    best = candidates.iloc[0].to_dict() if not candidates.empty else {}
    summary = {
        "generated_at": now_utc_iso(),
        "git_commit": git_commit(),
        "branch": git_branch(),
        "status": "HAS_50K_COMPACT_CANDIDATE" if best else "NO_50K_COMPACT_CANDIDATE",
        "profile": "combined_v2_50k_compact",
        "research_only": True,
        "default_release_profile_unchanged": True,
        "release_guard_status_should_remain_warn": True,
        "config_hash": config_hash([CONFIG_PATH]),
        "data_hash": data_hash(),
        "experiment_count": int(len(frame)),
        "hard_condition_pass_count": int(len(candidates)),
        "best_candidate": best,
        "rows_hash": stable_hash(frame.to_dict(orient="records")),
        "auto_trading_approved": False,
        "broker_integration_enabled": False,
        "llm_decision_allowed": False,
    }
    resolve_path(OUT_JSON).write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    _write_md(frame, summary, config)
    return summary


def _pct(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "None"
    return f"{float(value):.2%}"


def _write_md(frame: pd.DataFrame, summary: dict[str, Any], config: dict[str, Any]) -> None:
    lines = [
        "# combined_v2_50k_compact research report",
        "",
        f"- status: {summary['status']}",
        "- profile: combined_v2_50k_compact",
        "- research_only: true",
        "- capital: 50000",
        "- round_lot: 100",
        "- default_release_profile_unchanged: true",
        "- auto_trading_approved: false",
        "- broker_integration_enabled: false",
        "- llm_decision_allowed: false",
        f"- experiment_count: {summary['experiment_count']}",
        f"- hard_condition_pass_count: {summary['hard_condition_pass_count']}",
        "",
        "## conclusion",
        "",
    ]
    if summary["best_candidate"]:
        best = summary["best_candidate"]
        lines.append(
            "- 找到满足硬条件的 50k compact research-only 候选："
            f"{best['variant']}，annual={_pct(best['annual_return'])}，max_dd={_pct(best['max_drawdown'])}，"
            f"exec/actionable={_pct(best['executable_account_actionable_ratio'])}。"
        )
    else:
        lines.append("- 没有找到同时满足 50k compact 硬条件的候选；当前策略族在 50k 下仍不适合实盘化，只能 observation / paper trading。")
    lines.extend(
        [
            "- 通过实验不等于可以自动实盘；任何真实交易都必须人工独立决策。",
            "- 200k research profile 只用于解释资金规模瓶颈，不是可操作方案。",
            "",
            "## top variants",
            "",
            "| rank | variant | max_pos | tranches | target_universe | reserve | max_adds | annual | max_dd | max_exposure | trades | strategy_eligible | actionable | executable | exec/actionable | watch | industry_conc | pass | top reasons |",
            "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|",
        ]
    )
    for idx, row in enumerate(frame.head(20).to_dict(orient="records"), start=1):
        lines.append(
            "| {rank} | {variant} | {mp} | {tr} | {tu} | {reserve} | {adds} | {annual} | {dd} | {exposure} | {trades} | {eligible} | {actionable} | {exec_buy} | {ratio} | {watch} | {industry} | {passed} | {reasons} |".format(
                rank=idx,
                variant=row["variant"],
                mp=int(row["max_positions"]),
                tr=int(row["max_tranches"]),
                tu=int(row["target_universe_size"]),
                reserve=_pct(row["cash_reserve_ratio"]),
                adds=int(row["max_adds_per_day"]),
                annual=_pct(row["annual_return"]),
                dd=_pct(row["max_drawdown"]),
                exposure=_pct(row["max_exposure"]),
                trades=int(row["total_trades"]),
                eligible=int(row["strategy_eligible_count"]),
                actionable=int(row["account_actionable_buy_count"]),
                exec_buy=int(row["executable_buy_count"]),
                ratio=_pct(row["executable_account_actionable_ratio"]),
                watch=int(row["watch_only_count"]),
                industry=_pct(row["industry_concentration_max"]),
                passed=str(bool(row["passes_hard_conditions"])).lower(),
                reasons=str(row["top_block_or_watch_reasons"]),
            )
        )
    lines.extend(
        [
            "",
            "## hard conditions",
            "",
            f"- executable/account_actionable >= {_pct(config['evaluation']['executable_account_actionable_min'])}",
            f"- max_exposure <= {_pct(config['evaluation']['max_exposure_max'])}",
            "- max_positions <= 8",
            "- capital = 50000",
            "- round_lot = 100",
            "- default release profile remains 50k lot-aware WARN",
        ]
    )
    resolve_path(OUT_MD).write_text("\n".join(lines) + "\n", encoding="utf-8")


def _load_compact_metrics(metrics_path: str = OUT_CSV) -> pd.DataFrame:
    path = resolve_path(metrics_path)
    if not path.exists():
        raise FileNotFoundError(f"missing compact experiment metrics: {path}")
    frame = pd.read_csv(path)
    if "variant" not in frame.columns:
        raise ValueError(f"compact metrics missing variant column: {path}")
    return frame


def _best_candidate_record(frame: pd.DataFrame) -> dict[str, Any]:
    rows = frame[frame["variant"].astype(str) == OBSERVATION_CANDIDATE_VARIANT]
    if rows.empty:
        raise ValueError(f"best candidate variant not found: {OBSERVATION_CANDIDATE_VARIANT}")
    return rows.iloc[0].to_dict()


def _select_neighborhood_rows(frame: pd.DataFrame) -> pd.DataFrame:
    base = frame.copy()
    neighborhood = (
        base["max_positions"].isin([5, 6])
        & (base["max_tranches"] == 1)
        & base["target_universe_size"].isin([8, 10])
        & base["cash_reserve_ratio"].round(4).isin([0.15, 0.20])
        & (base["max_adds_per_day"] == 0)
    )
    negative_tranches = (
        base["max_positions"].isin([5, 6])
        & (base["max_tranches"] == 2)
        & base["target_universe_size"].isin([8, 10])
        & base["cash_reserve_ratio"].round(4).isin([0.15, 0.20])
        & (base["max_adds_per_day"] == 0)
    )
    negative_adds = (
        base["max_positions"].isin([5, 6])
        & (base["max_tranches"] == 1)
        & base["target_universe_size"].isin([8, 10])
        & base["cash_reserve_ratio"].round(4).isin([0.15, 0.20])
        & (base["max_adds_per_day"] == 1)
    )
    negative_positions = (
        (base["max_positions"] == 8)
        & (base["max_tranches"] == 1)
        & base["target_universe_size"].isin([8, 10])
        & base["cash_reserve_ratio"].round(4).isin([0.15, 0.20])
        & (base["max_adds_per_day"] == 0)
    )
    selected = base[neighborhood | negative_tranches | negative_adds | negative_positions].copy()
    selected["comparison_group"] = "neighborhood"
    selected.loc[negative_tranches.loc[selected.index], "comparison_group"] = "negative_max_tranches_2"
    selected.loc[negative_adds.loc[selected.index], "comparison_group"] = "negative_max_adds_1"
    selected.loc[negative_positions.loc[selected.index], "comparison_group"] = "negative_max_positions_8"
    return selected


def _passes_neighborhood_rule(row: dict[str, Any], best: dict[str, Any]) -> bool:
    annual_floor = float(best["annual_return"]) * 0.70
    max_drawdown_floor = float(best["max_drawdown"]) - 0.02
    ratio = row.get("executable_account_actionable_ratio")
    return (
        float(row["annual_return"]) >= annual_floor
        and float(row["max_drawdown"]) >= max_drawdown_floor
        and float(row["max_exposure"]) <= 0.85 + 1e-12
        and ratio is not None
        and not pd.isna(ratio)
        and float(ratio) >= 0.80
        and int(row["total_trades"]) >= 10
    )


def _build_neighborhood_frame(frame: pd.DataFrame, best: dict[str, Any]) -> pd.DataFrame:
    selected = _select_neighborhood_rows(frame)
    rows: list[dict[str, Any]] = []
    keep_columns = [
        "variant",
        "comparison_group",
        "capital",
        "max_positions",
        "max_tranches",
        "target_universe_size",
        "cash_reserve_ratio",
        "max_adds_per_day",
        "annual_return",
        "cumulative_return",
        "max_drawdown",
        "max_exposure",
        "total_trades",
        "executable_buy_count",
        "strategy_eligible_count",
        "account_actionable_buy_count",
        "watch_only_count",
        "executable_account_actionable_ratio",
        "executable_strategy_eligible_ratio",
        "industry_concentration_max",
        "top_block_or_watch_reasons",
    ]
    for row in selected.to_dict(orient="records"):
        payload = {key: row.get(key) for key in keep_columns}
        payload.update(
            {
                "is_best_candidate": row.get("variant") == OBSERVATION_CANDIDATE_VARIANT,
                "annual_return_delta": float(row["annual_return"]) - float(best["annual_return"]),
                "cumulative_return_delta": float(row["cumulative_return"]) - float(best["cumulative_return"]),
                "max_drawdown_delta": float(row["max_drawdown"]) - float(best["max_drawdown"]),
                "max_exposure_delta": float(row["max_exposure"]) - float(best["max_exposure"]),
                "total_trades_delta": int(row["total_trades"]) - int(best["total_trades"]),
                "watch_only_count_delta": int(row["watch_only_count"]) - int(best["watch_only_count"]),
                "passes_neighborhood_rule": _passes_neighborhood_rule(row, best),
            }
        )
        rows.append(payload)
    result = pd.DataFrame(rows)
    if result.empty:
        return result
    return result.sort_values(
        ["comparison_group", "passes_neighborhood_rule", "annual_return", "max_drawdown", "variant"],
        ascending=[True, False, False, False, True],
    ).reset_index(drop=True)


def _robustness_status(neighborhood: pd.DataFrame, best: dict[str, Any]) -> tuple[str, int, int]:
    if neighborhood.empty:
        return "INCONCLUSIVE", 0, 0
    core = neighborhood[neighborhood["comparison_group"] == "neighborhood"].copy()
    if len(core) < 3:
        return "INCONCLUSIVE", int(core.get("passes_neighborhood_rule", pd.Series(dtype=bool)).sum()), int(len(core))
    support = core[(core["variant"] != OBSERVATION_CANDIDATE_VARIANT) & core["passes_neighborhood_rule"].astype(bool)]
    support_count = int(len(support))
    if support_count >= 3:
        return "ROBUST", support_count, int(len(core))
    return "FRAGILE", support_count, int(len(core))


def _monitoring_metrics() -> list[str]:
    return [
        "generated_signal_count",
        "account_actionable_buy_count",
        "watch_only_count",
        "executable_buy_count",
        "top_watch_only_reasons",
        "current_positions_count",
        "current_exposure",
        "current_cash_ratio",
        "industry_concentration",
        "skipped_signal_reason",
        "actual_paper_fill_price",
        "paper_slippage_vs_next_open",
        "paper_slippage_vs_close",
        "manual_override_flag",
        "manual_override_reason",
    ]


def build_observation_candidate_reports(metrics_path: str = OUT_CSV) -> dict[str, Any]:
    frame = _load_compact_metrics(metrics_path)
    best = _best_candidate_record(frame)
    if int(best["max_positions"]) > 8:
        raise ValueError("compact observation candidate cannot use max_positions > 8")
    if float(best["capital"]) != 50_000.0:
        raise ValueError("compact observation candidate must use 50k capital")
    neighborhood = _build_neighborhood_frame(frame, best)
    status, support_count, neighborhood_count = _robustness_status(neighborhood, best)
    if status not in ROBUSTNESS_STATUSES:
        raise ValueError(f"invalid robustness status: {status}")

    out_dir = resolve_path(OUT_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    neighborhood.to_csv(resolve_path(ROBUSTNESS_CSV), index=False)
    summary = {
        "generated_at": now_utc_iso(),
        "status": status,
        "best_candidate": {key: _json_value(value) for key, value in best.items()},
        "supporting_neighborhood_count_excluding_best": support_count,
        "neighborhood_candidate_count": neighborhood_count,
        "criteria": {
            "annual_return_min_ratio_to_best": 0.70,
            "max_drawdown_not_worse_than_best_by": 0.02,
            "max_exposure_max": 0.85,
            "executable_account_actionable_ratio_min": 0.80,
            "total_trades_min": 10,
            "robust_support_count_min_excluding_best": 3,
        },
        "research_only": True,
        "default_release_profile_unchanged": True,
        "auto_trading_approved": False,
        "broker_integration_enabled": False,
        "llm_decision_allowed": False,
    }
    resolve_path(ROBUSTNESS_JSON).write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    _write_robustness_md(neighborhood, summary)

    candidate = {
        "generated_at": now_utc_iso(),
        "variant": OBSERVATION_CANDIDATE_VARIANT,
        "profile": "combined_v2_50k_compact",
        "research_only": True,
        "frozen_for": "paper_trading_observation_only",
        "selected_metrics": {
            "capital": float(best["capital"]),
            "max_positions": int(best["max_positions"]),
            "max_tranches": int(best["max_tranches"]),
            "target_universe_size": int(best["target_universe_size"]),
            "cash_reserve_ratio": float(best["cash_reserve_ratio"]),
            "max_adds_per_day": int(best["max_adds_per_day"]),
            "annual_return": float(best["annual_return"]),
            "cumulative_return": float(best["cumulative_return"]),
            "max_drawdown": float(best["max_drawdown"]),
            "max_exposure": float(best["max_exposure"]),
            "total_trades": int(best["total_trades"]),
            "executable_buy_count": int(best["executable_buy_count"]),
            "strategy_eligible_count": int(best["strategy_eligible_count"]),
            "account_actionable_buy_count": int(best["account_actionable_buy_count"]),
            "watch_only_count": int(best["watch_only_count"]),
            "executable_account_actionable_ratio": float(best["executable_account_actionable_ratio"]),
        },
        "selection_reasons": [
            "适配 50k 资金规模",
            "不超过 6 个持仓",
            "单档建仓",
            "15% 现金预留",
            "不加仓，避免小账户现金被切碎",
            "最大暴露低于 85%",
            "account actionable buy 基本可执行",
        ],
        "risks": [
            "样本交易少",
            "watch-only 很高",
            "最大回撤比默认 50k combined_v2 更深",
            "可能存在行业集中",
            "回测成交假设仍需纸面观察验证",
        ],
        "observation_conclusion": [
            "只能进入 paper trading / observation",
            "不得自动实盘",
            "不得替换 release 默认口径",
            "不得视为 PASS",
        ],
        "daily_monitoring_metrics": _monitoring_metrics(),
        "default_release_profile_replacement": False,
        "auto_trading_approved": False,
        "broker_integration_enabled": False,
        "llm_decision_allowed": False,
    }
    resolve_path(OBSERVATION_CANDIDATE_JSON).write_text(json.dumps(candidate, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    _write_observation_candidate_md(candidate, status)
    return {"robustness": summary, "candidate": candidate}


def _json_value(value: Any) -> Any:
    if pd.isna(value) if not isinstance(value, (dict, list, tuple)) else False:
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def _write_robustness_md(neighborhood: pd.DataFrame, summary: dict[str, Any]) -> None:
    best = summary["best_candidate"]
    lines = [
        "# 50k compact neighborhood robustness",
        "",
        f"- status: {summary['status']}",
        "- research_only: true",
        "- default_release_profile_unchanged: true",
        "- auto_trading_approved: false",
        "- broker_integration_enabled: false",
        "- llm_decision_allowed: false",
        "",
        "## best_candidate",
        "",
        f"- variant: {best['variant']}",
        f"- annual_return: {_pct(best['annual_return'])}",
        f"- cumulative_return: {_pct(best['cumulative_return'])}",
        f"- max_drawdown: {_pct(best['max_drawdown'])}",
        f"- max_exposure: {_pct(best['max_exposure'])}",
        f"- total_trades: {int(best['total_trades'])}",
        f"- executable_buy_count: {int(best['executable_buy_count'])}",
        f"- strategy_eligible_count: {int(best['strategy_eligible_count'])}",
        f"- account_actionable_buy_count: {int(best['account_actionable_buy_count'])}",
        f"- watch_only_count: {int(best['watch_only_count'])}",
        f"- executable_account_actionable_ratio: {_pct(best['executable_account_actionable_ratio'])}",
        "",
        "## robustness_judgement",
        "",
        f"- judgement: {summary['status']}",
        f"- supporting_neighborhood_count_excluding_best: {summary['supporting_neighborhood_count_excluding_best']}",
        f"- neighborhood_candidate_count: {summary['neighborhood_candidate_count']}",
        "- rule: at least 3 neighboring variants excluding the best must satisfy return, drawdown, exposure, execution and trade-count thresholds.",
        "",
        "## neighborhood and controls",
        "",
        "| group | variant | annual | annual_delta | cumulative_delta | max_dd | max_dd_delta | max_exposure | exposure_delta | trades | trades_delta | watch | watch_delta | exec/actionable | pass |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in neighborhood.to_dict(orient="records"):
        lines.append(
            "| {group} | {variant} | {annual} | {annual_delta} | {cum_delta} | {dd} | {dd_delta} | {exposure} | {exposure_delta} | {trades} | {trades_delta} | {watch} | {watch_delta} | {ratio} | {passed} |".format(
                group=row["comparison_group"],
                variant=row["variant"],
                annual=_pct(row["annual_return"]),
                annual_delta=_pct(row["annual_return_delta"]),
                cum_delta=_pct(row["cumulative_return_delta"]),
                dd=_pct(row["max_drawdown"]),
                dd_delta=_pct(row["max_drawdown_delta"]),
                exposure=_pct(row["max_exposure"]),
                exposure_delta=_pct(row["max_exposure_delta"]),
                trades=int(row["total_trades"]),
                trades_delta=int(row["total_trades_delta"]),
                watch=int(row["watch_only_count"]),
                watch_delta=int(row["watch_only_count_delta"]),
                ratio=_pct(row["executable_account_actionable_ratio"]),
                passed=str(bool(row["passes_neighborhood_rule"])).lower(),
            )
        )
    lines.extend(
        [
            "",
            "## note",
            "",
            "- This report reads existing compact_experiment_metrics.csv only.",
            "- It does not run a new search, expand the parameter space, change release guard, or change the default release profile.",
        ]
    )
    resolve_path(ROBUSTNESS_MD).write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_observation_candidate_md(candidate: dict[str, Any], robustness_status: str) -> None:
    metrics = candidate["selected_metrics"]
    lines = [
        "# 50k compact observation candidate",
        "",
        f"- candidate_variant: {candidate['variant']}",
        "- profile: combined_v2_50k_compact",
        "- research_only: true",
        "- frozen_for: paper_trading_observation_only",
        f"- neighborhood_robustness: {robustness_status}",
        "- auto_trading_approved: false",
        "- broker_integration_enabled: false",
        "- llm_decision_allowed: false",
        "",
        "## selected metrics",
        "",
        f"- capital: {metrics['capital']:.0f}",
        f"- max_positions: {metrics['max_positions']}",
        f"- max_tranches: {metrics['max_tranches']}",
        f"- target_universe_size: {metrics['target_universe_size']}",
        f"- cash_reserve_ratio: {_pct(metrics['cash_reserve_ratio'])}",
        f"- max_adds_per_day: {metrics['max_adds_per_day']}",
        f"- annual_return: {_pct(metrics['annual_return'])}",
        f"- cumulative_return: {_pct(metrics['cumulative_return'])}",
        f"- max_drawdown: {_pct(metrics['max_drawdown'])}",
        f"- max_exposure: {_pct(metrics['max_exposure'])}",
        f"- total_trades: {metrics['total_trades']}",
        f"- executable_buy_count: {metrics['executable_buy_count']}",
        f"- strategy_eligible_count: {metrics['strategy_eligible_count']}",
        f"- account_actionable_buy_count: {metrics['account_actionable_buy_count']}",
        f"- watch_only_count: {metrics['watch_only_count']}",
        f"- executable_account_actionable_ratio: {_pct(metrics['executable_account_actionable_ratio'])}",
        "",
        "## why selected",
        "",
    ]
    lines.extend(f"- {item}" for item in candidate["selection_reasons"])
    lines.extend(["", "## risks", ""])
    lines.extend(f"- {item}" for item in candidate["risks"])
    lines.extend(["", "## observation conclusion", ""])
    lines.extend(f"- {item}" for item in candidate["observation_conclusion"])
    lines.extend(["", "## daily monitoring metrics", ""])
    lines.extend(f"- `{item}`" for item in candidate["daily_monitoring_metrics"])
    resolve_path(OBSERVATION_CANDIDATE_MD).write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_experiments() -> dict[str, Any]:
    config = load_yaml(CONFIG_PATH)
    configs = load_audit_configs()
    features = load_feature_window(DEFAULT_START_DATE, DEFAULT_END_DATE)
    benchmark = load_benchmark_window(DEFAULT_START_DATE, DEFAULT_END_DATE)
    feature_by_date, _approximate = _prepare_feature_by_date(features, configs)
    rows: list[dict[str, Any]] = []
    for idx, params in enumerate(_params_from_config(config), start=1):
        print(f"[50k_compact] {idx:03d} {params.variant_id}", flush=True)
        rows.append(run_compact_backtest(params, feature_by_date=feature_by_date, benchmark=benchmark, configs=configs))
    return _write_reports(rows, config)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run research-only combined_v2_50k_compact experiment matrix.")
    parser.add_argument(
        "--build-observation-candidate",
        action="store_true",
        help="Build observation candidate reports from existing compact metrics without rerunning the matrix.",
    )
    parser.add_argument("--metrics-path", default=OUT_CSV)
    args = parser.parse_args()
    if args.build_observation_candidate:
        build_observation_candidate_reports(args.metrics_path)
        return 0
    run_experiments()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
