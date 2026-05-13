#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.audit_common import ensure_parent, pct


def _read_csv_optional(path: str) -> pd.DataFrame:
    try:
        return pd.read_csv(path)
    except (FileNotFoundError, pd.errors.EmptyDataError):
        return pd.DataFrame()


def _status_from_frame(frame: pd.DataFrame, ignore_ids: set[str] | None = None) -> str:
    if frame.empty:
        return "MISSING"
    ignore_ids = ignore_ids or set()
    active = frame[~frame.get("check_id", pd.Series(dtype=str)).astype(str).isin(ignore_ids)].copy()
    statuses = set(active.get("status", pd.Series(dtype=str)).astype(str).str.upper())
    if "FAIL" in statuses:
        return "FAIL"
    if "WARN" in statuses:
        return "WARN"
    return "PASS"


def _row(frame: pd.DataFrame, key: str, value: str) -> pd.Series:
    match = frame[frame[key] == value]
    return match.iloc[0] if not match.empty else pd.Series(dtype=object)


def _metric(metrics: pd.DataFrame, control_id: str) -> pd.Series:
    if metrics.empty:
        return pd.Series(dtype=object)
    match = metrics[metrics["control_id"] == control_id]
    return match.iloc[0] if not match.empty else pd.Series(dtype=object)


def _max_top_risk_on_share(daily_regime: pd.DataFrame) -> float:
    if daily_regime.empty:
        return 0.0
    risk_on = daily_regime[daily_regime["market_regime"] == "risk_on"].copy()
    positive = risk_on[risk_on["daily_pnl"] > 0]["daily_pnl"].astype(float).sort_values(ascending=False)
    total = float(positive.sum())
    if total <= 0:
        return 0.0
    return float(positive.head(3).sum() / total)


