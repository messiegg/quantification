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
from scripts.run_backtest_attribution import build_daily_regime_attribution, build_position_attribution, build_signal_attribution
from src.strategy.backtest_reports import build_universe_funnel, write_diagnostic_outputs
from src.utils.config import load_yaml


def _density_pass(row: pd.Series) -> bool:
    return bool(
        row["total_trades"] >= 25
        and row["buy_trades"] >= 12
        and row["avg_daily_exposure"] >= 0.15
        and row["exposure_active_days_ratio"] >= 0.30
        and row["avg_positions"] >= 2
    )


def _trade_dates(features: pd.DataFrame) -> list[str]:
    return sorted(features["date"].astype(str).unique())


def main() -> int:
    configs = load_audit_configs()
    guard_strategy = load_yaml("config/strategy_v2_1_risk_guard.yml")
    prepare_v2_history(configs)
    features = load_feature_window(DEFAULT_START_DATE, DEFAULT_END_DATE)
    benchmark = load_benchmark_window(DEFAULT_START_DATE, DEFAULT_END_DATE)
    initial_capital = float(configs["account"]["account"]["initial_capital"])

    v2 = run_profile("combined_v2", features, benchmark, configs, execution_mode="next_bar")
    guard = run_profile(
        "combined_v2_1_risk_guard",
        features,
        benchmark,
        configs,
        execution_mode="next_bar",
        historical_universe_dir=V2_HISTORY_DIR,
        strategy_cfg=guard_strategy,
        universe_cfg=configs["v2_universe"],
    )
    out_dir = ensure_parent("reports/backtest/v2_1/compare_v2_vs_v2_1_risk_guard_metrics.csv").parent
    universe, scores = build_universe_funnel(features, V2_HISTORY_DIR, configs["v2_universe"], configs["metric_map"])
    write_diagnostic_outputs("combined_v2_1_risk_guard", guard, universe, output_dir=out_dir, candidate_scores=scores)

    rows = []
    for profile, result, strategy in (
        ("combined_v2", v2, configs["v2_strategy"]),
        ("combined_v2_1_risk_guard", guard, guard_strategy),
    ):
        row = metrics_row(profile, "next_bar", result, benchmark)
        daily_regime, regime_attr = build_daily_regime_attribution(result, features, benchmark, strategy, initial_capital)
        row["neutral_daily_pnl"] = float(regime_attr.loc[regime_attr["market_regime"] == "neutral", "total_daily_pnl"].sum()) if not regime_attr.empty else 0.0
        row["risk_off_daily_pnl"] = float(regime_attr.loc[regime_attr["market_regime"] == "risk_off", "total_daily_pnl"].sum()) if not regime_attr.empty else 0.0
        row["risk_on_daily_pnl"] = float(regime_attr.loc[regime_attr["market_regime"] == "risk_on", "total_daily_pnl"].sum()) if not regime_attr.empty else 0.0
        row["exposure_active_days_ratio"] = result.metrics.get("exposure_active_days_ratio", 0.0)
        rows.append(row)
        if profile == "combined_v2_1_risk_guard":
            daily_regime.to_csv(out_dir / "combined_v2_1_risk_guard_daily_regime_attribution.csv", index=False)
            regime_attr.to_csv(out_dir / "combined_v2_1_risk_guard_regime_attribution.csv", index=False)
    metrics = pd.DataFrame(rows)
    metrics.to_csv(out_dir / "compare_v2_vs_v2_1_risk_guard_metrics.csv", index=False)

    guard.trades_detailed.to_csv(out_dir / "combined_v2_1_risk_guard_trades_detailed.csv", index=False)
    calendar = _trade_dates(features)
    position_attr = build_position_attribution(guard.trades_detailed, guard.final_positions, features, calendar)
    signal_attr = build_signal_attribution(guard.trades_detailed, guard.final_positions, calendar)
    position_attr.to_csv(out_dir / "combined_v2_1_risk_guard_position_attribution.csv", index=False)
    signal_attr.to_csv(out_dir / "combined_v2_1_risk_guard_signal_attribution.csv", index=False)

    v2_row = metrics[metrics["profile"] == "combined_v2"].iloc[0]
    guard_row = metrics[metrics["profile"] == "combined_v2_1_risk_guard"].iloc[0]
    density_ok = _density_pass(guard_row)
    risk_loss_improved = float(guard_row["risk_off_daily_pnl"] + guard_row["neutral_daily_pnl"]) > float(v2_row["risk_off_daily_pnl"] + v2_row["neutral_daily_pnl"])
    drawdown_improved = float(guard_row["max_drawdown"]) > float(v2_row["max_drawdown"])
    return_drop = float(v2_row["annual_return"]) - float(guard_row["annual_return"])
    if density_ok and risk_loss_improved and drawdown_improved and return_drop <= 0.02:
        label = "candidate_for_manual_review"
    elif drawdown_improved and return_drop > 0.02:
        label = "conservative_candidate"
    else:
        label = "research_only"

    attribution_lines = [
        "# combined_v2_1_risk_guard 归因摘要",
        "",
        "- universe、score、基础过滤沿用 combined_v2；本候选只改变 market regime 风险侧买入限制。",
        f"- 年化 {pct(guard_row['annual_return'])}，累计 {pct(guard_row['cumulative_return'])}，最大回撤 {pct(guard_row['max_drawdown'])}，成交 {int(guard_row['total_trades'])}。",
        f"- risk_off daily PnL {guard_row['risk_off_daily_pnl']:.2f}，neutral daily PnL {guard_row['neutral_daily_pnl']:.2f}。",
        "",
        "## entry / exit signal",
        "",
    ]
    for row in signal_attr[signal_attr["attribution_type"].isin(["entry_signal", "exit_signal"])].to_dict(orient="records"):
        key = row["entry_signal_level"] if row["attribution_type"] == "entry_signal" else f"{row['exit_action']} / {row['exit_reason']}"
        attribution_lines.append(f"- {row['attribution_type']} {key}: total_pnl {row['total_pnl']:.2f}，realized {row['realized_pnl']:.2f}，unrealized {row['unrealized_pnl']:.2f}，count {int(row['trade_count'])}。")
    attribution_lines.extend(["", "## position", ""])
    for row in position_attr.sort_values("total_pnl", ascending=False).head(10).to_dict(orient="records") if not position_attr.empty else []:
        attribution_lines.append(f"- {row['ts_code']} {row['name']}: total_pnl {row['total_pnl']:.2f}，holding_days {row['holding_days_total']}，open={row['is_open_position']}。")
    (out_dir / "combined_v2_1_risk_guard_attribution.md").write_text("\n".join(attribution_lines) + "\n", encoding="utf-8")

    lines = [
        "# combined_v2 vs combined_v2_1_risk_guard",
        "",
        "- 主策略仍是 combined_v2 PIT next_bar；combined_v2_1_risk_guard 只是非主策略候选，不替换主口径。",
        "- v2_1 沿用 combined_v2 universe，不新增 universe_rules 文件。",
        "",
        "## 对比结果",
        "",
        f"- v2: 年化 {pct(v2_row['annual_return'])}，累计 {pct(v2_row['cumulative_return'])}，最大回撤 {pct(v2_row['max_drawdown'])}，成交 {int(v2_row['total_trades'])}。",
        f"- v2_1: 年化 {pct(guard_row['annual_return'])}，累计 {pct(guard_row['cumulative_return'])}，最大回撤 {pct(guard_row['max_drawdown'])}，成交 {int(guard_row['total_trades'])}。",
        f"- 是否降低 risk_off / neutral 损失: {'是' if risk_loss_improved else '否'}。",
        f"- 是否降低最大回撤: {'是' if drawdown_improved else '否'}。",
        f"- 是否牺牲太多收益: {'是' if return_drop > 0.02 else '否'}；年化差 {pct(return_drop)}。",
        f"- 是否减少过多交易: {'否' if int(guard_row['total_trades']) >= 25 else '是'}。",
        "",
        "## 最低交易密度",
        "",
        f"- total_trades >= 25: {int(guard_row['total_trades'])}",
        f"- buy_trades >= 12: {int(guard_row['buy_trades'])}",
        f"- avg_daily_exposure >= 15%: {pct(guard_row['avg_daily_exposure'])}",
        f"- exposure_active_days_ratio >= 30%: {pct(guard_row['exposure_active_days_ratio'])}",
        f"- avg_positions >= 2: {guard_row['avg_positions']:.2f}",
        f"- density_status: {'PASS' if density_ok else 'FAIL'}",
        "",
        "## 结论",
        "",
        f"- 候选标签: {label}。",
        "- 如果 v2_1 不明显优于 v2，不推荐替换 v2；若只是降低回撤但明显牺牲收益，只能作为 conservative candidate 继续观察。",
    ]
    (out_dir / "compare_v2_vs_v2_1_risk_guard.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
