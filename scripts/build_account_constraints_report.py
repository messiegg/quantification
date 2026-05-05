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

from scripts.report_metadata import metadata_header, status_from_children, write_json
from src.utils.config import resolve_path


JSON_PATH = "reports/backtest/account_constraints_report.json"
MD_PATH = "reports/backtest/account_constraints_report.md"


BLOCKER_COLUMNS = {
    "MIN_TRADE_AMOUNT": "min_trade_amount_block_count",
    "CASH_INSUFFICIENT": "cash_block_count",
    "TOTAL_EXPOSURE_LIMIT": "exposure_block_count",
    "SINGLE_NAME_LIMIT": "exposure_block_count",
    "LOT_SIZE_ZERO": "lot_size_block_count",
    "DAILY_POSITION_LIMIT": "daily_limit_block_count",
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


def build_account_constraints_report(
    *,
    signal_funnel_path: str = "reports/backtest/combined_v2_signal_funnel.csv",
    blocked_signals_path: str = "reports/backtest/combined_v2_blocked_signals.csv",
    trades_path: str = "reports/backtest/combined_v2_trades_detailed.csv",
    write_report: bool = True,
) -> dict[str, Any]:
    funnel = _read_csv(signal_funnel_path)
    blocked = _read_csv(blocked_signals_path)
    trades = _read_csv(trades_path)
    raw_buy = _sum(funnel, "raw_buy_signal_count")
    raw_sell = _sum(funnel, "raw_sell_signal_count")
    executable_buy = _sum(funnel, "executable_buy_count")
    executable_sell = _sum(funnel, "executable_sell_count")
    blocker_counts = (
        blocked["reason_code"].astype(str).value_counts().to_dict()
        if not blocked.empty and "reason_code" in blocked.columns
        else {}
    )
    normalized_counts = {value: 0 for value in BLOCKER_COLUMNS.values()}
    for reason, count in blocker_counts.items():
        target = BLOCKER_COLUMNS.get(str(reason))
        if target:
            normalized_counts[target] = int(normalized_counts.get(target, 0)) + int(count)
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
    if raw_buy and min_trade_blocks / raw_buy > 0.5:
        warnings.append(
            {
                "code": "MIN_TRADE_AMOUNT_DOMINATES_EXECUTION",
                "message": "min_trade_amount dominates execution",
                "expected": "<=50% raw buy signals",
                "actual": min_trade_blocks / raw_buy,
            }
        )
    status = status_from_children(["WARN" if warnings else "PASS"])
    payload = {
        **metadata_header(),
        "status": status,
        "raw_buy_signal_count": raw_buy,
        "raw_sell_signal_count": raw_sell,
        "executable_buy_count": executable_buy,
        "executable_sell_count": executable_sell,
        "blocked_buy_count": blocked_buy,
        "blocked_sell_count": blocked_sell,
        "blocker_counts": blocker_counts,
        **normalized_counts,
        "executable_raw_buy_ratio": buy_ratio,
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
        write_json(JSON_PATH, payload)
        _write_md(payload, MD_PATH)
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
        f"- raw_buy_signal_count: {payload['raw_buy_signal_count']}",
        f"- raw_sell_signal_count: {payload['raw_sell_signal_count']}",
        f"- executable_buy_count: {payload['executable_buy_count']}",
        f"- executable_sell_count: {payload['executable_sell_count']}",
        f"- executable_raw_buy_ratio: {payload['executable_raw_buy_ratio']}",
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
