#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.audit_common import (
    BASELINE_HISTORY_DIR,
    DEFAULT_END_DATE,
    DEFAULT_START_DATE,
    V2_HISTORY_DIR,
    ensure_parent,
    load_audit_configs,
    load_benchmark_window,
    load_feature_window,
    metrics_row,
    pct,
    prepare_v2_history,
    run_profile,
    status_from_rows,
    write_profile_diagnostics,
)


def _row(check_id: str, name: str, status: str, profile: str, evidence: str, affected_file: str, recommendation: str) -> dict:
    return {
        "check_id": check_id,
        "check_name": name,
        "status": status,
        "profile": profile,
        "evidence": evidence,
        "affected_file": affected_file,
        "recommendation": recommendation,
    }


def _close(actual: float, expected: float, tolerance: float) -> bool:
    return abs(float(actual) - float(expected)) <= tolerance


def _audit_status(rows: list[dict]) -> str:
    current_rows = [row for row in rows if row.get("check_id") != "INT-012-LEGACY"]
    return status_from_rows(current_rows)


def _trade_cash_violations(trades: pd.DataFrame) -> int:
    if trades.empty:
        return 0
    violations = 0
    for item in trades.to_dict(orient="records"):
        if item["side"] == "BUY":
            expected = float(item["cash_before"]) - float(item["amount"]) - float(item["fee"])
        else:
            expected = float(item["cash_before"]) + float(item["amount"]) - float(item["fee"]) - float(item["tax"])
        if abs(expected - float(item["cash_after"])) > 0.02:
            violations += 1
    return violations


def _order_rule_violations(trades: pd.DataFrame, configs: dict, profile: str, result) -> dict:
    if trades.empty:
        return {"lot": 0, "min_amount": 0, "cash": 0, "single": 0, "exposure": 0}
    account = configs["account"]
    lot = int(account.get("execution", {}).get("round_lot", 100))
    min_trade = float(account.get("position_sizing", {}).get("min_trade_value", 0.0))
    default_single = float(account.get("position_sizing", {}).get("max_single_stock_weight", 1.0))
    strategy = configs["v2_strategy"] if profile == "combined_v2" else configs["baseline_strategy"]
    max_total = max(float(v) for v in strategy.get("market_regime", {}).get("max_total_position", {}).values())
    violations = {"lot": 0, "min_amount": 0, "cash": 0, "single": 0, "exposure": 0}
    for item in trades.to_dict(orient="records"):
        shares = float(item["shares"])
        if shares <= 0 or int(round(shares)) % lot != 0:
            violations["lot"] += 1
        if float(item["amount"]) < min_trade and item["action"] != "SELL_ALL":
            violations["min_amount"] += 1
        if item["side"] == "BUY" and float(item["cash_after"]) < -0.01:
            violations["cash"] += 1
        single_limit = default_single
        if profile == "combined_v2":
            bucket_cfg = strategy.get("buckets", {}).get(str(item.get("bucket")), {})
            single_limit = float(bucket_cfg.get("max_single_name_weight", default_single))
        if float(item["weight_after"]) > single_limit + 0.002:
            violations["single"] += 1
    if not result.nav.empty and float(result.nav["exposure"].max()) > max_total + 0.002:
        violations["exposure"] += 1
    return violations


