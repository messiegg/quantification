#!/usr/bin/env python3
from __future__ import annotations

import copy
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.audit_common import (
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
)
from src.strategy.backtest_engine import BacktestEngine


def _run_cost_profile(cost_profile: str, fee_mult: float, slippage_mult: float, tax_mult: float, features: pd.DataFrame, benchmark: pd.DataFrame, configs: dict):
    account_cfg = copy.deepcopy(configs["account"])
    engine = BacktestEngine(
        copy.deepcopy(configs["v2_strategy"]),
        universe_rules_cfg=copy.deepcopy(configs["v2_universe"]),
        account_cfg=account_cfg,
        historical_universe_dir=V2_HISTORY_DIR,
        execution_mode="next_bar",
    )
    engine.fee_rate *= fee_mult
    engine.slippage_rate *= slippage_mult
    engine.tax_rate *= tax_mult
    result = engine.run(features=features.copy(), benchmark=benchmark.copy(), bucket="combined")
    row = metrics_row("combined_v2", "next_bar", result, benchmark)
    row["cost_profile"] = cost_profile
    row["net_pnl"] = float(result.nav["nav"].iloc[-1] - engine.initial_cash) if not result.nav.empty else 0.0
    return row


def main() -> int:
    configs = load_audit_configs()
    prepare_v2_history(configs)
    features = load_feature_window(DEFAULT_START_DATE, DEFAULT_END_DATE)
    benchmark = load_benchmark_window(DEFAULT_START_DATE, DEFAULT_END_DATE)
    baseline = run_profile("baseline", features, benchmark, configs, execution_mode="next_bar")
    profiles = [
        ("normal_cost", 1.0, 1.0, 1.0),
        ("double_fee", 2.0, 1.0, 1.0),
        ("double_slippage", 1.0, 2.0, 1.0),
        ("high_cost", 2.0, 2.0, 1.0),
        ("sell_tax_stress", 1.0, 1.0, 1.5),
        ("no_slippage", 1.0, 0.0, 1.0),
    ]
    rows = [_run_cost_profile(*profile, features=features, benchmark=benchmark, configs=configs) for profile in profiles]
    frame = pd.DataFrame(rows)
    columns = [
        "cost_profile",
        "annual_return",
        "cumulative_return",
        "max_drawdown",
        "sharpe",
        "total_trades",
        "total_fees",
        "total_tax",
        "total_slippage",
        "net_pnl",
        "benchmark_annual_return",
        "excess_annual_return",
    ]
    frame = frame.reindex(columns=columns)
    frame.to_csv(ensure_parent("reports/backtest/robustness/cost_stress_metrics.csv"), index=False)

    normal = frame[frame["cost_profile"] == "normal_cost"].iloc[0]
    high = frame[frame["cost_profile"] == "high_cost"].iloc[0]
    baseline_annual = float(baseline.metrics["annual_return"])
    high_cost_sensitive = float(high["annual_return"]) < 0 and int(high["total_trades"]) >= 50
    lines = [
        "# 成本和滑点压力测试",
        "",
        "- 口径: combined_v2 next_bar。",
        "- 压力测试只覆盖成交成本参数；信号、股票池和策略阈值不写回、不修改。",
        f"- baseline next_bar 年化: {pct(baseline_annual)}",
        f"- normal_cost 年化: {pct(normal['annual_return'])}，总费用 {normal['total_fees']:.2f}，印花税 {normal['total_tax']:.2f}，滑点成本 {normal['total_slippage']:.2f}",
        f"- high_cost 年化: {pct(high['annual_return'])}，状态: {'成本敏感' if high_cost_sensitive else '未触发成本敏感硬标记'}",
        "",
        "## 关键回答",
        "",
        f"- 当前收益是否被交易成本明显侵蚀: {'是' if float(normal['total_fees'] + normal['total_tax'] + normal['total_slippage']) > abs(float(normal['net_pnl'])) * 0.15 else '否'}。",
        f"- 成本翻倍后是否仍显著优于 baseline: {'是' if float(high['annual_return']) > baseline_annual else '否'}。",
        f"- 当前交易换手是否合理: normal_cost 成交 {int(normal['total_trades'])} 笔，turnover 见 sensitivity/主审计指标；需结合归因判断是否过度依赖频繁交易。",
        f"- high_cost 下年化为负且交易频繁: {'是' if high_cost_sensitive else '否'}。",
        "",
        "## 成本档位",
        "",
    ]
    for row in frame.to_dict(orient="records"):
        lines.append(f"- {row['cost_profile']}: 年化 {pct(row['annual_return'])}，累计 {pct(row['cumulative_return'])}，回撤 {pct(row['max_drawdown'])}，夏普 {row['sharpe']:.2f}，费用 {row['total_fees']:.2f}，税 {row['total_tax']:.2f}，滑点 {row['total_slippage']:.2f}")
    ensure_parent("reports/backtest/robustness/cost_stress_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
