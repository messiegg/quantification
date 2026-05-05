#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_account_constraints_report import build_account_constraints_report
from scripts.report_metadata import metadata_header, write_json
from src.utils.config import load_yaml, resolve_path


OUT_JSON = "reports/backtest/account_suitability_report.json"
OUT_MD = "reports/backtest/account_suitability_report.md"


def _read_csv(path_like: str | Path) -> pd.DataFrame:
    path = resolve_path(path_like)
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return default
    return default if pd.isna(numeric) else numeric


def _scenario_rows(
    blocked: pd.DataFrame,
    *,
    raw_buy: int,
    executable_buy: int,
    initial_capital: float,
    min_trade_amount: float,
    capital_multipliers: list[float],
    min_trade_multipliers: list[float],
    target_positions: list[int],
) -> list[dict[str, Any]]:
    min_trade_blocked = blocked[blocked.get("reason_code", pd.Series(dtype=str)).astype(str) == "MIN_TRADE_AMOUNT"].copy()
    current_weight = pd.to_numeric(min_trade_blocked.get("current_weight", pd.Series(dtype=float)), errors="coerce").fillna(0.0)
    target_weight = pd.to_numeric(min_trade_blocked.get("intended_target_weight", pd.Series(dtype=float)), errors="coerce").fillna(0.0)
    incremental_weight = (target_weight - current_weight).clip(lower=0.0)
    rows: list[dict[str, Any]] = []
    for capital_multiple in capital_multipliers:
        for min_trade_multiple in min_trade_multipliers:
            for target_position in target_positions:
                capital = initial_capital * capital_multiple
                min_trade = min_trade_amount * min_trade_multiple
                lifted = int((incremental_weight * capital >= min_trade).sum()) if not incremental_weight.empty else 0
                estimated_executable = min(raw_buy, executable_buy + lifted)
                ratio = estimated_executable / raw_buy if raw_buy else None
                rows.append(
                    {
                        "scenario_id": f"capital_x{capital_multiple:g}_min_trade_x{min_trade_multiple:g}_target_positions_{target_position}",
                        "research_only": not (capital_multiple == 1 and min_trade_multiple == 1),
                        "capital_multiplier": capital_multiple,
                        "initial_capital": capital,
                        "min_trade_amount": min_trade,
                        "target_positions": target_position,
                        "estimated_executable_buy_count": estimated_executable,
                        "estimated_executable_raw_buy_ratio": ratio,
                        "estimation_method": "heuristic_min_trade_only_from_intended_target_weight",
                        "limitations": [
                            "per-signal actual portfolio equity and desired trade amount are not present in blocked_signals",
                            "cash, exposure, lot-size and same-day priority interactions are not re-simulated",
                            "scenario output is research_only and cannot be used for release PASS",
                        ],
                    }
                )
    return rows


