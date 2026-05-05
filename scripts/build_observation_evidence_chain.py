#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.audit_data_freshness import build_audit_data_freshness_report
from scripts.audit_universe_integrity import build_universe_integrity_report
from scripts.report_metadata import metadata_header, status_from_children, write_json
from src.utils.config import load_yaml, resolve_path


JSON_NAME = "evidence_chain.json"
MD_NAME = "evidence_chain.md"


def _read_csv(path_like: str | Path) -> pd.DataFrame:
    path = resolve_path(path_like)
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _target_rows(frame: pd.DataFrame, target_trade_date: str) -> pd.DataFrame:
    if frame.empty or "date" not in frame.columns:
        return pd.DataFrame()
    return frame[frame["date"].astype(str) == str(target_trade_date)].copy()


def _load_target_features(target_trade_date: str) -> pd.DataFrame:
    candidates = [
        resolve_path("data/features/latest_feature_snapshot.parquet"),
        resolve_path("data/features/daily_features") / f"{pd.Timestamp(target_trade_date).year}.parquet",
    ]
    frames: list[pd.DataFrame] = []
    for path in candidates:
        if not path.exists():
            continue
        try:
            frame = pd.read_parquet(path)
        except Exception:
            continue
        if "date" in frame.columns:
            frame = frame[frame["date"].astype(str) == target_trade_date].copy()
        if not frame.empty:
            frames.append(frame)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True, sort=False).drop_duplicates(subset=["symbol"], keep="last")


def _field(value: object, source: str, asof: str, effective_date: str = "", used_by_strategy: bool = True) -> dict[str, Any]:
    if pd.isna(value) if value is not None else True:
        value = None
    return {
        "value": value,
        "source": source,
        "asof": asof,
        "effective_date": effective_date or None,
        "used_by_strategy": bool(used_by_strategy),
    }


def _feature_lookup(features: pd.DataFrame) -> dict[str, dict[str, Any]]:
    if features.empty or "symbol" not in features.columns:
        return {}
    return {str(row.get("symbol")): row for row in features.to_dict(orient="records")}


def _constituents(universe_report: dict[str, Any], target_trade_date: str) -> list[dict[str, Any]]:
    features = _feature_lookup(_load_target_features(target_trade_date))
    output: list[dict[str, Any]] = []
    for item in universe_report.get("constituents", []):
        symbol = str(item.get("symbol") or item.get("code") or "")
        row = features.get(symbol, {})
        close = row.get("close")
        ma120 = row.get("ma120")
        deviation = None
        try:
            if close is not None and ma120 not in {None, 0} and not pd.isna(ma120):
                deviation = float(close) / float(ma120) - 1.0
        except (TypeError, ValueError):
            deviation = None
        output.append(
            {
                "symbol": symbol,
                "code": symbol,
                "name": item.get("name"),
                "industry": item.get("industry"),
                "bucket": item.get("bucket"),
                "selected": True,
                "hard_filter_results": {
                    "failed_filters": item.get("failed_filters", []),
                    "missing_fields": item.get("missing_fields", []),
                },
                "market_cap_billion": _field(item.get("market_cap_billion"), item.get("data_path", "config/universe.yml"), item.get("data_asof") or target_trade_date),
                "pe": _field(row.get("pe_ttm", item.get("pe")), "data/features/daily_features", target_trade_date, row.get("effective_date")),
                "pb": _field(row.get("pb", item.get("pb")), "data/features/daily_features", target_trade_date, row.get("effective_date")),
                "dividend_yield": _field(row.get("dv_ttm", item.get("dividend_yield")), "data/features/daily_features", target_trade_date, row.get("effective_date")),
                "valuation_percentile": _field(row.get("stock_q_blended"), "data/features/daily_features", target_trade_date),
                "industry_percentile": _field(row.get("industry_q_blended"), "data/features/daily_features", target_trade_date),
                "industry_rank": _field(item.get("industry_rank"), item.get("data_path", "config/universe.yml"), item.get("data_asof") or target_trade_date),
                "ma120": _field(ma120, "data/features/daily_features", target_trade_date),
                "close": _field(close, "data/features/daily_features", target_trade_date),
                "deviation_from_ma120": _field(deviation, "data/features/daily_features", target_trade_date),
                "selected_reason": item.get("selected_reason"),
                "exclusion_reason": None,
                "retained": item.get("retained"),
                "manual_override": item.get("manual_override"),
            }
        )
    return output


def _action_from_trade(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "symbol": row.get("ts_code") or row.get("symbol"),
        "code": row.get("ts_code") or row.get("symbol"),
        "action": row.get("action"),
        "raw_signal": row.get("signal_level") or row.get("action"),
        "final_action": row.get("action"),
        "target_weight": row.get("target_weight"),
        "current_weight": row.get("weight_before"),
        "target_amount": row.get("amount"),
        "executable_amount": row.get("amount"),
        "blocked": False,
        "blockers": [],
        "rule_path": "hard_filter -> bucket -> valuation -> market_state -> grid -> account_constraints",
        "triggered_rules": [value for value in [row.get("entry_reason"), row.get("exit_reason"), row.get("execution_reason_code")] if value],
        "suppressed_rules": [],
        "data_sources": ["reports/backtest/combined_v2_trades_detailed.csv", "data/features/daily_features"],
    }


