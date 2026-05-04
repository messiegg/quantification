#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.audit_common import (
    DEFAULT_END_DATE,
    DEFAULT_START_DATE,
    ensure_parent,
    load_audit_configs,
    load_benchmark_window,
    load_feature_window,
    metrics_row,
    pct,
    prepare_v2_history,
    run_profile,
)


def main() -> int:
    configs = load_audit_configs()
    prepare_v2_history(configs)
    features = load_feature_window()
    benchmark = load_benchmark_window()

    rows = []
    results = {}
    for profile in ("baseline", "combined_v2"):
        for mode in ("same_close", "next_bar"):
            result = run_profile(profile, features, benchmark, configs, execution_mode=mode)
            results[(profile, mode)] = result
            rows.append(metrics_row(profile, mode, result, benchmark))
    frame = pd.DataFrame(rows)
    frame.to_csv(ensure_parent("reports/backtest/audit/execution_mode_compare.csv"), index=False)

    v2_same = float(frame[(frame["profile"] == "combined_v2") & (frame["execution_mode"] == "same_close")]["annual_return"].iloc[0])
    v2_next = float(frame[(frame["profile"] == "combined_v2") & (frame["execution_mode"] == "next_bar")]["annual_return"].iloc[0])
    drop = (v2_same - v2_next) / abs(v2_same) if abs(v2_same) > 1e-12 else 0.0
    status = "WARN" if drop > 0.50 else "PASS"
    lines = [
        "# 执行价和交易时点审计",
        "",
        f"- 固定区间: {DEFAULT_START_DATE} 到 {DEFAULT_END_DATE}",
        "- 当前严格口径定义为 `next_bar`: t 日收盘后形成信号，下一交易日按 open 成交；没有 open 时退回下一交易日 close。",
        "- 乐观对照口径定义为 `same_close`: t 日信号直接按 t 日 close 成交，属于 optimistic_close_same_day。",
        f"- combined_v2 same_close 年化: {pct(v2_same)}",
        f"- combined_v2 next_bar 年化: {pct(v2_next)}",
        f"- next_bar 相对 same_close 年化下降: {drop:.2%}，状态: {status}",
        "",
        "## 指标表",
        "",
    ]
    for row in rows:
        lines.append(
            f"- {row['profile']} / {row['execution_mode']}: 年化 {pct(row['annual_return'])}，累计 {pct(row['cumulative_return'])}，最大回撤 {pct(row['max_drawdown'])}，夏普 {row['sharpe']:.2f}，成交 {int(row['total_trades'])} 笔，平均仓位 {pct(row['avg_daily_exposure'])}，超额年化 {pct(row['excess_annual_return'])}"
        )
    if status == "WARN":
        lines.extend(
            [
                "",
                "## 风险提示",
                "",
                "- combined_v2 在严格 next_bar 下较 same_close 年化下降超过 50%，需要把同日收盘成交视为乐观口径，主报告不能用 same_close 作为候选策略依据。",
            ]
        )
    ensure_parent("reports/backtest/audit/execution_mode_compare.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