def build_account_suitability_report(
    *,
    account_config: str = "config/account.yml",
    blocked_signals_path: str = "reports/backtest/combined_v2_blocked_signals.csv",
    write_report: bool = True,
) -> dict[str, Any]:
    account = load_yaml(account_config)
    strategy = load_yaml("config/strategy_v2.yml")
    base_report = build_account_constraints_report(write_report=False)
    blocked = _read_csv(blocked_signals_path)
    account_cfg = account.get("account", {}) or {}
    execution_cfg = account.get("execution", {}) or {}
    sizing_cfg = account.get("position_sizing", {}) or {}
    initial_capital = _safe_float(account_cfg.get("initial_capital"))
    min_trade_amount = _safe_float(sizing_cfg.get("min_trade_value"))
    raw_buy = int(base_report.get("raw_buy_signal_count", 0) or 0)
    executable_buy = int(base_report.get("executable_buy_count", 0) or 0)
    buy_ratio = base_report.get("executable_raw_buy_ratio")
    blocker_counts = base_report.get("blocker_counts", {}) or {}
    min_trade_blocks = int(base_report.get("min_trade_amount_block_count", 0) or 0)
    blocked_buy = int(base_report.get("blocked_buy_count", 0) or 0)
    current_max_positions = int(strategy.get("execution", {}).get("max_positions", 0) or 0)
    scenarios = _scenario_rows(
        blocked,
        raw_buy=raw_buy,
        executable_buy=executable_buy,
        initial_capital=initial_capital,
        min_trade_amount=min_trade_amount,
        capital_multipliers=[0.5, 1, 2, 5, 10],
        min_trade_multipliers=[1, 0.5, 0.25],
        target_positions=[current_max_positions, 12, 18, 24, 30],
    )
    missing_for_exact_estimate = [
        "per_signal_actual_equity",
        "per_signal_desired_trade_amount",
        "per_signal_cash_after_priority_ordering",
    ]
    warnings = []
    if buy_ratio is not None and buy_ratio < 0.25:
        warnings.append(
            {
                "code": "BASE_CASE_EXECUTION_RATIO_BELOW_OBSERVATION_MINIMUM",
                "expected": ">=0.25",
                "actual": buy_ratio,
            }
        )
    if raw_buy and min_trade_blocks / raw_buy > 0.5:
        warnings.append(
            {
                "code": "MIN_TRADE_AMOUNT_DOMINATES_BASE_CASE",
                "expected": "<=0.50 of raw buy signals",
                "actual": min_trade_blocks / raw_buy,
            }
        )
    payload = {
        **metadata_header(extra_config_paths=[account_config]),
        "status": "WARN" if warnings else "PASS",
        "base_case": {
            "research_only": False,
            "initial_capital": initial_capital,
            "current_cash": _safe_float(account_cfg.get("current_cash")),
            "reserved_cash": _safe_float(account_cfg.get("reserved_cash")),
            "latest_total_equity": _safe_float(account_cfg.get("latest_total_equity")),
            "min_trade_amount": min_trade_amount,
            "lot_size": int(execution_cfg.get("round_lot", 0) or 0),
            "tranche_weights": sizing_cfg.get("tranche_weights", {}),
            "max_position_weight": sizing_cfg.get("max_single_stock_weight"),
            "max_total_exposure": None,
            "raw_buy_signal_count": raw_buy,
            "executable_buy_count": executable_buy,
            "executable_raw_buy_ratio": buy_ratio,
            "blocker_counts": blocker_counts,
            "min_trade_amount_block_ratio": min_trade_blocks / raw_buy if raw_buy else None,
            "cash_block_ratio": int(base_report.get("cash_block_count", 0) or 0) / raw_buy if raw_buy else None,
            "exposure_block_ratio": int(base_report.get("exposure_block_count", 0) or 0) / raw_buy if raw_buy else None,
            "lot_size_block_ratio": int(base_report.get("lot_size_block_count", 0) or 0) / raw_buy if raw_buy else None,
            "avg_positions": None,
            "max_positions": current_max_positions,
            "avg_exposure": base_report.get("average_exposure"),
            "turnover": base_report.get("turnover"),
        },
        "scenarios": scenarios,
        "estimated_capital_required_to_reach_executable_raw_25": "unknown",
        "estimated_capital_required_to_reach_executable_raw_50": "unknown",
        "missing_data_for_exact_capital_estimate": missing_for_exact_estimate,
        "recommended_manual_use_notes": [
            "当前资金与最小成交额组合会让买入执行明显受账户约束主导。",
            "非 base 场景仅用于人工评估资金规模和最小成交额适配性，不改变 release 口径。",
            "在真实观察日志证明执行比例改善前，release 顶层应保持 WARN。",
        ],
        "warnings": warnings,
        "violations": [],
        "source_files": [blocked_signals_path, "reports/backtest/account_constraints_report.json", account_config],
    }
    if write_report:
        write_json(OUT_JSON, payload)
        _write_md(payload)
    return payload


def _write_md(payload: dict[str, Any]) -> None:
    base = payload["base_case"]
    lines = [
        "# account suitability report",
        "",
        f"- status: {payload['status']}",
        f"- generated_at: {payload['generated_at']}",
        f"- initial_capital: {base['initial_capital']}",
        f"- min_trade_amount: {base['min_trade_amount']}",
        f"- raw_buy_signal_count: {base['raw_buy_signal_count']}",
        f"- executable_buy_count: {base['executable_buy_count']}",
        f"- executable_raw_buy_ratio: {base['executable_raw_buy_ratio']}",
        f"- estimated_capital_required_to_reach_executable_raw_25: {payload['estimated_capital_required_to_reach_executable_raw_25']}",
        f"- estimated_capital_required_to_reach_executable_raw_50: {payload['estimated_capital_required_to_reach_executable_raw_50']}",
        "",
        "## base blocker ratios",
        "",
        f"- min_trade_amount_block_ratio: {base['min_trade_amount_block_ratio']}",
        f"- cash_block_ratio: {base['cash_block_ratio']}",
        f"- exposure_block_ratio: {base['exposure_block_ratio']}",
        f"- lot_size_block_ratio: {base['lot_size_block_ratio']}",
        "",
        "## scenario notes",
        "",
    ]
    for item in payload["scenarios"][:15]:
        lines.append(
            f"- {item['scenario_id']}: research_only={str(item['research_only']).lower()} "
            f"estimated_ratio={item['estimated_executable_raw_buy_ratio']}"
        )
    lines.extend(["", "## missing data for exact estimate", ""])
    lines.extend([f"- {item}" for item in payload["missing_data_for_exact_capital_estimate"]])
    lines.extend(["", "## warnings", ""])
    lines.extend([f"- {item['code']}: actual={item.get('actual')}" for item in payload["warnings"]] or ["- none"])
    resolve_path(OUT_MD).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Assess whether account size and min trade amount fit observed signals.")
    parser.add_argument("--no-write-report", action="store_true")
    args = parser.parse_args()
    payload = build_account_suitability_report(write_report=not args.no_write_report)
    return 1 if payload["status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
