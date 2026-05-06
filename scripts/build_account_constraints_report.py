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

from scripts.report_metadata import metadata_header, runtime_profile_lines, runtime_profile_metadata, status_from_children, write_json
from src.utils.config import resolve_path


JSON_PATH = "reports/backtest/account_constraints_report.json"
MD_PATH = "reports/backtest/account_constraints_report.md"


BLOCKER_COLUMNS = {
    "MIN_TRADE_AMOUNT": "min_trade_amount_block_count",
    "MIN_TRADE_AMOUNT_AT_FILL": "min_trade_amount_block_count",
    "CASH_INSUFFICIENT": "cash_block_count",
    "CASH_INSUFFICIENT_AT_FILL": "cash_block_count",
    "CASH_CLIPPED_AT_FILL": "cash_block_count",
    "CASH_INSUFFICIENT_FOR_ONE_LOT": "cash_one_lot_block_count",
    "TOTAL_EXPOSURE_LIMIT": "exposure_block_count",
    "TOTAL_EXPOSURE_LIMIT_AT_FILL": "exposure_block_count",
    "TOTAL_EXPOSURE_CLIPPED_AT_FILL": "exposure_block_count",
    "SINGLE_NAME_LIMIT": "single_name_block_count",
    "SINGLE_NAME_LIMIT_AT_FILL": "single_name_block_count",
    "SINGLE_NAME_CLIPPED_AT_FILL": "single_name_block_count",
    "LOT_SIZE_ZERO": "lot_size_block_count",
    "PRICE_TOO_HIGH_FOR_ACCOUNT_LOT": "price_too_high_for_account_lot_count",
    "PRICE_TOO_HIGH_FOR_REMAINING_CAPACITY": "price_too_high_for_remaining_capacity_count",
    "LOT_SIZE_ACCUMULATION_REQUIRED": "lot_size_accumulation_required_count",
    "HOLD_WITH_PENDING_ADD": "pending_add_block_count",
    "MAX_POSITIONS_LIMIT": "max_positions_block_count",
    "DAILY_POSITION_LIMIT": "daily_new_position_block_count",
    "DAILY_NEW_POSITION_LIMIT": "daily_new_position_block_count",
    "DAILY_ADD_LIMIT": "daily_add_block_count",
    "UNKNOWN": "unknown_block_count",
}

CANONICAL_BLOCKERS = [
    "MIN_TRADE_AMOUNT",
    "CASH_INSUFFICIENT",
    "TOTAL_EXPOSURE_LIMIT",
    "LOT_SIZE_ZERO",
    "PRICE_TOO_HIGH_FOR_ACCOUNT_LOT",
    "CASH_INSUFFICIENT_FOR_ONE_LOT",
    "PRICE_TOO_HIGH_FOR_REMAINING_CAPACITY",
    "LOT_SIZE_ACCUMULATION_REQUIRED",
    "HOLD_WITH_PENDING_ADD",
    "SINGLE_NAME_LIMIT",
    "MAX_POSITIONS_LIMIT",
    "DAILY_NEW_POSITION_LIMIT",
    "DAILY_ADD_LIMIT",
    "UNKNOWN",
]

CANONICAL_MAP = {
    "MIN_TRADE_AMOUNT_AT_FILL": "MIN_TRADE_AMOUNT",
    "MIN_TRADE_VALUE": "MIN_TRADE_AMOUNT",
    "CASH_INSUFFICIENT_AT_FILL": "CASH_INSUFFICIENT",
    "CASH_CLIPPED_AT_FILL": "CASH_INSUFFICIENT",
    "INSUFFICIENT_CASH": "CASH_INSUFFICIENT",
    "CASH_INSUFFICIENT_FOR_ONE_LOT": "CASH_INSUFFICIENT_FOR_ONE_LOT",
    "TOTAL_EXPOSURE_LIMIT_AT_FILL": "TOTAL_EXPOSURE_LIMIT",
    "TOTAL_EXPOSURE_CLIPPED_AT_FILL": "TOTAL_EXPOSURE_LIMIT",
    "REGIME_CAP_BLOCK": "TOTAL_EXPOSURE_LIMIT",
    "LOT_SIZE_ZERO_AT_FILL": "LOT_SIZE_ZERO",
    "ROUND_LOT_BLOCK": "LOT_SIZE_ZERO",
    "PRICE_TOO_HIGH_FOR_ACCOUNT_LOT": "PRICE_TOO_HIGH_FOR_ACCOUNT_LOT",
    "PRICE_TOO_HIGH_FOR_REMAINING_CAPACITY": "PRICE_TOO_HIGH_FOR_REMAINING_CAPACITY",
    "LOT_SIZE_ACCUMULATION_REQUIRED": "LOT_SIZE_ACCUMULATION_REQUIRED",
    "HOLD_WITH_PENDING_ADD": "HOLD_WITH_PENDING_ADD",
    "SINGLE_NAME_LIMIT_AT_FILL": "SINGLE_NAME_LIMIT",
    "SINGLE_NAME_CLIPPED_AT_FILL": "SINGLE_NAME_LIMIT",
    "DAILY_POSITION_LIMIT": "DAILY_NEW_POSITION_LIMIT",
}


