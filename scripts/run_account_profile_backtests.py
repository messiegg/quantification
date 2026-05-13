#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
import shutil
import sys
from math import ceil
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.audit_common import (
    DEFAULT_BENCHMARK_FILE,
    DEFAULT_END_DATE,
    DEFAULT_FEATURES_FILE,
    DEFAULT_START_DATE,
    V2_HISTORY_DIR,
    load_audit_configs,
    load_benchmark_window,
    load_feature_window,
    prepare_v2_history,
    run_profile,
)
from scripts.build_account_constraints_report import build_account_constraints_report
from scripts.build_account_suitability_report import build_account_suitability_report
from scripts.report_metadata import config_hash, data_hash, runtime_profile_metadata, stable_hash
from src.strategy.backtest_reports import build_universe_funnel, write_diagnostic_outputs
from src.utils.config import load_yaml, resolve_path


OUT_ROOT = "reports/backtest/account_profiles"
PROFILE_ORDER = ["reference_200k_current", "actual_50k_unmodified", "actual_50k_retail", "actual_50k_lot_aware"]


def _deepcopy_yaml(path: str) -> dict[str, Any]:
    return copy.deepcopy(load_yaml(path))


def _apply_strategy_execution(strategy: dict[str, Any], values: dict[str, Any]) -> dict[str, Any]:
    updated = copy.deepcopy(strategy)
    execution = updated.setdefault("execution", {})
    lot_flags = {"lot_aware_sizing", "pending_add_state", "duplicate_blocked_signal_suppression"}
    for key in (
        "max_positions",
        "equal_weight_target_universe_size",
        "max_new_positions_per_day",
        "max_adds_per_day",
        "lot_aware_sizing",
        "pending_add_state",
        "duplicate_blocked_signal_suppression",
    ):
        if key in values:
            execution[key] = values[key]
        elif key in lot_flags:
            execution[key] = False
    return updated


def _profile_configs(configs: dict[str, Any]) -> dict[str, dict[str, Any]]:
    base_strategy = configs["v2_strategy"]
    reference_account = _deepcopy_yaml("config/account_profiles/reference_200k.yml")
    retail_account = _deepcopy_yaml("config/account_profiles/retail_50k.yml")
    lot_aware_account = _deepcopy_yaml("config/account_profiles/retail_50k_lot_aware.yml")
    reference_execution = _deepcopy_yaml("config/strategy_profiles/reference_200k_execution.yml").get("execution", {})
    retail_execution = _deepcopy_yaml("config/strategy_profiles/retail_50k_execution.yml").get("execution", {})
    lot_aware_execution = _deepcopy_yaml("config/strategy_profiles/retail_50k_lot_aware_execution.yml").get("execution", {})

    unmodified_account = copy.deepcopy(retail_account)
    unmodified_account["profile_name"] = "actual_50k_unmodified"
    unmodified_account["research_only"] = True
    unmodified_account.setdefault("position_sizing", {})["min_trade_value"] = 5000

    profiles = {
        "reference_200k_current": {
            "account": reference_account,
            "strategy": _apply_strategy_execution(base_strategy, reference_execution),
            "account_profile_path": "config/account_profiles/reference_200k.yml",
            "strategy_profile_path": "config/strategy_profiles/reference_200k_execution.yml",
            "research_only": True,
        },
        "actual_50k_unmodified": {
            "account": unmodified_account,
            "strategy": _apply_strategy_execution(
                base_strategy,
                {
                    "max_positions": 20,
                    "equal_weight_target_universe_size": 36,
                    "max_new_positions_per_day": 3,
                    "max_adds_per_day": 5,
                },
            ),
            "account_profile_path": "in_memory_actual_50k_unmodified",
            "strategy_profile_path": "in_memory_actual_50k_unmodified",
            "research_only": True,
        },
        "actual_50k_retail": {
            "account": retail_account,
            "strategy": _apply_strategy_execution(base_strategy, retail_execution),
            "account_profile_path": "config/account_profiles/retail_50k.yml",
            "strategy_profile_path": "config/strategy_profiles/retail_50k_execution.yml",
            "research_only": False,
        },
        "actual_50k_lot_aware": {
            "account": lot_aware_account,
            "strategy": _apply_strategy_execution(base_strategy, lot_aware_execution),
            "account_profile_path": "config/account_profiles/retail_50k_lot_aware.yml",
            "strategy_profile_path": "config/strategy_profiles/retail_50k_lot_aware_execution.yml",
            "research_only": True,
            "candidate_default": True,
        },
    }
    for profile_id, profile in profiles.items():
        if profile_id == "actual_50k_retail":
            account_profile = "retail_50k"
        elif profile_id == "actual_50k_lot_aware":
            account_profile = "retail_50k_lot_aware"
        else:
            account_profile = profile_id
        profile["account"]["account_profile"] = account_profile
        profile["account"]["research_only"] = bool(profile["research_only"])
        profile["strategy"]["research_only"] = bool(profile["research_only"])
    return profiles


