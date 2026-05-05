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
from scripts.report_metadata import config_hash, data_hash, git_commit


SEGMENTS = [
    ("full", "2023-04-03", "2026-04-03"),
    ("year_2023_2024", "2023-04-03", "2024-04-03"),
    ("year_2024_2025", "2024-04-03", "2025-04-03"),
    ("year_2025_2026", "2025-04-03", "2026-04-03"),
    ("half_2023_h2", "2023-04-03", "2023-10-03"),
    ("half_2023h2_2024h1", "2023-10-03", "2024-04-03"),
    ("half_2024_h2", "2024-04-03", "2024-10-03"),
    ("half_2024h2_2025h1", "2024-10-03", "2025-04-03"),
    ("half_2025_h2", "2025-04-03", "2025-10-03"),
    ("half_2025h2_2026h1", "2025-10-03", "2026-04-03"),
]


def _actual_range(dates: list[str], requested_start: str, requested_end: str) -> tuple[str, str]:
    start_candidates = [date for date in dates if date >= requested_start]
    end_candidates = [date for date in dates if date <= requested_end]
    if not start_candidates or not end_candidates:
        raise ValueError(f"No trading dates for {requested_start} -> {requested_end}")
    start = start_candidates[0]
    end = end_candidates[-1]
    if start > end:
        raise ValueError(f"Invalid actual range {start} -> {end}")
    return start, end


def main() -> int:
    configs = load_audit_configs()
    prepare_v2_history(configs)
    features_full = load_feature_window(DEFAULT_START_DATE, DEFAULT_END_DATE)
    benchmark_full = load_benchmark_window(DEFAULT_START_DATE, DEFAULT_END_DATE)
    all_dates = sorted(features_full["date"].astype(str).unique())
    rows = []
    for segment_name, requested_start, requested_end in SEGMENTS:
        actual_start, actual_end = _actual_range(all_dates, requested_start, requested_end)
        features = features_full[(features_full["date"] >= actual_start) & (features_full["date"] <= actual_end)].copy()
        benchmark = benchmark_full[(benchmark_full["date"] >= actual_start) & (benchmark_full["date"] <= actual_end)].copy()
        for profile in ("combined_v2", "baseline"):
            result = run_profile(profile, features, benchmark, configs, execution_mode="next_bar")
            row = metrics_row(profile, "next_bar", result, benchmark)
            row.update(
                {
                    "segment_name": segment_name,
                    "requested_start": requested_start,
                    "requested_end": requested_end,
                    "actual_start": actual_start,
                    "actual_end": actual_end,
                }
            )
            rows.append(row)
    frame = pd.DataFrame(rows)
    columns = [
        "segment_name",
        "requested_start",
        "requested_end",
        "actual_start",
        "actual_end",
        "profile",
        "execution_mode",
        "annual_return",
        "cumulative_return",
        "max_drawdown",
        "sharpe",
        "calmar",
        "volatility",
        "total_trades",
        "buy_trades",
        "sell_trades",
        "avg_daily_exposure",
        "max_daily_exposure",
        "avg_positions",
        "max_positions",
        "turnover",
        "benchmark_annual_return",
        "excess_annual_return",
        "defensive_pnl",
        "cyclical_pnl",
        "defensive_trade_count",
        "cyclical_trade_count",
    ]
    frame = frame.reindex(columns=columns)
    frame.to_csv(ensure_parent("reports/backtest/robustness/walkforward_metrics.csv"), index=False)

    v2 = frame[frame["profile"] == "combined_v2"].copy()
    year = v2[v2["segment_name"].str.startswith("year_")]
    half = v2[v2["segment_name"].str.startswith("half_")]
    positive_years = int((year["annual_return"] > 0).sum())
    half_abs = half["cumulative_return"].abs()
    largest_half_share = float(half_abs.max() / half_abs.sum()) if half_abs.sum() > 0 else 0.0
    low_trade = half[half["total_trades"] <= 1]["segment_name"].tolist()
    down_market = v2[v2["benchmark_annual_return"] < 0]
    up_underperform = v2[(v2["benchmark_annual_return"] > 0) & (v2["excess_annual_return"] < 0)]

    lines = [
        "# walk-forward / 分年度鲁棒性验证",
        "",
        f"- git_commit: {git_commit()}",
        f"- config_hash: {config_hash()}",
        f"- data_hash: {data_hash()}",
        "- 主口径: combined_v2 next_bar，baseline next_bar 作为参考。",
        f"- 全区间: {DEFAULT_START_DATE} 到 {DEFAULT_END_DATE}",
        f"- 分年度正收益段数: {positive_years}/{len(year)}",
        f"- 最大半年度绝对收益贡献占比: {largest_half_share:.2%}",
        f"- 几乎不交易的半年度段: {', '.join(low_trade) if low_trade else '无'}",
        "",
        "## 关键回答",
        "",
        f"- combined_v2 是否只在某一年有效: {'是，存在明显单一年份依赖' if positive_years <= 1 else '否，正收益不只集中于单一年份'}。",
        f"- 是否某个半年段贡献大部分收益: {'是' if largest_half_share > 0.60 else '否'}，最大半年度占比 {largest_half_share:.2%}。",
        f"- 是否某阶段几乎不交易: {'是，' + ', '.join(low_trade) if low_trade else '否'}。",
        f"- benchmark 下跌阶段控制回撤: 下跌段 {len(down_market)} 个，combined_v2 最差回撤 {pct(down_market['max_drawdown'].min()) if not down_market.empty else '无下跌段'}。",
        f"- benchmark 上涨阶段是否因仓位不足跑输: {'是，' + ', '.join(up_underperform['segment_name'].tolist()) if not up_underperform.empty else '未观察到上涨段显著跑输'}。",
        "",
        "## 分段指标",
        "",
    ]
    for row in v2.to_dict(orient="records"):
        lines.append(
            f"- {row['segment_name']}: {row['actual_start']} 到 {row['actual_end']}，年化 {pct(row['annual_return'])}，累计 {pct(row['cumulative_return'])}，回撤 {pct(row['max_drawdown'])}，成交 {int(row['total_trades'])}，平均仓位 {pct(row['avg_daily_exposure'])}，超额 {pct(row['excess_annual_return'])}"
        )
    ensure_parent("reports/backtest/robustness/walkforward_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