def _read_csv(path_like: str | Path) -> pd.DataFrame:
    path = resolve_path(path_like)
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _sum(frame: pd.DataFrame, column: str) -> int:
    if frame.empty or column not in frame.columns:
        return 0
    return int(pd.to_numeric(frame[column], errors="coerce").fillna(0).sum())


def _canonical_reason(raw: object) -> str:
    value = str(raw) if raw is not None else "UNKNOWN"
    return CANONICAL_MAP.get(value, value if value in CANONICAL_BLOCKERS else "UNKNOWN")


def build_account_constraints_report(
    *,
    signal_funnel_path: str = "reports/backtest/combined_v2_signal_funnel.csv",
    blocked_signals_path: str = "reports/backtest/combined_v2_blocked_signals.csv",
    trades_path: str = "reports/backtest/combined_v2_trades_detailed.csv",
    account_config: str = "config/account.yml",
    strategy_config: str = "config/strategy_v2.yml",
    universe_rules_config: str = "config/universe_rules_v2.yml",
    output_json: str = JSON_PATH,
    output_md: str = MD_PATH,
    write_report: bool = True,
) -> dict[str, Any]:
    funnel = _read_csv(signal_funnel_path)
    blocked = _read_csv(blocked_signals_path)
    trades = _read_csv(trades_path)
    raw_buy = _sum(funnel, "raw_buy_signal_count")
    raw_sell = _sum(funnel, "raw_sell_signal_count")
    unique_raw_buy_intents = _sum(funnel, "unique_raw_buy_intent_count") if "unique_raw_buy_intent_count" in funnel.columns else raw_buy
    repeated_blocked_buy = _sum(funnel, "repeated_blocked_buy_signal_count")
    user_visible_buy_recommendations = _sum(funnel, "user_visible_buy_recommendation_count")
    user_visible_blocked_buy = _sum(funnel, "user_visible_blocked_buy_count")
    pending_buy_intents = _sum(funnel, "pending_buy_intent_count")
    account_feasible_buy = _sum(funnel, "account_feasible_buy_signal_count")
    executable_buy = _sum(funnel, "executable_buy_count")
    executable_sell = _sum(funnel, "executable_sell_count")
    blocker_counts = (
        blocked["reason_code"].map(_canonical_reason).value_counts().to_dict()
        if not blocked.empty and "reason_code" in blocked.columns
        else {}
    )
    normalized_counts = {value: 0 for value in BLOCKER_COLUMNS.values()}
    for reason, count in blocker_counts.items():
        target = BLOCKER_COLUMNS.get(str(reason))
        if target:
            normalized_counts[target] = int(normalized_counts.get(target, 0)) + int(count)
        else:
            normalized_counts["unknown_block_count"] = int(normalized_counts.get("unknown_block_count", 0)) + int(count)
    average_cash_ratio = 0.0
    average_exposure = 0.0
    max_exposure = 0.0
    if not funnel.empty:
        cash = pd.to_numeric(funnel.get("current_cash", pd.Series(dtype=float)), errors="coerce")
        exposure = pd.to_numeric(funnel.get("current_total_exposure", pd.Series(dtype=float)), errors="coerce")
        average_cash_ratio = float((cash / cash.max()).replace([float("inf"), -float("inf")], pd.NA).dropna().mean()) if not cash.dropna().empty and cash.max() else 0.0
        average_exposure = float(exposure.dropna().mean()) if not exposure.dropna().empty else 0.0
        max_exposure = float(exposure.dropna().max()) if not exposure.dropna().empty else 0.0
    turnover = float(pd.to_numeric(trades.get("amount", pd.Series(dtype=float)), errors="coerce").abs().sum()) if not trades.empty else 0.0
    blocked_buy = max(0, raw_buy - executable_buy)
    blocked_sell = max(0, raw_sell - executable_sell)
    buy_ratio = executable_buy / raw_buy if raw_buy else None
    feasible_ratio = executable_buy / account_feasible_buy if account_feasible_buy else None
    sell_ratio = executable_sell / raw_sell if raw_sell else None
    warnings: list[dict[str, Any]] = []
    if buy_ratio is not None and buy_ratio < 0.25:
        warnings.append(
            {
                "code": "ACCOUNT_CONSTRAINTS_DOMINATE_BUY_EXECUTION",
                "message": "account constraints dominate buy execution",
                "expected": "executable/raw >= 0.25",
                "actual": buy_ratio,
            }
        )
    min_trade_blocks = int(normalized_counts.get("min_trade_amount_block_count", 0))
    if raw_buy and min_trade_blocks / raw_buy > 0.4:
        warnings.append(
            {
                "code": "MIN_TRADE_AMOUNT_DOMINATES_EXECUTION",
                "message": "min_trade_amount dominates execution",
                "expected": "<=40% raw buy signals",
                "actual": min_trade_blocks / raw_buy,
            }
        )
    profile_meta = runtime_profile_metadata(
        account_config=account_config,
        strategy_config=strategy_config,
        universe_rules_config=universe_rules_config,
    )
    status = status_from_children(["WARN" if warnings else "PASS"])
    payload = {
        **metadata_header(extra_config_paths=[account_config, strategy_config, universe_rules_config]),
        **profile_meta,
        "runtime_profile": profile_meta,
        "status": status,
        "raw_buy_signal_count": raw_buy,
        "unique_raw_buy_intent_count": unique_raw_buy_intents,
        "repeated_blocked_buy_signal_count": repeated_blocked_buy,
        "raw_sell_signal_count": raw_sell,
        "account_feasible_buy_signal_count": account_feasible_buy,
        "user_visible_buy_recommendation_count": user_visible_buy_recommendations,
        "user_visible_blocked_buy_count": user_visible_blocked_buy,
        "pending_buy_intent_count": pending_buy_intents,
        "executable_buy_count": executable_buy,
        "executable_sell_count": executable_sell,
        "blocked_buy_count": blocked_buy,
        "blocked_sell_count": blocked_sell,
        "blocker_counts": blocker_counts,
        **normalized_counts,
        "executable_raw_buy_ratio": buy_ratio,
        "executable_account_feasible_buy_ratio": feasible_ratio,
        "executable_raw_sell_ratio": sell_ratio,
        "average_cash_ratio": average_cash_ratio,
        "average_exposure": average_exposure,
        "max_exposure": max_exposure,
        "turnover": turnover,
        "warnings": warnings,
        "violations": [],
        "source_files": [signal_funnel_path, blocked_signals_path, trades_path],
    }
    if write_report:
        write_json(output_json, payload)
        _write_md(payload, output_md)
    return payload


