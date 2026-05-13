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

BUY_ACTIONS = {"BUY_1", "BUY_2", "BUY_3", "HOLD_WITH_PENDING_ADD", "BLOCKED"}

REASON_DESCRIPTIONS_ZH = {
    "MAX_POSITIONS_LIMIT": "组合已达到最大持仓数，新的买入意图被阻断。",
    "PRICE_TOO_HIGH_FOR_ACCOUNT_LOT": "按当前账户和单票上限，一手金额过高。",
    "CASH_INSUFFICIENT_FOR_ONE_LOT": "当前可用现金不足以买入一手。",
    "LOT_SIZE_ACCUMULATION_REQUIRED": "加仓目标差额、现金或剩余单票容量尚未满足一手。",
    "MIN_TRADE_AMOUNT": "目标成交额低于最小成交额。",
    "DAILY_NEW_POSITION_LIMIT": "当日新开仓数量达到上限。",
    "DAILY_ADD_LIMIT": "当日加仓数量达到上限。",
    "HARD_ADD_BAN": "硬性禁止加仓条件触发。",
    "DATA_STALE": "数据新鲜度阻断。",
    "CORE_FIELDS_INCOMPLETE": "核心字段不完整。",
    "CASH_INSUFFICIENT": "现金不足以满足目标订单金额。",
    "PRICE_TOO_HIGH_FOR_REMAINING_CAPACITY": "剩余单票容量不足以容纳一手或目标加仓。",
    "LOT_SIZE_ZERO": "目标股数低于整手后为零。",
    "UNKNOWN": "未知或未归类阻断原因。",
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


def _ratio(numerator: float, denominator: float) -> float | None:
    return float(numerator) / float(denominator) if denominator else None


def _series(frame: pd.DataFrame, column: str, default: object = "") -> pd.Series:
    if frame.empty:
        return pd.Series(dtype=object)
    if column in frame.columns:
        return frame[column]
    return pd.Series(default, index=frame.index)


def _is_buy_blocked_frame(blocked: pd.DataFrame) -> pd.Series:
    if blocked.empty:
        return pd.Series(dtype=bool)
    intended = _series(blocked, "intended_action").astype(str)
    level = _series(blocked, "intended_signal_level").astype(str)
    return intended.str.startswith("BUY_") | level.str.startswith("BUY_") | (intended == "HOLD_WITH_PENDING_ADD")


def _new_position_mask_from_blocked(blocked: pd.DataFrame) -> pd.Series:
    if blocked.empty:
        return pd.Series(dtype=bool)
    current_weight = pd.to_numeric(_series(blocked, "current_weight", 0.0), errors="coerce").fillna(0.0)
    level = _series(blocked, "intended_signal_level").astype(str)
    return (current_weight <= 0) & ~level.isin({"BUY_2", "BUY_3"})


def _add_position_mask_from_blocked(blocked: pd.DataFrame) -> pd.Series:
    if blocked.empty:
        return pd.Series(dtype=bool)
    current_weight = pd.to_numeric(_series(blocked, "current_weight", 0.0), errors="coerce").fillna(0.0)
    level = _series(blocked, "intended_signal_level").astype(str)
    return (current_weight > 0) | level.isin({"BUY_2", "BUY_3"})


def _is_buy_trade_frame(trades: pd.DataFrame) -> pd.Series:
    if trades.empty:
        return pd.Series(dtype=bool)
    side = _series(trades, "side").astype(str).str.upper()
    action = _series(trades, "action").astype(str)
    return (side == "BUY") | action.str.startswith("BUY_")


def _new_position_mask_from_trades(trades: pd.DataFrame) -> pd.Series:
    if trades.empty:
        return pd.Series(dtype=bool)
    position_before = pd.to_numeric(_series(trades, "position_before", 0.0), errors="coerce").fillna(0.0)
    action = _series(trades, "action").astype(str)
    return (position_before <= 0) & ~action.isin({"BUY_2", "BUY_3"})


def _add_position_mask_from_trades(trades: pd.DataFrame) -> pd.Series:
    if trades.empty:
        return pd.Series(dtype=bool)
    position_before = pd.to_numeric(_series(trades, "position_before", 0.0), errors="coerce").fillna(0.0)
    action = _series(trades, "action").astype(str)
    return (position_before > 0) | action.isin({"BUY_2", "BUY_3"})


def _block_reason_breakdown(blocked: pd.DataFrame, *, raw_buy: int) -> list[dict[str, Any]]:
    if blocked.empty:
        return []
    frame = blocked.copy()
    frame["reason_code"] = _series(frame, "reason_code", "UNKNOWN").map(_canonical_reason)
    blocked_count = len(frame)
    rows: list[dict[str, Any]] = []
    for reason, group in frame.groupby("reason_code", dropna=False):
        symbols = [str(item) for item in _series(group, "ts_code").dropna().astype(str).unique().tolist() if item]
        buckets = _series(group, "bucket").dropna().astype(str)
        dominant_bucket = ""
        if not buckets.empty:
            dominant_bucket = str(buckets.value_counts().idxmax())
        rows.append(
            {
                "reason_code": str(reason),
                "description_zh": REASON_DESCRIPTIONS_ZH.get(str(reason), REASON_DESCRIPTIONS_ZH["UNKNOWN"]),
                "count": int(len(group)),
                "count_pct_of_raw": _ratio(len(group), raw_buy),
                "count_pct_of_blocked": _ratio(len(group), blocked_count),
                "affected_unique_symbols": int(len(set(symbols))),
                "affected_trade_dates": int(_series(group, "date").dropna().astype(str).nunique()),
                "dominant_bucket": dominant_bucket,
                "example_symbols": symbols[:10],
            }
        )
    return sorted(rows, key=lambda item: (-int(item["count"]), item["reason_code"]))


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
    buy_blocked_mask = _is_buy_blocked_frame(blocked)
    buy_blocked = blocked.loc[buy_blocked_mask].copy() if not blocked.empty else pd.DataFrame()
    buy_trades_mask = _is_buy_trade_frame(trades)
    buy_trades = trades.loc[buy_trades_mask].copy() if not trades.empty else pd.DataFrame()
    blocked_new = int(_new_position_mask_from_blocked(buy_blocked).sum()) if not buy_blocked.empty else 0
    blocked_add = int(_add_position_mask_from_blocked(buy_blocked).sum()) if not buy_blocked.empty else 0
    executable_new = int(_new_position_mask_from_trades(buy_trades).sum()) if not buy_trades.empty else 0
    executable_add = int(_add_position_mask_from_trades(buy_trades).sum()) if not buy_trades.empty else 0
    new_position_raw_intent_count = blocked_new + executable_new
    add_position_raw_intent_count = blocked_add + executable_add
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
    repeat_raw_buy_intent_count = max(0, raw_buy - unique_raw_buy_intents)
    repeat_raw_buy_intent_ratio = _ratio(repeat_raw_buy_intent_count, raw_buy)
    executable_unique_raw_intent_ratio = _ratio(executable_buy, unique_raw_buy_intents)
    full_portfolio_raw_buy_intent_count = int(blocker_counts.get("MAX_POSITIONS_LIMIT", 0) or 0)
    full_portfolio_raw_buy_intent_ratio = _ratio(full_portfolio_raw_buy_intent_count, raw_buy)
    max_positions_block_count = int(normalized_counts.get("max_positions_block_count", 0) or 0)
    cash_block_count = int(normalized_counts.get("cash_block_count", 0) or 0)
    cash_one_lot_block_count = int(normalized_counts.get("cash_one_lot_block_count", 0) or 0)
    cash_liquidity_block_count = cash_block_count + cash_one_lot_block_count
    block_reason_breakdown = _block_reason_breakdown(blocked, raw_buy=raw_buy)
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
        "repeat_raw_buy_intent_count": repeat_raw_buy_intent_count,
        "repeat_raw_buy_intent_ratio": repeat_raw_buy_intent_ratio,
        "raw_sell_signal_count": raw_sell,
        "account_feasible_buy_signal_count": account_feasible_buy,
        "user_visible_buy_recommendation_count": user_visible_buy_recommendations,
        "user_visible_blocked_buy_count": user_visible_blocked_buy,
        "pending_buy_intent_count": pending_buy_intents,
        "executable_buy_count": executable_buy,
        "executable_new_position_buy_count": executable_new,
        "executable_add_buy_count": executable_add,
        "executable_sell_count": executable_sell,
        "blocked_buy_count": blocked_buy,
        "blocked_sell_count": blocked_sell,
        "full_portfolio_raw_buy_intent_count": full_portfolio_raw_buy_intent_count,
        "full_portfolio_raw_buy_intent_ratio": full_portfolio_raw_buy_intent_ratio,
        "new_position_raw_intent_count": new_position_raw_intent_count,
        "add_position_raw_intent_count": add_position_raw_intent_count,
        "blocker_counts": blocker_counts,
        **normalized_counts,
        "executable_raw_buy_ratio": buy_ratio,
        "executable_unique_raw_intent_ratio": executable_unique_raw_intent_ratio,
        "executable_account_feasible_buy_ratio": feasible_ratio,
        "executable_raw_sell_ratio": sell_ratio,
        "max_positions_block_ratio": _ratio(max_positions_block_count, raw_buy),
        "cash_block_ratio": _ratio(cash_block_count, raw_buy),
        "cash_liquidity_block_count": cash_liquidity_block_count,
        "cash_liquidity_block_ratio": _ratio(cash_liquidity_block_count, raw_buy),
        "cash_insufficient_for_one_lot_ratio": _ratio(cash_one_lot_block_count, raw_buy),
        "lot_size_accumulation_required_ratio": _ratio(normalized_counts.get("lot_size_accumulation_required_count", 0), raw_buy),
        "price_too_high_for_account_lot_ratio": _ratio(normalized_counts.get("price_too_high_for_account_lot_count", 0), raw_buy),
        "average_cash_ratio": average_cash_ratio,
        "average_exposure": average_exposure,
        "max_exposure": max_exposure,
        "turnover": turnover,
        "metric_denominators": {
            "executable_raw_buy_ratio": "executable_buy_count / raw_buy_signal_count",
            "executable_unique_raw_intent_ratio": "executable_buy_count / unique_raw_buy_intent_count",
            "executable_account_feasible_buy_ratio": "executable_buy_count / account_feasible_buy_signal_count",
            "repeat_raw_buy_intent_ratio": "repeat_raw_buy_intent_count / raw_buy_signal_count",
            "full_portfolio_raw_buy_intent_ratio": "full_portfolio_raw_buy_intent_count / raw_buy_signal_count",
            "max_positions_block_ratio": "max_positions_block_count / raw_buy_signal_count",
            "cash_block_ratio": "cash_block_count / raw_buy_signal_count; excludes CASH_INSUFFICIENT_FOR_ONE_LOT",
            "cash_liquidity_block_ratio": "(cash_block_count + cash_insufficient_for_one_lot_count) / raw_buy_signal_count",
            "block_reason_breakdown.count_pct_of_raw": "reason_code count / raw_buy_signal_count",
            "block_reason_breakdown.count_pct_of_blocked": "reason_code count / total blocked_signals rows",
        },
        "block_reason_breakdown": block_reason_breakdown,
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
        f"- repeat_raw_buy_intent_count: {payload['repeat_raw_buy_intent_count']}",
        f"- repeat_raw_buy_intent_ratio: {payload['repeat_raw_buy_intent_ratio']}",
        f"- repeated_blocked_buy_signal_count: {payload['repeated_blocked_buy_signal_count']}",
        f"- account_feasible_buy_signal_count: {payload['account_feasible_buy_signal_count']}",
        f"- user_visible_buy_recommendation_count: {payload['user_visible_buy_recommendation_count']}",
        f"- user_visible_blocked_buy_count: {payload['user_visible_blocked_buy_count']}",
        f"- pending_buy_intent_count: {payload['pending_buy_intent_count']}",
        f"- raw_sell_signal_count: {payload['raw_sell_signal_count']}",
        f"- executable_buy_count: {payload['executable_buy_count']}",
        f"- executable_sell_count: {payload['executable_sell_count']}",
        f"- executable_raw_buy_ratio: {payload['executable_raw_buy_ratio']}",
        f"- executable_unique_raw_intent_ratio: {payload['executable_unique_raw_intent_ratio']}",
        f"- executable_account_feasible_buy_ratio: {payload['executable_account_feasible_buy_ratio']}",
        f"- full_portfolio_raw_buy_intent_count: {payload['full_portfolio_raw_buy_intent_count']}",
        f"- full_portfolio_raw_buy_intent_ratio: {payload['full_portfolio_raw_buy_intent_ratio']}",
        f"- new_position_raw_intent_count: {payload['new_position_raw_intent_count']}",
        f"- add_position_raw_intent_count: {payload['add_position_raw_intent_count']}",
        f"- executable_new_position_buy_count: {payload['executable_new_position_buy_count']}",
        f"- executable_add_buy_count: {payload['executable_add_buy_count']}",
        f"- average_cash_ratio: {payload['average_cash_ratio']:.4f}",
        f"- average_exposure: {payload['average_exposure']:.4f}",
        f"- max_exposure: {payload['max_exposure']:.4f}",
        f"- turnover: {payload['turnover']:.2f}",
        "",
        "## denominator notes",
        "",
    ]
    for key, value in payload["metric_denominators"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(
        [
            "",
            "## blocker ratios",
            "",
            f"- max_positions_block_count: {payload['max_positions_block_count']}",
            f"- max_positions_block_ratio: {payload['max_positions_block_ratio']}",
            f"- price_too_high_for_account_lot_count: {payload['price_too_high_for_account_lot_count']}",
            f"- price_too_high_for_account_lot_ratio: {payload['price_too_high_for_account_lot_ratio']}",
            f"- cash_insufficient_for_one_lot_count: {payload['cash_one_lot_block_count']}",
            f"- cash_insufficient_for_one_lot_ratio: {payload['cash_insufficient_for_one_lot_ratio']}",
            f"- lot_size_accumulation_required_count: {payload['lot_size_accumulation_required_count']}",
            f"- lot_size_accumulation_required_ratio: {payload['lot_size_accumulation_required_ratio']}",
            f"- cash_block_count: {payload['cash_block_count']}",
            f"- cash_block_ratio: {payload['cash_block_ratio']} (direct CASH_INSUFFICIENT only)",
            f"- cash_liquidity_block_count: {payload['cash_liquidity_block_count']}",
            f"- cash_liquidity_block_ratio: {payload['cash_liquidity_block_ratio']} (cash + one-lot cash blockers)",
        ]
    )
    lines.extend(
        [
            "",
            "## block reason breakdown",
            "",
            "| reason_code | count | pct_raw | pct_blocked | unique_symbols | trade_dates | dominant_bucket | examples | description |",
            "|---|---:|---:|---:|---:|---:|---|---|---|",
        ]
    )
    for row in payload["block_reason_breakdown"]:
        examples = ",".join(row.get("example_symbols", []))
        pct_raw = row["count_pct_of_raw"]
        pct_blocked = row["count_pct_of_blocked"]
        lines.append(
            f"| {row['reason_code']} | {row['count']} | {pct_raw} | {pct_blocked} | "
            f"{row['affected_unique_symbols']} | {row['affected_trade_dates']} | {row['dominant_bucket']} | {examples} | {row['description_zh']} |"
        )
    lines.extend(
        [
        "",
        "## blocker_counts",
        "",
        ]
    )
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
