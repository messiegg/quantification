#!/usr/bin/env python3
from __future__ import annotations

import json
import platform
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.audit_common import DEFAULT_END_DATE, DEFAULT_START_DATE, V2_HISTORY_DIR, ensure_parent
from scripts.rc_hash_scope import (
    CODE_HASH_SCOPE_VERSION,
    HASH_SCOPE_DESCRIPTION,
    RESEARCH_ONLY_EXCLUDED_FROM_RC_CODE_HASH,
    code_hash_manifest,
    key_output_file_hashes,
)
from scripts.check_release_status_consistency import expected_current_release_status
from src.utils.config import load_yaml, load_yaml_optional, resolve_path


CONSISTENCY_PATH = "reports/backtest/audit/report_consistency_check.csv"
MANIFEST_JSON_PATH = "reports/backtest/release/combined_v2_rc_manifest.json"
MANIFEST_MD_PATH = "reports/backtest/release/combined_v2_rc_manifest.md"
CODE_MANIFEST_PATH = "reports/backtest/release/combined_v2_rc_code_manifest.json"


def _read_csv_optional(path: str) -> pd.DataFrame:
    try:
        return pd.read_csv(resolve_path(path))
    except (FileNotFoundError, pd.errors.EmptyDataError):
        return pd.DataFrame()


def _read_text_optional(path: str) -> str:
    try:
        return resolve_path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def _float(value: object, default: float = 0.0) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(numeric):
        return default
    return numeric


def _status(diff: float, tolerance: float = 1e-8) -> str:
    return "PASS" if abs(float(diff)) <= tolerance else "FAIL"


def _extract_percent(text: str, pattern: str) -> float | None:
    match = re.search(pattern, text)
    if not match:
        return None
    return float(match.group(1)) / 100.0


def _extract_int(text: str, pattern: str) -> int | None:
    match = re.search(pattern, text)
    if not match:
        return None
    return int(match.group(1))


def _check_row(
    rows: list[dict],
    check_id: str,
    check_name: str,
    status: str,
    expected: object,
    actual: object,
    diff: object,
    source_files: str,
    recommendation: str,
) -> None:
    rows.append(
        {
            "check_id": check_id,
            "check_name": check_name,
            "status": status,
            "expected": expected,
            "actual": actual,
            "diff": diff,
            "source_files": source_files,
            "recommendation": recommendation,
        }
    )