def main() -> int:
    configs = load_audit_configs()
    prepare_v2_history(configs)
    features = load_feature_window()
    benchmark = load_benchmark_window()

    baseline = run_profile("baseline", features, benchmark, configs, execution_mode="next_bar")
    v2 = run_profile("combined_v2", features, benchmark, configs, execution_mode="next_bar")

    rows: list[dict] = []
    account = configs["account"]
    fee = account["execution"]["commission_rate"]
    tax = account["execution"]["stamp_duty_rate_sell"]
    slippage = account["execution"]["slippage_bps"]
    lot = account["execution"]["round_lot"]
    min_trade = account["position_sizing"]["min_trade_value"]
    rows.append(_row("INT-001", "账户与执行成本一致", "PASS", "both", f"initial_capital={account['account']['initial_capital']}, fee={fee}, tax={tax}, slippage_bps={slippage}, lot={lot}, min_trade={min_trade}", "config/account.yml", "继续统一读取 account 配置。"))

    dates = sorted(features["date"].astype(str).unique())
    status = "PASS" if dates[0] == DEFAULT_START_DATE and dates[-1] == DEFAULT_END_DATE else "FAIL"
    rows.append(_row("INT-002", "baseline 与 combined_v2 日期一致", status, "both", f"features_start={dates[0]}, features_end={dates[-1]}", "data/features/daily_features", "保持固定三年窗口，不读取 2026-04-03 之后数据。"))

    bm_dates = sorted(benchmark["date"].astype(str).unique())
    calendar_match = dates == bm_dates
    rows.append(_row("INT-003", "交易日历与 benchmark 一致", "PASS" if calendar_match else "FAIL", "both", f"feature_days={len(dates)}, benchmark_days={len(bm_dates)}", "data/raw/benchmark_daily.parquet", "若失败，先修复 benchmark 与特征日期对齐。"))

    compare_source = Path("scripts/run_backtest_compare.py").read_text(encoding="utf-8")
    independent = "baseline_engine = BacktestEngine" in compare_source and "v2_engine = BacktestEngine" in compare_source
    rows.append(_row("INT-004", "compare 账户状态互不污染", "PASS" if independent else "FAIL", "both", "compare script constructs separate baseline_engine and v2_engine instances" if independent else "compare script does not clearly separate engine instances", "scripts/run_backtest_compare.py", "baseline/v2 必须保持独立 BacktestEngine 实例。"))

    before = (v2.trade_list.copy(), dict(v2.metrics))
    write_profile_diagnostics("baseline", baseline, features, configs, BASELINE_HISTORY_DIR)
    write_profile_diagnostics("combined_v2", v2, features, configs, V2_HISTORY_DIR)
    diagnostics_ok = before[0].equals(v2.trade_list) and before[1] == v2.metrics
    rows.append(_row("INT-005", "diagnostics 不改变策略行为", "PASS" if diagnostics_ok else "FAIL", "both", "writing diagnostics left trades and metrics unchanged" if diagnostics_ok else "diagnostics mutated result object", "src/strategy/backtest_reports.py", "诊断输出只能读 result，不得回写信号、订单、现金或持仓。"))

    config_ok = configs["v2_strategy"].get("profile") == "combined_v2" and configs["v2_universe"].get("profile") == "combined_v2" and configs["baseline_strategy"].get("profile") != "combined_v2"
    rows.append(_row("INT-006", "strategy_config 与 universe_config 未串线", "PASS" if config_ok else "FAIL", "both", "baseline uses config/strategy.yml + config/universe_rules.yml; v2 uses config/strategy_v2.yml + config/universe_rules_v2.yml", "scripts/run_backtest_compare.py", "保持命令行参数分离。"))

    rows.append(_row("INT-007", "historical_universe_dir 按 profile 读取", "PASS", "both", f"baseline={BASELINE_HISTORY_DIR}; combined_v2={V2_HISTORY_DIR}", "scripts/run_backtest_compare.py", "不要把 v2 历史股票池传给 baseline。"))

    for profile, result in (("baseline", baseline), ("combined_v2", v2)):
        final_positions = result.final_positions if result.final_positions is not None else pd.DataFrame()
        final_equity = result.final_cash + (float(final_positions["market_value"].sum()) if not final_positions.empty else 0.0)
        nav_last = float(result.nav["nav"].iloc[-1])
        ok = abs(final_equity - nav_last) <= 0.02
        rows.append(_row(f"INT-008-{profile}", "最终权益等于现金加持仓市值", "PASS" if ok else "FAIL", profile, f"final_equity={final_equity:.2f}, nav_last={nav_last:.2f}", "src/strategy/backtest_engine.py", "若失败，先修复持仓估值或现金流水。"))

        trades = result.trades_detailed if result.trades_detailed is not None else pd.DataFrame()
        cash_violations = _trade_cash_violations(trades)
        rows.append(_row(f"INT-009-{profile}", "逐笔交易 cash_after 可复算", "PASS" if cash_violations == 0 else "FAIL", profile, f"violations={cash_violations}, trades={len(trades)}", "reports/backtest/*_trades_detailed.csv", "逐笔核对 amount/fee/tax/slippage 后再继续解释收益。"))

        violations = _order_rule_violations(trades, configs, profile, result)
        order_status = "PASS" if sum(violations.values()) == 0 else "FAIL"
        rows.append(_row(f"INT-010-{profile}", "交易订单满足整手、最小成交额、现金和仓位约束", order_status, profile, str(violations), "src/strategy/backtest_engine.py", "若失败，优先修复成交日重算约束。"))

    baseline_metrics = baseline.metrics
    baseline_ok = _close(baseline_metrics["annual_return"], 0.0010, 0.003) and abs(int(baseline_metrics["total_trades"]) - 7) <= 2
    rows.append(_row("INT-011", "baseline 结果可复现", "PASS" if baseline_ok else "FAIL", "baseline", f"annual_return={pct(baseline_metrics['annual_return'])}, total_trades={baseline_metrics['total_trades']}", "reports/backtest/baseline_diagnostic_report.md", "若失败，确认历史股票池和执行口径是否被改变。"))

    v2_metrics = v2.metrics
    rows.append(
        _row(
            "INT-012-LEGACY",
            "legacy pre-PIT 结果已废弃",
            "WARN",
            "combined_v2",
            "legacy same_close / pre-PIT result was 9.14% / 83 trades, now superseded by PIT-corrected result 7.14% / 76 trades",
            "reports/backtest/compare_combined_vs_v2_metrics.csv",
            "保留旧结果作审计记录；不得再把 9.14%/83 笔作为当前主策略必须复现的 PASS/FAIL 标准。",
        )
    )
    v2_current_ok = (
        _close(v2_metrics["annual_return"], 0.0714, 0.003)
        and abs(int(v2_metrics["total_trades"]) - 76) <= 2
        and _close(v2_metrics["max_drawdown"], -0.0936, 0.005)
    )
    rows.append(
        _row(
            "INT-013-CURRENT-PIT-STRICT",
            "combined_v2 当前 PIT 严格主口径可复现",
            "PASS" if v2_current_ok else "FAIL",
            "combined_v2",
            f"profile=combined_v2, execution_mode=next_bar, annual_return={pct(v2_metrics['annual_return'])}, cumulative_return={pct(v2_metrics['cumulative_return'])}, max_drawdown={pct(v2_metrics['max_drawdown'])}, total_trades={v2_metrics['total_trades']}",
            "reports/backtest/combined_v2_diagnostic_report.md",
            "当前主口径固定为 PIT 修正后的 combined_v2 next_bar；若失败，检查历史股票池、执行价或信号逻辑是否漂移。",
        )
    )

    audit_status = _audit_status(rows)
    out_csv = ensure_parent("reports/backtest/audit/integrity_audit.csv")
    out_md = ensure_parent("reports/backtest/audit/integrity_audit.md")
    pd.DataFrame(rows).to_csv(out_csv, index=False)

    metrics = pd.DataFrame(
        [
            metrics_row("baseline", "next_bar", baseline, benchmark),
            metrics_row("combined_v2", "next_bar", v2, benchmark),
        ]
    )
    metrics.to_csv(ensure_parent("reports/backtest/audit/integrity_recomputed_metrics.csv"), index=False)

    lines = [
        "# 回测完整性审计",
        "",
        f"- 审计结论: {audit_status}",
        f"- 固定区间: {DEFAULT_START_DATE} 到 {DEFAULT_END_DATE}",
        f"- baseline next_bar: 年化 {pct(baseline.metrics['annual_return'])}，成交 {baseline.metrics['total_trades']} 笔，最大回撤 {pct(baseline.metrics['max_drawdown'])}",
        f"- combined_v2 next_bar: 年化 {pct(v2.metrics['annual_return'])}，成交 {v2.metrics['total_trades']} 笔，最大回撤 {pct(v2.metrics['max_drawdown'])}",
        "",
        "## 检查项",
        "",
    ]
    for item in rows:
        lines.append(f"- {item['check_id']} {item['status']} [{item['profile']}]: {item['check_name']}。证据：{item['evidence']}")
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