def _write_md(payload: dict[str, Any], path_like: str | Path) -> None:
    path = resolve_path(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# account constraints report",
        "",
        f"- status: {payload['status']}",
        f"- generated_at: {payload['generated_at']}",
        f"- git_commit: {payload['git_commit']}",
        f"- config_hash: {payload['config_hash']}",
        "",
        "## runtime profile",
        "",
        *runtime_profile_lines(payload),
        "",
        "## execution funnel",
        "",
        f"- raw_buy_signal_count: {payload['raw_buy_signal_count']}",
        f"- unique_raw_buy_intent_count: {payload['unique_raw_buy_intent_count']}",
        f"- repeated_blocked_buy_signal_count: {payload['repeated_blocked_buy_signal_count']}",
        f"- account_feasible_buy_signal_count: {payload['account_feasible_buy_signal_count']}",
        f"- user_visible_buy_recommendation_count: {payload['user_visible_buy_recommendation_count']}",
        f"- user_visible_blocked_buy_count: {payload['user_visible_blocked_buy_count']}",
        f"- pending_buy_intent_count: {payload['pending_buy_intent_count']}",
        f"- raw_sell_signal_count: {payload['raw_sell_signal_count']}",
        f"- executable_buy_count: {payload['executable_buy_count']}",
        f"- executable_sell_count: {payload['executable_sell_count']}",
        f"- executable_raw_buy_ratio: {payload['executable_raw_buy_ratio']}",
        f"- executable_account_feasible_buy_ratio: {payload['executable_account_feasible_buy_ratio']}",
        f"- average_cash_ratio: {payload['average_cash_ratio']:.4f}",
        f"- average_exposure: {payload['average_exposure']:.4f}",
        f"- max_exposure: {payload['max_exposure']:.4f}",
        f"- turnover: {payload['turnover']:.2f}",
        "",
        "## blocker_counts",
        "",
    ]
    for key, value in sorted(payload["blocker_counts"].items()):
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## WARN", ""])
    lines.extend([f"- {item['code']}: {item['message']} actual={item['actual']}" for item in payload.get("warnings", [])] or ["- 无"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize account constraint impact on backtest execution.")
    parser.add_argument("--no-write-report", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    build_account_constraints_report(write_report=not args.no_write_report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