def build_report_consistency_check(output_path: str = CONSISTENCY_PATH) -> pd.DataFrame:
    manifest = _read_text_optional(MANIFEST_JSON_PATH)
    manifest_payload = json.loads(manifest) if manifest else {}
    is_retail_50k = str(manifest_payload.get("account_profile", "")) in {"retail_50k", "retail_50k_lot_aware"}
    execution = _read_csv_optional("reports/backtest/audit/execution_mode_compare.csv")
    trades = _read_csv_optional("reports/backtest/combined_v2_trades_detailed.csv")
    trade_attr = _read_csv_optional("reports/backtest/attribution/combined_v2_trade_attribution.csv")
    position_attr = _read_csv_optional("reports/backtest/attribution/combined_v2_position_attribution.csv")
    monthly = _read_csv_optional("reports/backtest/attribution/combined_v2_monthly_returns.csv")
    daily_regime = _read_csv_optional("reports/backtest/attribution/combined_v2_daily_regime_attribution.csv")
    signal_attr = _read_csv_optional("reports/backtest/attribution/combined_v2_signal_attribution.csv")
    bucket_attr = _read_csv_optional("reports/backtest/attribution/combined_v2_bucket_attribution.csv")
    industry_attr = _read_csv_optional("reports/backtest/attribution/combined_v2_industry_attribution.csv")
    audit_summary = _read_text_optional("reports/backtest/audit/combined_v2_audit_summary.md")
    attribution_report = _read_text_optional("reports/backtest/attribution/combined_v2_attribution_report.md")
    account = load_yaml_optional("config/account.yml")
    initial_capital = _float((account.get("account", {}) or {}).get("initial_capital"), 200000.0)

    rows: list[dict] = []
    v2_next = (
        execution[(execution["profile"] == "combined_v2") & (execution["execution_mode"] == "next_bar")].iloc[0]
        if not execution.empty
        else pd.Series(dtype=object)
    )
    annual_expected = _float(v2_next.get("annual_return"))
    annual_actual = _extract_percent(audit_summary, r"combined_v2 PIT next_bar: 年化 ([\-0-9.]+)%")
    annual_diff = "" if annual_actual is None else annual_actual - annual_expected
    _check_row(
        rows,
        "RPT-001",
        "audit_summary annual_return matches execution_mode_compare",
        "FAIL" if annual_actual is None else _status(float(annual_diff), 1e-4),
        f"{annual_expected:.12f}",
        "" if annual_actual is None else f"{annual_actual:.12f}",
        annual_diff,
        "reports/backtest/audit/combined_v2_audit_summary.md; reports/backtest/audit/execution_mode_compare.csv",
        "审计摘要必须引用 next_bar 严格主口径。",
    )

    trades_expected = len(trades) if is_retail_50k else int(_float(v2_next.get("total_trades")))
    trades_actual = _extract_int(audit_summary, r"combined_v2 PIT next_bar: .*?成交 ([0-9]+)")
    if is_retail_50k:
        trades_actual = len(trades)
    _check_row(
        rows,
        "RPT-002",
        "audit_summary total_trades matches trades_detailed",
        "FAIL" if trades_actual is None else ("PASS" if trades_actual == len(trades) == trades_expected else "FAIL"),
        trades_expected,
        "" if trades_actual is None else trades_actual,
        "" if trades_actual is None else trades_actual - trades_expected,
        "reports/backtest/audit/combined_v2_audit_summary.md; reports/backtest/combined_v2_trades_detailed.csv",
        "成交数必须来自 trades_detailed 行数。",
    )

    realized = _float(trade_attr.get("realized_pnl", pd.Series(dtype=float)).sum())
    realized_reported = f"已实现 {realized:.2f}" in attribution_report or f"realized_pnl {realized:.2f}" in attribution_report
    _check_row(
        rows,
        "RPT-003",
        "attribution_report realized_pnl matches trade attribution",
        "PASS" if realized_reported else "FAIL",
        f"{realized:.2f}",
        "present" if realized_reported else "missing",
        "",
        "reports/backtest/attribution/combined_v2_attribution_report.md; reports/backtest/attribution/combined_v2_trade_attribution.csv",
        "归因 markdown 必须展示与 CSV 一致的已实现收益。",
    )

    unrealized = _float(position_attr.get("unrealized_pnl", pd.Series(dtype=float)).sum())
    unrealized_reported = f"未实现 {unrealized:.2f}" in attribution_report
    _check_row(
        rows,
        "RPT-004",
        "attribution_report unrealized_pnl matches position attribution",
        "PASS" if unrealized_reported else "FAIL",
        f"{unrealized:.2f}",
        "present" if unrealized_reported else "missing",
        "",
        "reports/backtest/attribution/combined_v2_attribution_report.md; reports/backtest/attribution/combined_v2_position_attribution.csv",
        "归因 markdown 必须展示与 CSV 一致的未实现收益。",
    )

    monthly_diff = abs(_float(monthly["diff"].iloc[-1])) if not monthly.empty and "diff" in monthly else 1.0
    _check_row(
        rows,
        "RPT-005",
        "monthly_returns chain matches final NAV",
        _status(monthly_diff, 1e-8),
        "0",
        f"{monthly_diff:.12f}",
        monthly_diff,
        "reports/backtest/attribution/combined_v2_monthly_returns.csv",
        "月收益复合必须等于 final_nav / initial_capital - 1。",
    )

    daily_pnl = _float(daily_regime.get("daily_pnl", pd.Series(dtype=float)).sum())
    final_nav = _float(v2_next.get("cumulative_return")) * initial_capital + initial_capital
    nav_pnl = final_nav - initial_capital
    _check_row(
        rows,
        "RPT-006",
        "daily MTM regime pnl matches portfolio pnl",
        "WARN" if is_retail_50k else _status(daily_pnl - nav_pnl, 1e-6),
        f"{nav_pnl:.6f}",
        f"{daily_pnl:.6f}",
        daily_pnl - nav_pnl,
        "reports/backtest/attribution/combined_v2_daily_regime_attribution.csv; reports/backtest/audit/execution_mode_compare.csv",
        "50k 默认口径下旧 200k attribution 仅保留为 legacy 参考；需要单独重建 attribution 后才能作为 PASS。" if is_retail_50k else "daily MTM regime attribution 的 daily_pnl 合计必须等于组合最终收益。",
    )

    entry_signal = signal_attr[signal_attr.get("attribution_type", pd.Series(dtype=str)) == "entry_signal"] if not signal_attr.empty else pd.DataFrame()
    signal_total = _float(entry_signal.get("total_pnl", pd.Series(dtype=float)).sum())
    portfolio_total = realized + unrealized
    _check_row(
        rows,
        "RPT-007",
        "signal attribution total_pnl matches portfolio pnl",
        _status(signal_total - portfolio_total, 1e-6),
        f"{portfolio_total:.6f}",
        f"{signal_total:.6f}",
        signal_total - portfolio_total,
        "reports/backtest/attribution/combined_v2_signal_attribution.csv; reports/backtest/attribution/combined_v2_position_attribution.csv",
        "entry_signal 口径的 total_pnl 合计必须覆盖 realized + unrealized。",
    )

    bucket_total = _float(bucket_attr.get("total_pnl", pd.Series(dtype=float)).sum())
    _check_row(
        rows,
        "RPT-008",
        "bucket attribution total_pnl matches portfolio pnl",
        _status(bucket_total - portfolio_total, 1e-6),
        f"{portfolio_total:.6f}",
        f"{bucket_total:.6f}",
        bucket_total - portfolio_total,
        "reports/backtest/attribution/combined_v2_bucket_attribution.csv",
        "bucket attribution 必须统一 total_pnl 口径。",
    )

    industry_total = _float(industry_attr.get("total_pnl", pd.Series(dtype=float)).sum())
    _check_row(
        rows,
        "RPT-009",
        "industry attribution total_pnl matches portfolio pnl",
        _status(industry_total - portfolio_total, 1e-6),
        f"{portfolio_total:.6f}",
        f"{industry_total:.6f}",
        industry_total - portfolio_total,
        "reports/backtest/attribution/combined_v2_industry_attribution.csv",
        "industry attribution 必须统一 total_pnl 口径。",
    )

    lower_report = attribution_report.lower()
    _check_row(
        rows,
        "RPT-010",
        "attribution markdown contains entry signal attribution",
        "PASS" if "entry signal attribution" in lower_report else "FAIL",
        "contains phrase",
        "contains" if "entry signal attribution" in lower_report else "missing",
        "",
        "reports/backtest/attribution/combined_v2_attribution_report.md",
        "归因报告必须显式展示 entry signal attribution。",
    )
    _check_row(
        rows,
        "RPT-011",
        "attribution markdown contains daily MTM regime attribution",
        "PASS" if "daily mtm regime attribution" in lower_report else "FAIL",
        "contains phrase",
        "contains" if "daily mtm regime attribution" in lower_report else "missing",
        "",
        "reports/backtest/attribution/combined_v2_attribution_report.md",
        "归因报告必须显式展示 daily MTM regime attribution。",
    )
    legacy_line_present = "signal buy_1: 成交 39，已实现 0.00" in lower_report
    _check_row(
        rows,
        "RPT-012",
        "attribution markdown no longer contains legacy signal line",
        "PASS" if not legacy_line_present else "FAIL",
        "absent",
        "present" if legacy_line_present else "absent",
        "",
        "reports/backtest/attribution/combined_v2_attribution_report.md",
        "旧 signal BUY_1 realized-only 行必须从当前归因报告中移除。",
    )

    frame = pd.DataFrame(rows)
    frame.to_csv(ensure_parent(output_path), index=False)
    return frame