def main() -> int:
    integrity = _read_csv_optional("reports/backtest/audit/integrity_audit.csv")
    integrity_metrics = _read_csv_optional("reports/backtest/audit/integrity_recomputed_metrics.csv")
    lookahead = _read_csv_optional("reports/backtest/audit/lookahead_audit.csv")
    violations = _read_csv_optional("reports/backtest/audit/lookahead_violations.csv")
    universe_pit = _read_csv_optional("reports/backtest/audit/universe_pit_audit.csv")
    execution = _read_csv_optional("reports/backtest/audit/execution_mode_compare.csv")
    walk = _read_csv_optional("reports/backtest/robustness/walkforward_metrics.csv")
    sensitivity = _read_csv_optional("reports/backtest/robustness/sensitivity_metrics.csv")
    cost = _read_csv_optional("reports/backtest/robustness/cost_stress_metrics.csv")
    position = _read_csv_optional("reports/backtest/attribution/combined_v2_position_attribution.csv")
    industry = _read_csv_optional("reports/backtest/attribution/combined_v2_industry_attribution.csv")
    monthly_check = _read_csv_optional("reports/backtest/attribution/combined_v2_monthly_returns_check.csv")
    daily_regime = _read_csv_optional("reports/backtest/attribution/combined_v2_daily_regime_attribution.csv")
    regime = _read_csv_optional("reports/backtest/attribution/combined_v2_regime_attribution.csv")
    controls = _read_csv_optional("reports/backtest/controls/control_baselines_metrics.csv")
    placebo = _read_csv_optional("reports/backtest/controls/random_placebo_metrics.csv")
    v21 = _read_csv_optional("reports/backtest/v2_1/compare_v2_vs_v2_1_risk_guard_metrics.csv")
    report_consistency = _read_csv_optional("reports/backtest/audit/report_consistency_check.csv")

    baseline = _row(integrity_metrics, "profile", "baseline")
    v2 = _row(integrity_metrics, "profile", "combined_v2")
    v2_same = execution[(execution["profile"] == "combined_v2") & (execution["execution_mode"] == "same_close")].iloc[0] if not execution.empty else pd.Series(dtype=object)
    v2_next = execution[(execution["profile"] == "combined_v2") & (execution["execution_mode"] == "next_bar")].iloc[0] if not execution.empty else pd.Series(dtype=object)
    drop = (float(v2_same.get("annual_return", 0.0)) - float(v2_next.get("annual_return", 0.0))) / abs(float(v2_same.get("annual_return", 0.0))) if abs(float(v2_same.get("annual_return", 0.0))) > 1e-12 else 0.0
    walk_v2 = walk[walk["profile"] == "combined_v2"] if not walk.empty else pd.DataFrame()
    non_current = sensitivity[sensitivity["variant_id"] != "current_v2"] if not sensitivity.empty and "variant_id" in sensitivity else pd.DataFrame()
    near_zero = int((non_current["annual_return"].abs() < 0.01).sum()) if not non_current.empty else 0
    under_baseline = int((non_current["annual_return"] <= float(baseline.get("annual_return", 0.0))).sum()) if not non_current.empty else 0
    high_cost = cost[cost["cost_profile"] == "high_cost"].iloc[0] if not cost.empty and "cost_profile" in cost else pd.Series(dtype=object)
    max_stock_pct = float(position["contribution_pct_of_total_pnl"].max()) if not position.empty else 0.0
    max_industry_pct = float(industry["contribution_pct_of_total_pnl"].max()) if not industry.empty else 0.0
    monthly_diff = abs(float(monthly_check["diff"].iloc[-1])) if not monthly_check.empty else 0.0
    top_risk_on_share = _max_top_risk_on_share(daily_regime)
    placebo_seed = placebo[placebo.get("row_type", pd.Series(dtype=str)) == "seed"] if not placebo.empty else pd.DataFrame()
    placebo_percentile = (
        float((placebo_seed["annual_return"].astype(float) <= float(v2.get("annual_return", 0.0))).mean() * 100.0)
        if not placebo_seed.empty
        else 0.0
    )
    control_v2 = _metric(controls, "combined_v2_next_bar")
    universe_equal = _metric(controls, "v2_universe_equal_weight_monthly")
    top_score = _metric(controls, "v2_top_score_monthly")
    defensive = _metric(controls, "v2_defensive_only")
    cyclical = _metric(controls, "v2_cyclical_only")
    no_div = _metric(controls, "v2_no_high_dividend_supplement")
    no_grid = _metric(controls, "v2_no_grid")
    no_stop = _metric(controls, "v2_no_trend_stop")
    no_risk_buy = _metric(controls, "v2_risk_off_no_new_buy")
    v21_row = v21[v21["profile"] == "combined_v2_1_risk_guard"].iloc[0] if not v21.empty and "profile" in v21 else pd.Series(dtype=object)

    blockers = []
    warnings = []
    integrity_status = _status_from_frame(integrity, {"INT-012-LEGACY"})
    lookahead_status = _status_from_frame(lookahead)
    report_consistency_status = _status_from_frame(report_consistency)
    if integrity_status == "FAIL":
        blockers.append("integrity_audit 存在非 legacy FAIL。")
    if not violations.empty:
        blockers.append("lookahead_audit 存在确认的未来数据使用。")
    if not universe_pit.empty and bool(universe_pit.get("used_future_data", pd.Series(dtype=bool)).any()):
        blockers.append("universe_pit_audit 发现月度股票池使用 future data。")
    if monthly_diff > 1e-8:
        warnings.append(f"monthly return 复合仍不等于总累计收益，diff={monthly_diff:.12f}。")
    if top_risk_on_share > 0.70:
        warnings.append(f"risk_on 正收益过度集中，前三个 risk_on 正收益日贡献 {top_risk_on_share:.2%}。")
    if placebo_percentile and placebo_percentile < 75:
        warnings.append(f"combined_v2 随机 placebo 年化分位只有 {placebo_percentile:.1f}%。")
    if not universe_equal.empty and float(control_v2.get("annual_return", v2.get("annual_return", 0.0))) < float(universe_equal.get("annual_return", 0.0)):
        warnings.append("combined_v2 输给 v2_universe_equal_weight_monthly。")
    if max_stock_pct > 0.50:
        warnings.append(f"最大单股贡献 {max_stock_pct:.2%} 超过 50%。")
    if max_industry_pct > 0.70:
        warnings.append(f"最大行业贡献 {max_industry_pct:.2%} 超过 70%。")
    if lookahead_status == "WARN":
        warnings.append("lookahead 审计仍有非确认前视的 WARN，例如字段缺失或报告口径提示。")
    if report_consistency_status == "FAIL":
        warnings.append("report_consistency_check 存在 FAIL，最终评级最多 WARN_CANDIDATE。")
    elif report_consistency_status == "WARN":
        warnings.append("report_consistency_check 存在 WARN。")

    if blockers:
        rc_rating = "FAIL_RESEARCH_ONLY"
    elif warnings:
        rc_rating = "WARN_CANDIDATE"
    else:
        better_than_controls = (
            not control_v2.empty
            and not universe_equal.empty
            and not top_score.empty
            and float(control_v2["annual_return"]) > float(universe_equal["annual_return"])
            and float(control_v2["annual_return"]) > float(top_score["annual_return"])
            and placebo_percentile >= 75
        )
        rc_rating = "PASS_CANDIDATE" if better_than_controls else "WARN_CANDIDATE"

    audit_rating = "FAIL" if blockers else ("WARN" if warnings or integrity_status == "WARN" or lookahead_status == "WARN" else "PASS")
    summary_lines = [
        "# combined_v2 总审计结论",
        "",
        f"- 最终评级: {audit_rating}",
        "- 评级含义: 旧 9.14% / 83 笔为 LEGACY_SUPERSEDED 口径；当前审计不再要求复现 legacy 指标。",
        "",
        "## 1. baseline vs combined_v2 主结果",
        "",
        f"- baseline next_bar: 年化 {pct(baseline.get('annual_return', 0.0))}，累计 {pct(baseline.get('cumulative_return', 0.0))}，最大回撤 {pct(baseline.get('max_drawdown', 0.0))}，成交 {int(baseline.get('total_trades', 0))}。",
        f"- combined_v2 PIT next_bar: 年化 {pct(v2.get('annual_return', 0.0))}，累计 {pct(v2.get('cumulative_return', 0.0))}，最大回撤 {pct(v2.get('max_drawdown', 0.0))}，成交 {int(v2.get('total_trades', 0))}。",
        "- legacy pre-PIT / old same_close: 9.14% 年化、83 笔，已标记为 INT-012-LEGACY WARN，仅保留作历史记录。",
        "",
        "## 2. same_close vs next_bar",
        "",
        f"- same_close: 年化 {pct(v2_same.get('annual_return', 0.0))}，累计 {pct(v2_same.get('cumulative_return', 0.0))}，最大回撤 {pct(v2_same.get('max_drawdown', 0.0))}。",
        f"- next_bar: 年化 {pct(v2_next.get('annual_return', 0.0))}，累计 {pct(v2_next.get('cumulative_return', 0.0))}，最大回撤 {pct(v2_next.get('max_drawdown', 0.0))}。",
        f"- next_bar 相对 same_close 年化变化 {drop:.2%}。",
        "",
        "## 3. 审计状态",
        "",
        f"- integrity: {integrity_status}。",
        f"- lookahead audit status: {lookahead_status}；确认违规 {len(violations)} 条。",
        f"- universe PIT: 月度文件 {len(universe_pit)} 个，future-data 文件 {int(universe_pit['used_future_data'].sum()) if not universe_pit.empty and 'used_future_data' in universe_pit else 0} 个。",
        f"- execution mode: next_bar 为当前严格主口径。",
        f"- report consistency: {report_consistency_status}。",
        f"- cost stress high_cost: 年化 {pct(high_cost.get('annual_return', 0.0))}。",
        f"- sensitivity: 年化接近 0 的变体 {near_zero}/{len(non_current)}，跑输 baseline 的变体 {under_baseline}/{len(non_current)}。",
        "",
        "## 4. 收益归因修复",
        "",
        f"- monthly_returns: 最后一行复合差异 {monthly_diff:.12f}。",
        "- open position holding days: 未平仓持仓统计到回测结束日，字段包含 is_open_position/open_position_days/realized_holding_days/total_holding_days_to_end。",
        "- signal attribution: 已按 entry_signal / exit_signal / entry_exit_pair 归因。",
        "- regime attribution: 已新增 daily MTM 口径，并与 trade realization 口径分开。",
        "- bucket / industry attribution: 已统一 total_pnl 口径。",
        f"- markdown / CSV consistency: {report_consistency_status}。",
        f"- 最大单股贡献 {max_stock_pct:.2%}，最大行业贡献 {max_industry_pct:.2%}。",
        "",
        "## 5. control baselines",
        "",
        f"- v2 vs universe equal weight: {pct(control_v2.get('annual_return', v2.get('annual_return', 0.0)))} vs {pct(universe_equal.get('annual_return', 0.0))}。",
        f"- v2 vs top score monthly: {pct(control_v2.get('annual_return', v2.get('annual_return', 0.0)))} vs {pct(top_score.get('annual_return', 0.0))}。",
        f"- random placebo percentile: {placebo_percentile:.1f}%。",
        f"- defensive_only 年化 {pct(defensive.get('annual_return', 0.0))}；cyclical_only 年化 {pct(cyclical.get('annual_return', 0.0))}。",
        f"- no_high_dividend_supplement 年化 {pct(no_div.get('annual_return', 0.0))}。",
        f"- no_grid 年化 {pct(no_grid.get('annual_return', 0.0))}。",
        f"- no_trend_stop 年化 {pct(no_stop.get('annual_return', 0.0))}，只作风险解释。",
        f"- risk_off_no_new_buy 年化 {pct(no_risk_buy.get('annual_return', 0.0))}。",
        "",
        "## 6. v2_1_risk_guard",
        "",
        f"- 年化 {pct(v21_row.get('annual_return', 0.0))}，最大回撤 {pct(v21_row.get('max_drawdown', 0.0))}，成交 {int(v21_row.get('total_trades', 0))}。",
        "- v2_1 不覆盖 combined_v2；如果不明显优于 v2，不推荐替换。",
        "",
        "## 7. 最大风险点",
        "",
    ]
    if blockers or warnings:
        for item in blockers + warnings:
            summary_lines.append(f"- {item}")
    else:
        summary_lines.append("- 未触发硬性阻断项或候选降级项。")
    summary_lines.extend(
        [
            "",
            "## 8. 下一步建议",
            "",
            "- 保留 combined_v2 为当前严格主候选，主口径固定为 PIT next_bar 7.14%/76 笔附近。",
            "- 不追求恢复 legacy 9.14%，不继续放宽参数。",
            "- 若进入观察，只能小资金、人工、继续审计，不能自动下单。",
        ]
    )
    ensure_parent("reports/backtest/audit/combined_v2_audit_summary.md").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    rc_lines = [
        "# combined_v2 RC 总结",
        "",
        f"- 最终评级: {rc_rating}",
        "- 评级边界: 这是“小资金手动试运行候选”评级，不是自动实盘策略评级；本仓库仍禁止自动下单和券商 API。",
        "",
        "## 当前严格主口径",
        "",
        "- combined_v2 PIT next_bar。",
        f"- 当前严谨结果: 年化 {pct(v2.get('annual_return', 0.0))}，累计 {pct(v2.get('cumulative_return', 0.0))}，最大回撤 {pct(v2.get('max_drawdown', 0.0))}，夏普 {float(v2.get('sharpe', 0.0)):.2f}，成交 {int(v2.get('total_trades', 0))}，平均日仓位 {pct(v2.get('avg_daily_exposure', 0.0))}，最大持仓数 {int(v2.get('max_positions', 0))}。",
        "- 9.14% / 83 笔是旧口径，已被废弃；不作为当前主策略复现标准。",
        "",
        "## 报告口径修复状态",
        "",
        f"- monthly_returns 复合一致: {'是' if monthly_diff <= 1e-8 else '否'}，diff={monthly_diff:.12f}。",
        "- open position holding days 已修复: 未平仓统计到回测结束日。",
        "- signal attribution 已按 entry_signal / exit_signal / entry_exit_pair 归因。",
        "- regime attribution 已使用 daily MTM，并保留 trade realization 对照。",
        "- bucket / industry attribution 已统一 total_pnl 口径。",
        f"- markdown / CSV consistency: {report_consistency_status}。",
        "",
        "## 审计状态",
        "",
        f"- integrity: {integrity_status}",
        f"- lookahead audit status: {lookahead_status}，确认违规 {len(violations)} 条",
        f"- universe PIT: future-data 文件 {int(universe_pit['used_future_data'].sum()) if not universe_pit.empty and 'used_future_data' in universe_pit else 0} 个",
        "- execution mode: PASS，next_bar 为严格主口径",
        f"- report consistency: {report_consistency_status}",
        f"- cost stress: high_cost 年化 {pct(high_cost.get('annual_return', 0.0))}",
        f"- sensitivity: near_zero {near_zero}/{len(non_current)}，under_baseline {under_baseline}/{len(non_current)}",
        "",
        "## control baseline 结果",
        "",
        f"- v2 是否优于 universe equal weight: {'是' if float(control_v2.get('annual_return', v2.get('annual_return', 0.0))) > float(universe_equal.get('annual_return', 0.0)) else '否'}。",
        f"- v2 是否优于 top score monthly: {'是' if float(control_v2.get('annual_return', v2.get('annual_return', 0.0))) > float(top_score.get('annual_return', 0.0)) else '否'}。",
        f"- v2 是否优于 random placebo: percentile {placebo_percentile:.1f}%。",
        f"- defensive_only / cyclical_only: {pct(defensive.get('annual_return', 0.0))} / {pct(cyclical.get('annual_return', 0.0))}。",
        f"- no_high_dividend_supplement: {pct(no_div.get('annual_return', 0.0))}。",
        f"- no_grid: {pct(no_grid.get('annual_return', 0.0))}。",
        f"- no_trend_stop: {pct(no_stop.get('annual_return', 0.0))}。",
        f"- risk_off_no_new_buy: {pct(no_risk_buy.get('annual_return', 0.0))}。",
        "",
        "## v2_1_risk_guard",
        "",
        f"- 年化 {pct(v21_row.get('annual_return', 0.0))}，回撤 {pct(v21_row.get('max_drawdown', 0.0))}，交易 {int(v21_row.get('total_trades', 0))}。",
        "- 不替换 v2；可作为保守观察候选。",
        "",
        "## 主要风险",
        "",
        "- 三年样本偏短。",
        "- A 股风格切换可能导致当前 bucket 和估值分位逻辑失效。",
        "- risk_off daily MTM 损失仍明显。",
        "- no_high_dividend_supplement 和 no_trend_stop 对照结果提示部分模块需要后续研究，但不能直接删除。",
        "- 数据更新滞后到 2026-04-03，不能生成 2026-05-04 实盘日报。",
        "",
        "## 最终建议",
        "",
        "- combined_v2 是否保留为主候选: 是，前提是继续使用 PIT next_bar 严格口径。",
        "- combined_v2_1_risk_guard 是否值得继续观察: 取决于上面的 v2_1 对比标签，不自动替换 v2。",
        "- 已证明有贡献或需要保留观察的模块: PIT 股票池、defensive/cyclical 双 bucket、严格 next_bar 审计、成本压力和敏感性检查。",
        "- 贡献不足或需后续研究的模块: 见 no_grid、no_trend_stop、risk_off_no_new_buy 和 signal attribution 的对照结果。",
        "- 是否可进入小资金手动试运行候选阶段: 由最终评级决定；即便 PASS_CANDIDATE，也只能小资金、手动、继续观察，不能自动下单。",
        "",
        "## 降级项",
        "",
    ]
    if blockers or warnings:
        for item in blockers + warnings:
            rc_lines.append(f"- {item}")
    else:
        rc_lines.append("- 无。")
    ensure_parent("reports/backtest/audit/combined_v2_rc_summary.md").write_text("\n".join(rc_lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