def _write_effective_configs(out_dir: Path, account: dict[str, Any], strategy: dict[str, Any]) -> tuple[Path, Path]:
    account_path = out_dir / "account_config_effective.yml"
    strategy_path = out_dir / "strategy_config_effective.yml"
    account_path.write_text(yaml.safe_dump(account, allow_unicode=True, sort_keys=False), encoding="utf-8")
    strategy_path.write_text(yaml.safe_dump(strategy, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return account_path, strategy_path


def _sum_column(frame: pd.DataFrame, column: str) -> int:
    if frame.empty or column not in frame.columns:
        return 0
    return int(pd.to_numeric(frame[column], errors="coerce").fillna(0).sum())


def _ratio(numerator: float, denominator: float) -> float | None:
    return float(numerator) / float(denominator) if denominator else None


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _profile_status(
    *,
    profile_id: str,
    metrics: dict[str, Any],
    account_report: dict[str, Any],
    account: dict[str, Any],
    strategy: dict[str, Any],
    years: float,
) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
    warnings: list[dict[str, Any]] = []
    violations: list[dict[str, Any]] = []
    raw_buy = int(account_report.get("raw_buy_signal_count", 0) or 0)
    ratio = account_report.get("executable_raw_buy_ratio")
    min_trade_ratio = _ratio(float(account_report.get("min_trade_amount_block_count", 0) or 0), raw_buy)
    max_positions_cfg = int(strategy.get("execution", {}).get("max_positions", 0) or 0)
    avg_positions = float(metrics.get("avg_positions", 0.0) or 0.0)
    max_positions_seen = int(metrics.get("max_positions", 0) or 0)
    max_single = float(account.get("position_sizing", {}).get("max_single_stock_weight", 1.0) or 1.0)
    cost_total = float(metrics.get("total_fees", 0.0) or 0.0) + float(metrics.get("total_tax", 0.0) or 0.0) + float(metrics.get("total_slippage", 0.0) or 0.0)
    initial = float(account.get("account", {}).get("initial_capital", 0.0) or 0.0)
    annual_cost_drag = (cost_total / initial / years) if initial and years else None
    buy_trades = int(metrics.get("buy_trades", 0) or 0)
    if ratio is None or float(ratio) < 0.25:
        warnings.append({"code": "ACCOUNT_CONSTRAINTS_DOMINATE_EXECUTION", "actual": ratio, "expected": ">=0.25"})
    if min_trade_ratio is not None and min_trade_ratio > 0.40:
        warnings.append({"code": "MIN_TRADE_AMOUNT_BLOCK_RATIO_HIGH", "actual": min_trade_ratio, "expected": "<=0.40"})
    if profile_id in {"actual_50k_retail", "actual_50k_lot_aware"} and avg_positions > max_positions_cfg + 1e-9:
        violations.append({"code": "AVERAGE_POSITIONS_EXCEED_LIMIT", "actual": avg_positions, "expected": max_positions_cfg})
    if profile_id in {"actual_50k_retail", "actual_50k_lot_aware"} and max_positions_seen > max_positions_cfg:
        violations.append({"code": "MAX_POSITIONS_EXCEED_LIMIT", "actual": max_positions_seen, "expected": max_positions_cfg})
    if float(metrics.get("max_weight_after", 0.0) or 0.0) > max_single + 1e-6:
        violations.append({"code": "SINGLE_NAME_WEIGHT_EXCEEDS_LIMIT", "actual": metrics.get("max_weight_after"), "expected": max_single})
    if annual_cost_drag is None or annual_cost_drag > 0.03:
        warnings.append({"code": "TRANSACTION_COST_DRAG_HIGH_OR_UNKNOWN", "actual": annual_cost_drag, "expected": "<=0.03 annualized"})
    if profile_id in {"actual_50k_retail", "actual_50k_lot_aware"} and buy_trades < 10:
        warnings.append({"code": "BUY_TRADES_TOO_FEW_FOR_DEFAULT_RELEASE", "actual": buy_trades, "expected": ">=10"})
    status = "FAIL" if violations else "WARN" if warnings else "PASS"
    return status, warnings, violations


def _metrics_payload(
    *,
    profile_id: str,
    result,
    account: dict[str, Any],
    strategy: dict[str, Any],
    account_report: dict[str, Any],
    account_config_path: Path,
    strategy_config_path: Path,
    start_date: str,
    end_date: str,
    research_only: bool,
    account_profile_path: str,
    strategy_profile_path: str,
) -> dict[str, Any]:
    metrics = dict(result.metrics)
    nav = result.nav if result.nav is not None else pd.DataFrame()
    detailed = result.trades_detailed if result.trades_detailed is not None else pd.DataFrame()
    years = max(len(nav) / 252, 1 / 252) if not nav.empty else 0.0
    initial = float(account.get("account", {}).get("initial_capital", 0.0) or 0.0)
    cost_total = float(metrics.get("total_fees", 0.0) or 0.0) + float(metrics.get("total_tax", 0.0) or 0.0) + float(metrics.get("total_slippage", 0.0) or 0.0)
    if not nav.empty and "cash" in nav and "nav" in nav:
        average_cash_ratio = float((pd.to_numeric(nav["cash"], errors="coerce") / pd.to_numeric(nav["nav"], errors="coerce")).dropna().mean())
    else:
        average_cash_ratio = 0.0
    max_weight_after = 0.0
    if not detailed.empty and "weight_after" in detailed:
        max_weight_after = float(pd.to_numeric(detailed["weight_after"], errors="coerce").fillna(0).max())
    metrics["max_weight_after"] = max_weight_after
    status, warnings, violations = _profile_status(
        profile_id=profile_id,
        metrics=metrics,
        account_report=account_report,
        account=account,
        strategy=strategy,
        years=years,
    )
    profile_meta = runtime_profile_metadata(account_config=account_config_path, strategy_config=strategy_config_path)
    payload = {
        **profile_meta,
        "profile_id": profile_id,
        "research_only": bool(research_only),
        "status": status,
        "warnings": warnings,
        "violations": violations,
        "start_date": start_date,
        "end_date": end_date,
        "execution_mode": result.execution_mode,
        "account_profile_path": account_profile_path,
        "strategy_profile_path": strategy_profile_path,
        "account_config_effective": str(account_config_path.relative_to(ROOT)),
        "strategy_config_effective": str(strategy_config_path.relative_to(ROOT)),
        "config_hash": config_hash([account_config_path, strategy_config_path, "config/universe_rules_v2.yml", "config/metric_map.yml"]),
        "profile_config_hash": stable_hash({"account": account, "strategy_execution": strategy.get("execution", {})}),
        "data_hash": data_hash(),
        "lot_aware_sizing": bool(strategy.get("execution", {}).get("lot_aware_sizing", False)),
        "pending_add_state_enabled": bool(strategy.get("execution", {}).get("pending_add_state", False)),
        "duplicate_blocked_signal_suppression": bool(strategy.get("execution", {}).get("duplicate_blocked_signal_suppression", False)),
        "raw_buy_signal_count": int(account_report.get("raw_buy_signal_count", 0) or 0),
        "unique_raw_buy_intent_count": int(account_report.get("unique_raw_buy_intent_count", account_report.get("raw_buy_signal_count", 0)) or 0),
        "repeated_blocked_buy_signal_count": int(account_report.get("repeated_blocked_buy_signal_count", 0) or 0),
        "repeat_raw_buy_intent_count": int(account_report.get("repeat_raw_buy_intent_count", 0) or 0),
        "repeat_raw_buy_intent_ratio": account_report.get("repeat_raw_buy_intent_ratio"),
        "account_feasible_buy_signal_count": int(account_report.get("account_feasible_buy_signal_count", 0) or 0),
        "executable_buy_count": int(account_report.get("executable_buy_count", 0) or 0),
        "executable_new_position_buy_count": int(account_report.get("executable_new_position_buy_count", 0) or 0),
        "executable_add_buy_count": int(account_report.get("executable_add_buy_count", 0) or 0),
        "user_visible_buy_recommendation_count": int(account_report.get("user_visible_buy_recommendation_count", 0) or 0),
        "user_visible_blocked_buy_count": int(account_report.get("user_visible_blocked_buy_count", 0) or 0),
        "pending_buy_intent_count": int(account_report.get("pending_buy_intent_count", 0) or 0),
        "full_portfolio_raw_buy_intent_count": int(account_report.get("full_portfolio_raw_buy_intent_count", 0) or 0),
        "full_portfolio_raw_buy_intent_ratio": account_report.get("full_portfolio_raw_buy_intent_ratio"),
        "new_position_raw_intent_count": int(account_report.get("new_position_raw_intent_count", 0) or 0),
        "add_position_raw_intent_count": int(account_report.get("add_position_raw_intent_count", 0) or 0),
        "blocked_buy_count": int(account_report.get("blocked_buy_count", 0) or 0),
        "executable_raw_buy_ratio": account_report.get("executable_raw_buy_ratio"),
        "executable_unique_raw_intent_ratio": account_report.get("executable_unique_raw_intent_ratio"),
        "executable_account_feasible_buy_ratio": account_report.get("executable_account_feasible_buy_ratio"),
        "block_reason_breakdown": account_report.get("block_reason_breakdown", []),
        "metric_denominators": account_report.get("metric_denominators", {}),
        "blocker_counts": account_report.get("blocker_counts", {}),
        "min_trade_amount_block_ratio": _ratio(float(account_report.get("min_trade_amount_block_count", 0) or 0), float(account_report.get("raw_buy_signal_count", 0) or 0)),
        "lot_size_zero_block_count": int(account_report.get("lot_size_block_count", 0) or 0),
        "lot_size_zero_block_ratio": _ratio(float(account_report.get("lot_size_block_count", 0) or 0), float(account_report.get("raw_buy_signal_count", 0) or 0)),
        "price_too_high_for_account_lot_count": int(account_report.get("price_too_high_for_account_lot_count", 0) or 0),
        "price_too_high_for_account_lot_ratio": _ratio(float(account_report.get("price_too_high_for_account_lot_count", 0) or 0), float(account_report.get("raw_buy_signal_count", 0) or 0)),
        "cash_insufficient_for_one_lot_count": int(account_report.get("cash_one_lot_block_count", 0) or 0),
        "cash_insufficient_for_one_lot_ratio": _ratio(float(account_report.get("cash_one_lot_block_count", 0) or 0), float(account_report.get("raw_buy_signal_count", 0) or 0)),
        "price_too_high_for_remaining_capacity_count": int(account_report.get("price_too_high_for_remaining_capacity_count", 0) or 0),
        "lot_size_accumulation_required_count": int(account_report.get("lot_size_accumulation_required_count", 0) or 0),
        "cash_block_ratio": _ratio(float(account_report.get("cash_block_count", 0) or 0), float(account_report.get("raw_buy_signal_count", 0) or 0)),
        "exposure_block_ratio": _ratio(float(account_report.get("exposure_block_count", 0) or 0), float(account_report.get("raw_buy_signal_count", 0) or 0)),
        "max_positions_block_ratio": _ratio(float(account_report.get("max_positions_block_count", 0) or 0), float(account_report.get("raw_buy_signal_count", 0) or 0)),
        "average_positions": float(metrics.get("avg_positions", 0.0) or 0.0),
        "max_positions_seen": int(metrics.get("max_positions", 0) or 0),
        "average_cash_ratio": average_cash_ratio,
        "average_exposure": float(metrics.get("avg_daily_exposure", 0.0) or 0.0),
        "max_exposure": float(metrics.get("max_daily_exposure", 0.0) or 0.0),
        "annual_return": float(metrics.get("annual_return", 0.0) or 0.0),
        "cumulative_return": float(metrics.get("cumulative_return", 0.0) or 0.0),
        "max_drawdown": float(metrics.get("max_drawdown", 0.0) or 0.0),
        "Sharpe": float(metrics.get("sharpe", 0.0) or 0.0),
        "turnover": float(metrics.get("turnover", 0.0) or 0.0),
        "transaction_cost_total": cost_total,
        "transaction_cost_as_pct_of_initial_capital": (cost_total / initial) if initial else None,
        "annualized_transaction_cost_drag": (cost_total / initial / years) if initial and years else None,
        "total_fees": float(metrics.get("total_fees", 0.0) or 0.0),
        "total_tax": float(metrics.get("total_tax", 0.0) or 0.0),
        "total_slippage": float(metrics.get("total_slippage", 0.0) or 0.0),
        "total_trades": int(metrics.get("total_trades", 0) or 0),
        "buy_trades": int(metrics.get("buy_trades", 0) or 0),
        "sell_trades": int(metrics.get("sell_trades", 0) or 0),
    }
    return payload


def _write_profile_report(out_dir: Path, payload: dict[str, Any]) -> None:
    (out_dir / "metrics.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    pd.DataFrame([payload]).to_csv(out_dir / "metrics.csv", index=False)
    lines = [
        f"# {payload['profile_id']} account profile backtest",
        "",
        f"- status: {payload['status']}",
        f"- research_only: {str(payload['research_only']).lower()}",
        f"- initial_capital: {payload['initial_capital']}",
        f"- min_trade_value: {payload['min_trade_value']}",
        f"- portfolio_max_positions: {payload['portfolio_max_positions']}",
        f"- portfolio_equal_weight_target_positions: {payload['portfolio_equal_weight_target_positions']}",
        f"- universe_target_size: {payload['universe_target_size']}",
        f"- universe_selected_count: {payload['universe_selected_count']}",
        f"- lot_aware_sizing: {str(payload['lot_aware_sizing']).lower()}",
        f"- raw_buy_signal_count: {payload['raw_buy_signal_count']}",
        f"- unique_raw_buy_intent_count: {payload['unique_raw_buy_intent_count']}",
        f"- repeated_blocked_buy_signal_count: {payload['repeated_blocked_buy_signal_count']}",
        f"- account_feasible_buy_signal_count: {payload['account_feasible_buy_signal_count']}",
        f"- executable_buy_count: {payload['executable_buy_count']}",
        f"- executable_raw_buy_ratio: {payload['executable_raw_buy_ratio']}",
        f"- executable_account_feasible_buy_ratio: {payload['executable_account_feasible_buy_ratio']}",
        f"- user_visible_buy_recommendation_count: {payload['user_visible_buy_recommendation_count']}",
        f"- user_visible_blocked_buy_count: {payload['user_visible_blocked_buy_count']}",
        f"- pending_buy_intent_count: {payload['pending_buy_intent_count']}",
        f"- min_trade_amount_block_ratio: {payload['min_trade_amount_block_ratio']}",
        f"- lot_size_zero_block_count: {payload['lot_size_zero_block_count']}",
        f"- lot_size_zero_block_ratio: {payload['lot_size_zero_block_ratio']}",
        f"- price_too_high_for_account_lot_count: {payload['price_too_high_for_account_lot_count']}",
        f"- cash_block_ratio: {payload['cash_block_ratio']}",
        f"- max_positions_block_ratio: {payload['max_positions_block_ratio']}",
        f"- average_positions: {payload['average_positions']}",
        f"- max_positions_seen: {payload['max_positions_seen']}",
        f"- annual_return: {payload['annual_return']}",
        f"- cumulative_return: {payload['cumulative_return']}",
        f"- max_drawdown: {payload['max_drawdown']}",
        f"- Sharpe: {payload['Sharpe']}",
        f"- turnover: {payload['turnover']}",
        f"- transaction_cost_pct: {payload['transaction_cost_as_pct_of_initial_capital']}",
        "",
        "## warnings",
        "",
    ]
    lines.extend([f"- {item['code']}: actual={item.get('actual')} expected={item.get('expected')}" for item in payload["warnings"]] or ["- none"])
    lines.extend(["", "## violations", ""])
    lines.extend([f"- {item['code']}: actual={item.get('actual')} expected={item.get('expected')}" for item in payload["violations"]] or ["- none"])
    (out_dir / "trade_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _adoption_decision(profile_payloads: list[dict[str, Any]]) -> tuple[bool, str, list[str]]:
    by_profile = {item["profile_id"]: item for item in profile_payloads}
    retail = by_profile.get("actual_50k_retail", {})
    lot = by_profile.get("actual_50k_lot_aware", {})
    if not retail or not lot:
        return False, "lot-aware 或 retail profile 缺失，不能切默认。", ["missing_profile"]
    reasons: list[str] = []
    retail_ratio = float(retail.get("executable_raw_buy_ratio") or 0.0)
    lot_ratio = float(lot.get("executable_raw_buy_ratio") or 0.0)
    retail_exec = int(retail.get("executable_buy_count") or 0)
    lot_exec = int(lot.get("executable_buy_count") or 0)
    retail_min_ratio = retail.get("min_trade_amount_block_ratio")
    lot_min_ratio = lot.get("min_trade_amount_block_ratio")
    retail_lot_zero = int(retail.get("lot_size_zero_block_count") or 0)
    lot_lot_zero = int(lot.get("lot_size_zero_block_count") or 0)
    annual_cost_drag = lot.get("annualized_transaction_cost_drag")
    drawdown_delta = float(retail.get("max_drawdown") or 0.0) - float(lot.get("max_drawdown") or 0.0)
    checks = [
        (lot_ratio > retail_ratio, "executable_raw_buy_ratio 没有高于 actual_50k_retail"),
        (lot_exec > retail_exec, "executable_buy_count 没有高于 actual_50k_retail"),
        (lot_min_ratio is not None and retail_min_ratio is not None and float(lot_min_ratio) <= float(retail_min_ratio) + 1e-12, "MIN_TRADE_AMOUNT 阻断占比高于 retail"),
        (lot_lot_zero <= int(retail_lot_zero * 0.70), "LOT_SIZE_ZERO 阻断没有至少下降 30%"),
        (int(lot.get("portfolio_max_positions") or 0) <= 8, "max_positions 超过 8"),
        (not lot.get("violations"), "存在执行层 FAIL 违规"),
        (annual_cost_drag is not None and float(annual_cost_drag) <= 0.03, "年化交易成本拖累高于 3%"),
        (drawdown_delta <= 0.05 + 1e-12, "max_drawdown 比 retail 恶化超过 5 个百分点"),
        (int(lot.get("buy_trades") or 0) >= 10, "buy_trades 低于 10，收益口径不够有意义"),
    ]
    for ok, reason in checks:
        if not ok:
            reasons.append(reason)
    adopted = not reasons
    if adopted:
        return True, "actual_50k_lot_aware 满足本轮全部切默认条件。", []
    return False, "actual_50k_lot_aware 未满足全部切默认条件，默认继续保留 retail_50k。", reasons


def _comparison_payload(profile_payloads: list[dict[str, Any]]) -> dict[str, Any]:
    adopted, adoption_reason, adoption_failures = _adoption_decision(profile_payloads)
    rows = []
    for item in profile_payloads:
        adopted_as_default = bool(adopted and item["profile_id"] == "actual_50k_lot_aware") or bool(
            not adopted and item["profile_id"] == "actual_50k_retail"
        )
        rows.append(
            {
                "profile": item["profile_id"],
                "initial_capital": item["initial_capital"],
                "min_trade_value": item["min_trade_value"],
                "portfolio_max_positions": item["portfolio_max_positions"],
                "equal_weight_target_universe_size": item["portfolio_equal_weight_target_positions"],
                "lot_aware_sizing": item["lot_aware_sizing"],
                "raw_buy_signal_count": item["raw_buy_signal_count"],
                "unique_raw_buy_intent_count": item["unique_raw_buy_intent_count"],
                "repeated_blocked_buy_signal_count": item["repeated_blocked_buy_signal_count"],
                "account_feasible_buy_signal_count": item["account_feasible_buy_signal_count"],
                "executable_buy_count": item["executable_buy_count"],
                "executable_raw_buy_ratio": item["executable_raw_buy_ratio"],
                "executable_account_feasible_buy_ratio": item["executable_account_feasible_buy_ratio"],
                "user_visible_buy_recommendation_count": item["user_visible_buy_recommendation_count"],
                "user_visible_blocked_buy_count": item["user_visible_blocked_buy_count"],
                "pending_buy_intent_count": item["pending_buy_intent_count"],
                "min_trade_amount_block_ratio": item["min_trade_amount_block_ratio"],
                "min_trade_amount_block_count": int((item.get("blocker_counts") or {}).get("MIN_TRADE_AMOUNT", 0)),
                "lot_size_zero_block_count": item["lot_size_zero_block_count"],
                "lot_size_zero_block_ratio": item["lot_size_zero_block_ratio"],
                "price_too_high_for_account_lot_count": item["price_too_high_for_account_lot_count"],
                "price_too_high_for_account_lot_ratio": item["price_too_high_for_account_lot_ratio"],
                "cash_insufficient_for_one_lot_count": item["cash_insufficient_for_one_lot_count"],
                "cash_insufficient_for_one_lot_ratio": item["cash_insufficient_for_one_lot_ratio"],
                "cash_block_ratio": item["cash_block_ratio"],
                "exposure_block_ratio": item["exposure_block_ratio"],
                "max_positions_block_ratio": item["max_positions_block_ratio"],
                "average_positions": item["average_positions"],
                "max_positions": item["max_positions_seen"],
                "average_cash_ratio": item["average_cash_ratio"],
                "average_exposure": item["average_exposure"],
                "max_exposure": item["max_exposure"],
                "annual_return": item["annual_return"],
                "cumulative_return": item["cumulative_return"],
                "max_drawdown": item["max_drawdown"],
                "Sharpe": item["Sharpe"],
                "turnover": item["turnover"],
                "transaction_cost_total": item["transaction_cost_total"],
                "transaction_cost_pct": item["transaction_cost_as_pct_of_initial_capital"],
                "annualized_transaction_cost_drag": item["annualized_transaction_cost_drag"],
                "buy_trades": item["buy_trades"],
                "sell_trades": item["sell_trades"],
                "total_trades": item["total_trades"],
                "status": item["status"],
                "warnings": item["warnings"],
                "research_only": item["research_only"],
                "config_hash": item["profile_config_hash"],
                "adopted_as_default": adopted_as_default,
                "adoption_reason": adoption_reason if adopted_as_default else "",
            }
        )
    status = "FAIL" if any(row["status"] == "FAIL" for row in rows) else "WARN" if any(row["status"] == "WARN" for row in rows) else "PASS"
    retail = next((item for item in profile_payloads if item["profile_id"] == "actual_50k_retail"), {})
    default_profile = "actual_50k_lot_aware" if adopted else "actual_50k_retail"
    return {
        "status": status,
        "account_profile_comparison_status": status,
        "default_release_profile": default_profile,
        "release_account_profile": "retail_50k_lot_aware" if adopted else "retail_50k",
        "lot_aware_adopted_as_default": adopted,
        "adoption_reason": adoption_reason,
        "adoption_failures": adoption_failures,
        "manual_review_required": True,
        "auto_trading_approved": False,
        "broker_integration_enabled": False,
        "llm_decision_allowed": False,
        "not_production_ready": True,
        "retail_50k_executable_raw_buy_ratio": retail.get("executable_raw_buy_ratio"),
        "profiles": rows,
    }


def _write_comparison(out_root: Path, payload: dict[str, Any]) -> None:
    json_path = out_root / "account_profile_comparison.json"
    md_path = out_root / "account_profile_comparison.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    rows = payload["profiles"]
    by_profile = {row["profile"]: row for row in rows}
    unmodified = by_profile.get("actual_50k_unmodified", {})
    retail = by_profile.get("actual_50k_retail", {})
    min_trade_delta = None
    if unmodified and retail:
        min_trade_delta = (unmodified.get("min_trade_amount_block_ratio") or 0) - (retail.get("min_trade_amount_block_ratio") or 0)
    lines = [
        "# 账户 profile 回测对比",
        "",
        f"- status: {payload['status']}",
        f"- default_release_profile: {payload['default_release_profile']}",
        f"- release_account_profile: {payload['release_account_profile']}",
        f"- lot_aware_adopted_as_default: {str(payload['lot_aware_adopted_as_default']).lower()}",
        f"- adoption_reason: {payload['adoption_reason']}",
        "- manual_review_required: true",
        "- auto_trading_approved: false",
        "- broker_integration_enabled: false",
        "- llm_decision_allowed: false",
        "- not production ready",
        "",
        "## 对比表",
        "",
        "| profile | initial | min_trade | max_pos | eq_target | lot_aware | raw | unique | repeat_blocked | feasible | executable | exec/raw | exec/feasible | visible_buy | visible_blocked | pending | MIN_TRADE ratio | LOT_SIZE count/ratio | PRICE_TOO_HIGH count | annual | cumulative | max_dd | Sharpe | turnover | cost_pct | max_pos_seen | status | adopted |",
        "|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for row in rows:
        lines.append(
            "| {profile} | {initial_capital} | {min_trade_value} | {portfolio_max_positions} | {equal_weight_target_universe_size} | "
            "{lot_aware_sizing} | {raw_buy_signal_count} | {unique_raw_buy_intent_count} | {repeated_blocked_buy_signal_count} | "
            "{account_feasible_buy_signal_count} | {executable_buy_count} | {executable_raw_buy_ratio} | "
            "{executable_account_feasible_buy_ratio} | {user_visible_buy_recommendation_count} | {user_visible_blocked_buy_count} | "
            "{pending_buy_intent_count} | {min_trade_amount_block_ratio} | {lot_size_zero_block_count}/{lot_size_zero_block_ratio} | "
            "{price_too_high_for_account_lot_count} | {annual_return} | {cumulative_return} | {max_drawdown} | {Sharpe} | "
            "{turnover} | {transaction_cost_pct} | {max_positions} | {status} | {adopted_as_default} |".format(**row)
        )
    lines.extend(
        [
            "",
            "## adoption failures",
            "",
        ]
    )
    lines.extend([f"- {item}" for item in payload.get("adoption_failures", [])] or ["- none"])
    lines.extend(
        [
            "",
            "## 人话说明",
            "",
            "- 50000 元账户继续使用 5000 元最小交易额时，单笔门槛约等于本金 10%，大量 raw buy 会在资金颗粒度上被阻断。",
            f"- retail_50k 把最小交易额降到 1500 元后，MIN_TRADE_AMOUNT 阻断占比较 5000 元原参数下降 {min_trade_delta}；这是用同一 raw buy 口径比较，不是重定义 raw buy。",
            "- lot-aware sizing 会把 NEW_BUY 提升到至少一手，同时仍受现金、单票上限和每日开仓数约束；ADD 不足一手时进入 pending，不进入可执行买入。",
            "- 8 或 12 只最大持仓是组合执行层约束，目标是让 50000 元资金的单票交易额更符合整手颗粒度；universe target 仍是 36，只代表候选股票池目标。",
            f"- actual_50k_retail executable/raw={retail.get('executable_raw_buy_ratio')}，是否解除账户约束 WARN 仍按 25% 门槛判断。",
            "- 当前输出只用于人工观察和研究复核，不是实盘批准，也不包含自动下单或券商接口。",
        ]
    )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _latest_universe_stocks(end_date: str) -> list[dict[str, Any]]:
    history_path = resolve_path(V2_HISTORY_DIR)
    candidates: list[tuple[pd.Timestamp, Path]] = []
    if history_path.exists():
        for path in history_path.glob("*.json"):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            effective = payload.get("effective_from") or payload.get("as_of_date") or path.stem
            try:
                ts = pd.Timestamp(effective)
            except Exception:
                continue
            if ts <= pd.Timestamp(end_date):
                candidates.append((ts, path))
    if candidates:
        _, path = max(candidates, key=lambda item: item[0])
        return json.loads(path.read_text(encoding="utf-8")).get("stocks", []) or []
    universe = load_yaml("config/universe.yml")
    return universe.get("stocks", []) if isinstance(universe.get("stocks"), list) else []


def _build_lot_affordability_report(
    *,
    features: pd.DataFrame,
    account: dict[str, Any],
    strategy: dict[str, Any],
    end_date: str,
    output_root: Path,
) -> dict[str, Any]:
    account_values = account.get("account", {}) or {}
    execution = account.get("execution", {}) or {}
    sizing = account.get("position_sizing", {}) or {}
    strategy_execution = strategy.get("execution", {}) or {}
    initial = float(account_values.get("latest_total_equity") or account_values.get("initial_capital") or 0.0)
    cash = float(account_values.get("current_cash") or initial)
    round_lot = int(execution.get("round_lot", 100) or 100)
    min_trade = float(sizing.get("min_trade_value", 0.0) or 0.0)
    max_single_weight = float(sizing.get("max_single_stock_weight", 0.0) or 0.0)
    max_single_value = initial * max_single_weight
    target_positions = int(strategy_execution.get("equal_weight_target_universe_size", 1) or 1)
    target_position_value = initial / max(target_positions, 1)
    latest_date = str(features["date"].max()) if not features.empty and "date" in features.columns else end_date
    latest_features = features[features["date"].astype(str) == latest_date].copy() if not features.empty else pd.DataFrame()
    feature_lookup = latest_features.set_index("symbol").to_dict(orient="index") if "symbol" in latest_features.columns else {}
    rows: list[dict[str, Any]] = []
    for item in _latest_universe_stocks(end_date):
        symbol = str(item.get("symbol") or item.get("code") or "")
        row = feature_lookup.get(symbol, {})
        close = float(row.get("close") or item.get("close") or 0.0)
        lot_notional = close * round_lot if close > 0 else 0.0
        minimum_lots = ceil(max(min_trade, lot_notional) / lot_notional) if lot_notional > 0 else 0
        minimum_lot_order_value = minimum_lots * lot_notional
        price_too_high = bool(lot_notional > max_single_value + 1e-9)
        affordable_one_lot = bool(lot_notional > 0 and lot_notional <= max_single_value + 1e-9 and lot_notional <= cash + 1e-9)
        affordable_min = bool(not price_too_high and minimum_lot_order_value > 0 and minimum_lot_order_value <= cash + 1e-9 and minimum_lot_order_value <= max_single_value + 1e-9)
        if price_too_high:
            reason = "PRICE_TOO_HIGH_FOR_ACCOUNT_LOT"
        elif not affordable_one_lot:
            reason = "CASH_INSUFFICIENT_FOR_ONE_LOT"
        elif not affordable_min:
            reason = "CASH_INSUFFICIENT"
        else:
            reason = ""
        rows.append(
            {
                "symbol": symbol,
                "name": item.get("name"),
                "industry": item.get("industry") or item.get("industry_l1"),
                "bucket": item.get("bucket"),
                "close": close,
                "lot_notional": lot_notional,
                "minimum_lot_order_value": minimum_lot_order_value,
                "max_single_position_value": max_single_value,
                "target_position_value": target_position_value,
                "affordable_one_lot": affordable_one_lot,
                "affordable_min_trade_lot_order": affordable_min,
                "price_too_high_for_50k_lot": price_too_high,
                "execution_eligible_for_new_buy": affordable_min,
                "execution_ineligible_reason": reason,
            }
        )
    frame = pd.DataFrame(rows)
    breakdown = {
        "universe_count": int(len(frame)),
        "execution_eligible_for_new_buy_count": int(frame.get("execution_eligible_for_new_buy", pd.Series(dtype=bool)).fillna(False).sum()) if not frame.empty else 0,
        "price_too_high_for_50k_lot_count": int(frame.get("price_too_high_for_50k_lot", pd.Series(dtype=bool)).fillna(False).sum()) if not frame.empty else 0,
        "cash_insufficient_for_one_lot_count": int((frame.get("execution_ineligible_reason", pd.Series(dtype=str)).astype(str) == "CASH_INSUFFICIENT_FOR_ONE_LOT").sum()) if not frame.empty else 0,
    }
    payload = {
        "status": "WARN" if breakdown["execution_eligible_for_new_buy_count"] < breakdown["universe_count"] else "PASS",
        "account_profile": account.get("account_profile", "retail_50k_lot_aware"),
        "as_of_date": latest_date,
        "initial_capital": initial,
        "min_trade_value": min_trade,
        "round_lot": round_lot,
        "max_single_position_value": max_single_value,
        "target_position_value": target_position_value,
        "affordability_breakdown": breakdown,
        "constituents": rows,
    }
    json_path = output_root / "lot_affordability_report.json"
    md_path = output_root / "lot_affordability_report.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# 50k 整手可买性报告",
        "",
        f"- status: {payload['status']}",
        f"- as_of_date: {latest_date}",
        f"- account_profile: {payload['account_profile']}",
        f"- initial_capital: {initial}",
        f"- min_trade_value: {min_trade}",
        f"- round_lot: {round_lot}",
        f"- max_single_position_value: {max_single_value}",
        f"- target_position_value: {target_position_value}",
        "",
        "## breakdown",
        "",
    ]
    for key, value in breakdown.items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## execution ineligible", ""])
    ineligible = [row for row in rows if not row["execution_eligible_for_new_buy"]]
    for row in ineligible[:50]:
        lines.append(
            f"- {row['symbol']} {row.get('name') or ''}: lot_notional={row['lot_notional']:.2f}, "
            f"max_single={row['max_single_position_value']:.2f}, reason={row['execution_ineligible_reason']}"
        )
    if not ineligible:
        lines.append("- none")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return payload


def _publish_default_profile_outputs(out_root: Path, comparison: dict[str, Any]) -> None:
    default_profile = str(comparison.get("default_release_profile", "actual_50k_retail"))
    src_dir = out_root / default_profile
    if not src_dir.exists():
        return
    canonical = resolve_path("reports/backtest")
    canonical.mkdir(parents=True, exist_ok=True)
    copies = [
        (src_dir / f"{default_profile}_signal_funnel.csv", canonical / "combined_v2_signal_funnel.csv"),
        (src_dir / f"{default_profile}_universe_funnel.csv", canonical / "combined_v2_universe_funnel.csv"),
        (src_dir / f"{default_profile}_blocked_signals.csv", canonical / "combined_v2_blocked_signals.csv"),
        (src_dir / f"{default_profile}_trades_detailed.csv", canonical / "combined_v2_trades_detailed.csv"),
        (src_dir / f"{default_profile}_candidate_scores.csv", canonical / "combined_v2_candidate_scores.csv"),
        (src_dir / f"{default_profile}_diagnostic_report.md", canonical / "combined_v2_diagnostic_report.md"),
        (src_dir / "equity_curve.csv", canonical / "combined_v2_equity_curve.csv"),
        (src_dir / "metrics.csv", canonical / "combined_v2_retail_50k_metrics.csv"),
        (src_dir / "metrics.csv", canonical / "combined_v2_default_account_metrics.csv"),
    ]
    for source, target in copies:
        if source.exists():
            shutil.copyfile(source, target)


def run_account_profile_backtests(
    *,
    start_date: str = DEFAULT_START_DATE,
    end_date: str = DEFAULT_END_DATE,
    features_file: str = DEFAULT_FEATURES_FILE,
    benchmark_file: str = DEFAULT_BENCHMARK_FILE,
    output_root: str = OUT_ROOT,
) -> dict[str, Any]:
    configs = load_audit_configs()
    prepare_v2_history(configs, end_date=end_date, features_file=features_file, start_date=start_date)
    features = load_feature_window(start_date, end_date, features_file)
    benchmark = load_benchmark_window(start_date, end_date, benchmark_file)
    out_root = resolve_path(output_root)
    out_root.mkdir(parents=True, exist_ok=True)
    profiles = _profile_configs(configs)
    payloads: list[dict[str, Any]] = []
    for profile_id in PROFILE_ORDER:
        profile = profiles[profile_id]
        out_dir = out_root / profile_id
        out_dir.mkdir(parents=True, exist_ok=True)
        account_path, strategy_path = _write_effective_configs(out_dir, profile["account"], profile["strategy"])
        result = run_profile(
            "combined_v2",
            features,
            benchmark,
            configs,
            execution_mode="next_bar",
            historical_universe_dir=V2_HISTORY_DIR,
            strategy_cfg=profile["strategy"],
            universe_cfg=configs["v2_universe"],
            account_cfg=profile["account"],
        )
        universe, scores = build_universe_funnel(features, V2_HISTORY_DIR, configs["v2_universe"], configs["metric_map"])
        paths = write_diagnostic_outputs(profile_id, result, universe, output_dir=out_dir, candidate_scores=scores)
        result.nav.to_csv(out_dir / "equity_curve.csv", index=False)
        (result.trade_list if result.trade_list is not None else pd.DataFrame()).to_csv(out_dir / "trade_list.csv", index=False)
        account_report = build_account_constraints_report(
            signal_funnel_path=str(paths["signal_funnel"].relative_to(ROOT)),
            blocked_signals_path=str(paths["blocked_signals"].relative_to(ROOT)),
            trades_path=str(paths["trades_detailed"].relative_to(ROOT)),
            account_config=str(account_path.relative_to(ROOT)),
            strategy_config=str(strategy_path.relative_to(ROOT)),
            output_json=str((out_dir / "account_constraints_report.json").relative_to(ROOT)),
            output_md=str((out_dir / "account_constraints_report.md").relative_to(ROOT)),
            write_report=True,
        )
        build_account_suitability_report(
            account_config=str(account_path.relative_to(ROOT)),
            strategy_config=str(strategy_path.relative_to(ROOT)),
            signal_funnel_path=str(paths["signal_funnel"].relative_to(ROOT)),
            blocked_signals_path=str(paths["blocked_signals"].relative_to(ROOT)),
            trades_path=str(paths["trades_detailed"].relative_to(ROOT)),
            output_json=str((out_dir / "account_suitability_report.json").relative_to(ROOT)),
            output_md=str((out_dir / "account_suitability_report.md").relative_to(ROOT)),
            write_report=True,
        )
        payload = _metrics_payload(
            profile_id=profile_id,
            result=result,
            account=profile["account"],
            strategy=profile["strategy"],
            account_report=account_report,
            account_config_path=account_path,
            strategy_config_path=strategy_path,
            start_date=start_date,
            end_date=end_date,
            research_only=bool(profile["research_only"]),
            account_profile_path=profile["account_profile_path"],
            strategy_profile_path=profile["strategy_profile_path"],
        )
        _write_profile_report(out_dir, payload)
        payloads.append(payload)
        if profile_id == "actual_50k_retail":
            canonical_paths = write_diagnostic_outputs("combined_v2", result, universe, output_dir="reports/backtest", candidate_scores=scores)
            result.nav.to_csv(resolve_path("reports/backtest/combined_v2_equity_curve.csv"), index=False)
            pd.DataFrame([payload]).to_csv(resolve_path("reports/backtest/combined_v2_retail_50k_metrics.csv"), index=False)
            _ = canonical_paths
    lot_profile = profiles["actual_50k_lot_aware"]
    _build_lot_affordability_report(
        features=features,
        account=lot_profile["account"],
        strategy=lot_profile["strategy"],
        end_date=end_date,
        output_root=out_root,
    )
    comparison = _comparison_payload(payloads)
    _write_comparison(out_root, comparison)
    _publish_default_profile_outputs(out_root, comparison)
    return comparison


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run combined_v2 backtests across account execution profiles.")
    parser.add_argument("--start-date", default=DEFAULT_START_DATE)
    parser.add_argument("--end-date", default=DEFAULT_END_DATE)
    parser.add_argument("--features-file", default=DEFAULT_FEATURES_FILE)
    parser.add_argument("--benchmark-file", default=DEFAULT_BENCHMARK_FILE)
    parser.add_argument("--output-root", default=OUT_ROOT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = run_account_profile_backtests(
        start_date=args.start_date,
        end_date=args.end_date,
        features_file=args.features_file,
        benchmark_file=args.benchmark_file,
        output_root=args.output_root,
    )
    return 1 if payload["status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