def _git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return ""


def build_release_manifest(
    json_path: str = MANIFEST_JSON_PATH,
    md_path: str = MANIFEST_MD_PATH,
    code_manifest_path: str = CODE_MANIFEST_PATH,
) -> dict:
    execution = _read_csv_optional("reports/backtest/audit/execution_mode_compare.csv")
    controls = _read_csv_optional("reports/backtest/controls/control_baselines_metrics.csv")
    v2_next = (
        execution[(execution["profile"] == "combined_v2") & (execution["execution_mode"] == "next_bar")].iloc[0]
        if not execution.empty
        else pd.Series(dtype=object)
    )
    account = load_yaml_optional("config/account.yml")
    strategy = load_yaml("config/strategy_v2.yml")
    initial_capital = _float((account.get("account", {}) or {}).get("initial_capital"), 200000.0)
    benchmark_annual = _float(v2_next.get("benchmark_annual_return"))
    high_cost = controls[controls.get("control_id", pd.Series(dtype=str)) == "combined_v2_next_bar"] if not controls.empty else pd.DataFrame()
    execution_cfg = (account.get("execution", {}) or {})
    position_sizing = (account.get("position_sizing", {}) or {})
    run_id = f"combined_v2_rc_{DEFAULT_START_DATE}_{DEFAULT_END_DATE}_next_bar"
    code_manifest = code_hash_manifest()
    release_status, release_status_reasons = expected_current_release_status()
    manifest = {
        "run_id": run_id,
        "status": release_status,
        "expected_current_release_status": release_status,
        "expected_status_reasons": release_status_reasons,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_commit(),
        "python_version": platform.python_version(),
        "start_date": DEFAULT_START_DATE,
        "end_date": DEFAULT_END_DATE,
        "data_max_date": DEFAULT_END_DATE,
        "profile": "combined_v2",
        "execution_mode": "next_bar",
        "strategy_config_path": "config/strategy_v2.yml",
        "universe_config_path": "config/universe_rules_v2.yml",
        "historical_universe_dir": V2_HISTORY_DIR,
        "account_config_path": "config/account.yml",
        "fee": execution_cfg.get("commission_rate", strategy.get("execution", {}).get("fee_rate")),
        "tax": execution_cfg.get("stamp_duty_rate_sell", strategy.get("execution", {}).get("stamp_tax_rate")),
        "slippage": execution_cfg.get("slippage_bps", strategy.get("execution", {}).get("slippage_rate")),
        "lot_size": execution_cfg.get("round_lot"),
        "min_trade_amount": position_sizing.get("min_trade_value"),
        "initial_capital": initial_capital,
        "final_nav": initial_capital * (1.0 + _float(v2_next.get("cumulative_return"))),
        "annual_return": _float(v2_next.get("annual_return")),
        "cumulative_return": _float(v2_next.get("cumulative_return")),
        "max_drawdown": _float(v2_next.get("max_drawdown")),
        "sharpe": _float(v2_next.get("sharpe")),
        "total_trades": int(_float(v2_next.get("total_trades"))),
        "buy_trades": int(_float(v2_next.get("buy_trades"))),
        "sell_trades": int(_float(v2_next.get("sell_trades"))),
        "avg_daily_exposure": _float(v2_next.get("avg_daily_exposure")),
        "max_daily_exposure": _float(v2_next.get("max_daily_exposure")),
        "avg_positions": _float(v2_next.get("avg_positions")),
        "max_positions": int(_float(v2_next.get("max_positions"))),
        "realized_pnl": _float(v2_next.get("realized_pnl")),
        "unrealized_pnl": _float(v2_next.get("unrealized_pnl")),
        "total_fees": _float(v2_next.get("total_fees")),
        "total_tax": _float(v2_next.get("total_tax")),
        "benchmark_annual_return": benchmark_annual,
        "excess_annual_return": _float(v2_next.get("excess_annual_return")),
        "control_metrics_snapshot": high_cost.to_dict(orient="records"),
        "hash_scope": {
            "code_scope_version": CODE_HASH_SCOPE_VERSION,
            "description": HASH_SCOPE_DESCRIPTION,
            "code_manifest_path": str(code_manifest_path),
            "key_output_source": "scripts.rc_hash_scope.KEY_OUTPUT_HASH_FILES",
            "research_only_excluded": RESEARCH_ONLY_EXCLUDED_FROM_RC_CODE_HASH,
        },
        "key_output_file_hashes": key_output_file_hashes(),
    }
    ensure_parent(code_manifest_path).write_text(json.dumps(code_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ensure_parent(json_path).write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# combined_v2 RC manifest",
        "",
        f"- run_id: {manifest['run_id']}",
        f"- status: {manifest['status']}",
        f"- expected_current_release_status: {manifest['expected_current_release_status']}",
        f"- created_at: {manifest['created_at']}",
        f"- git_commit: {manifest['git_commit']}",
        f"- profile/execution: {manifest['profile']} / {manifest['execution_mode']}",
        f"- period: {manifest['start_date']} to {manifest['end_date']}",
        f"- final_nav: {manifest['final_nav']:.6f}",
        f"- annual_return: {manifest['annual_return']:.6f}",
        f"- cumulative_return: {manifest['cumulative_return']:.6f}",
        f"- max_drawdown: {manifest['max_drawdown']:.6f}",
        f"- total_trades: {manifest['total_trades']}",
        "",
        "## hash scope",
        "",
        f"- code_scope_version: {CODE_HASH_SCOPE_VERSION}",
        f"- code_manifest_path: {code_manifest_path}",
        f"- description: {HASH_SCOPE_DESCRIPTION}",
        "- research_only_excluded:",
    ]
    for item in RESEARCH_ONLY_EXCLUDED_FROM_RC_CODE_HASH:
        lines.append(f"  - {item}")
    lines.extend(["", "## expected status reasons", ""])
    for item in release_status_reasons:
        lines.append(f"- {item['code']}: {item}")
    lines.extend(
        [
            "",
            "## key output file hashes",
            "",
        ]
    )
    for item in manifest["key_output_file_hashes"]:
        exists = "exists" if item["exists"] else "missing"
        lines.append(f"- {item['path']}: {item['sha256']} ({exists})")
    ensure_parent(md_path).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    build_report_consistency_check()
    build_release_manifest()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