def _action_from_blocked(row: dict[str, Any]) -> dict[str, Any]:
    reason = row.get("reason_code") or row.get("blocked_reason") or "UNKNOWN"
    return {
        "symbol": row.get("ts_code") or row.get("symbol"),
        "code": row.get("ts_code") or row.get("symbol"),
        "action": row.get("intended_action"),
        "raw_signal": row.get("intended_signal_level") or row.get("intended_action"),
        "final_action": "BLOCKED",
        "target_weight": row.get("intended_target_weight"),
        "current_weight": row.get("current_weight"),
        "target_amount": None,
        "executable_amount": 0,
        "blocked": True,
        "blockers": [reason],
        "rule_path": "hard_filter -> bucket -> valuation -> market_state -> grid -> account_constraints",
        "triggered_rules": [],
        "suppressed_rules": [row.get("reason_detail") or reason],
        "data_sources": ["reports/backtest/combined_v2_blocked_signals.csv", "data/features/daily_features"],
    }


def build_observation_evidence_chain(
    requested_date: str,
    target_trade_date: str | None = None,
    *,
    output_dir: str | Path | None = None,
    universe_report: dict[str, Any] | None = None,
    freshness_report: dict[str, Any] | None = None,
    write_report: bool = True,
) -> dict[str, Any]:
    freshness = freshness_report or build_audit_data_freshness_report(requested_date, write_report=False)
    target = target_trade_date or str(freshness.get("target_trade_date") or freshness.get("target_trading_date") or requested_date)
    universe = universe_report or build_universe_integrity_report(write_report=False)
    trades = _target_rows(_read_csv("reports/backtest/combined_v2_trades_detailed.csv"), target)
    blocked = _target_rows(_read_csv("reports/backtest/combined_v2_blocked_signals.csv"), target)
    actions = [_action_from_trade(row) for row in trades.to_dict(orient="records")]
    actions.extend(_action_from_blocked(row) for row in blocked.to_dict(orient="records"))
    universe_status = str(universe.get("status", "FAIL"))
    freshness_status = str(freshness.get("status", "FAIL"))
    status = status_from_children([universe_status, freshness_status])
    payload = {
        **metadata_header(requested_date=requested_date, target_trade_date=target),
        "status": status,
        "report_date": requested_date,
        "requested_date": requested_date,
        "target_trade_date": target,
        "target_trading_date": target,
        "universe_status": universe_status,
        "data_freshness_status": freshness_status,
        "actions": actions,
        "constituents": _constituents(universe, target),
        "action_allowed": status != "FAIL",
        "manual_review_required": True,
        "auto_trading_approved": False,
        "broker_integration_enabled": False,
        "llm_decision_allowed": False,
    }
    if write_report:
        base = resolve_path(output_dir or Path("reports/observation") / requested_date)
        base.mkdir(parents=True, exist_ok=True)
        write_json(base / JSON_NAME, payload)
        _write_md(payload, base / MD_NAME)
    return payload


def _write_md(payload: dict[str, Any], path_like: str | Path) -> None:
    path = resolve_path(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# observation evidence chain",
        "",
        f"- status: {payload['status']}",
        f"- report_date: {payload['report_date']}",
        f"- requested_date: {payload['requested_date']}",
        f"- target_trade_date: {payload['target_trade_date']}",
        f"- git_commit: {payload['git_commit']}",
        f"- config_hash: {payload['config_hash']}",
        f"- data_hash: {payload['data_hash']}",
        f"- universe_status: {payload['universe_status']}",
        f"- data_freshness_status: {payload['data_freshness_status']}",
        f"- action_count: {len(payload['actions'])}",
        f"- constituent_count: {len(payload['constituents'])}",
        "- auto_trading_approved: false",
        "",
        "## Actions",
        "",
    ]
    if payload["actions"]:
        for item in payload["actions"]:
            lines.append(
                f"- {item['symbol']} | raw={item['raw_signal']} | final={item['final_action']} | blocked={str(item['blocked']).lower()} | blockers={','.join(item['blockers']) if item['blockers'] else 'none'}"
            )
    else:
        lines.append("- 无")
    lines.extend(["", "## Constituents", ""])
    for item in payload["constituents"]:
        failures = ",".join(item.get("hard_filter_results", {}).get("failed_filters", [])) or "none"
        lines.append(f"- {item['symbol']} {item.get('name') or ''} | {item.get('industry') or ''} | {item.get('bucket') or ''} | failed_filters={failures}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build per-constituent and per-action observation evidence chain.")
    parser.add_argument("--requested-date", "--as-of-date", dest="requested_date", required=True)
    parser.add_argument("--target-trade-date", default="")
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--no-write-report", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_observation_evidence_chain(
        args.requested_date,
        target_trade_date=args.target_trade_date or None,
        output_dir=args.output_dir or None,
        write_report=not args.no_write_report,
    )
    return 1 if payload["status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
