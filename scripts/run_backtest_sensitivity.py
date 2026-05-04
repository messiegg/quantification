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
    BASELINE_HISTORY_DIR,
    DEFAULT_END_DATE,
    DEFAULT_FEATURES_FILE,
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
from scripts.run_backtest_compare import _generate_v2_history, _history_generation_start


def _bump_buy_thresholds(strategy: dict, bucket: str, stock_delta: float, industry_delta: float) -> None:
    for rule in strategy["buckets"][bucket]["buy_levels"].values():
        rule["stock_q_blended_max"] = float(rule["stock_q_blended_max"]) + stock_delta
        rule["industry_q_blended_max"] = float(rule["industry_q_blended_max"]) + industry_delta


def _set_defensive_ma(strategy: dict, values: tuple[float, float, float]) -> None:
    for level, value in zip(("BUY_1", "BUY_2", "BUY_3"), values, strict=True):
        strategy["buckets"]["defensive_dividend"]["buy_levels"][level]["close_to_ma120_max"] = value


def _set_positions(strategy: dict, defensive: tuple[float, float, float], cyclical: tuple[float, float, float]) -> None:
    strategy["buckets"]["defensive_dividend"]["tranche_weights"] = {1: defensive[0], 2: defensive[1], 3: defensive[2]}
    strategy["buckets"]["defensive_dividend"]["max_single_name_weight"] = max(defensive)
    strategy["buckets"]["cyclical_rotation"]["tranche_weights"] = {1: cyclical[0], 2: cyclical[1], 3: cyclical[2]}
    strategy["buckets"]["cyclical_rotation"]["max_single_name_weight"] = max(cyclical)


def _variants(configs: dict) -> list[dict]:
    base_strategy = configs["v2_strategy"]
    base_universe = configs["v2_universe"]
    variants = [
        {
            "variant_id": "current_v2",
            "variant_group": "current",
            "changed_parameter": "current combined_v2 parameters",
            "strategy": copy.deepcopy(base_strategy),
            "universe": copy.deepcopy(base_universe),
            "history_dir": V2_HISTORY_DIR,
            "regenerate_universe": False,
        }
    ]
    for variant_id, target, floor, ceiling in (
        ("universe_small", 24, 18, 36),
        ("universe_large", 48, 36, 60),
    ):
        universe = copy.deepcopy(base_universe)
        universe.update({"target_size": target, "floor_size": floor, "ceiling_size": ceiling, "target_universe_size": target, "target_universe_floor": floor, "target_universe_ceiling": ceiling})
        variants.append({"variant_id": variant_id, "variant_group": "universe_size", "changed_parameter": f"target_size={target}, floor_size={floor}, ceiling_size={ceiling}", "strategy": copy.deepcopy(base_strategy), "universe": universe, "history_dir": f"reports/backtest/robustness/sensitivity_universe_history/{variant_id}", "regenerate_universe": True})

    for variant_id, delta in (("defensive_valuation_strict", -5), ("defensive_valuation_loose", 5)):
        strategy = copy.deepcopy(base_strategy)
        _bump_buy_thresholds(strategy, "defensive_dividend", delta, delta)
        variants.append({"variant_id": variant_id, "variant_group": "defensive_valuation_threshold", "changed_parameter": f"defensive stock/industry thresholds {delta:+}", "strategy": strategy, "universe": copy.deepcopy(base_universe), "history_dir": V2_HISTORY_DIR, "regenerate_universe": False})

    for variant_id, values in (("defensive_ma_strict", (0.98, 0.94, 0.90)), ("defensive_ma_loose", (1.02, 0.98, 0.94))):
        strategy = copy.deepcopy(base_strategy)
        _set_defensive_ma(strategy, values)
        variants.append({"variant_id": variant_id, "variant_group": "defensive_ma120_trigger", "changed_parameter": f"close_to_ma120={values}", "strategy": strategy, "universe": copy.deepcopy(base_universe), "history_dir": V2_HISTORY_DIR, "regenerate_universe": False})

    for variant_id, delta in (("cyclical_pb_strict", -5), ("cyclical_pb_loose", 5)):
        strategy = copy.deepcopy(base_strategy)
        _bump_buy_thresholds(strategy, "cyclical_rotation", delta, delta)
        variants.append({"variant_id": variant_id, "variant_group": "cyclical_pb_threshold", "changed_parameter": f"cyclical PB stock/industry thresholds {delta:+}", "strategy": strategy, "universe": copy.deepcopy(base_universe), "history_dir": V2_HISTORY_DIR, "regenerate_universe": False})

    for variant_id, trim, exit_ in (("holding_shorter", 30, 45), ("holding_longer", 60, 90)):
        strategy = copy.deepcopy(base_strategy)
        strategy["execution"]["min_holding_days_for_soft_trim"] = trim
        strategy["execution"]["min_holding_days_for_soft_exit"] = exit_
        variants.append({"variant_id": variant_id, "variant_group": "min_holding_days", "changed_parameter": f"soft_trim={trim}, soft_exit={exit_}", "strategy": strategy, "universe": copy.deepcopy(base_universe), "history_dir": V2_HISTORY_DIR, "regenerate_universe": False})

    for variant_id, atr, min_step, max_step in (("grid_tighter", 1.0, 0.03, 0.07), ("grid_wider", 1.5, 0.04, 0.09)):
        strategy = copy.deepcopy(base_strategy)
        grid = strategy["execution"]["grid_execution"]
        grid["atr_multiplier"] = atr
        grid["min_step"] = min_step
        grid["max_step"] = max_step
        variants.append({"variant_id": variant_id, "variant_group": "grid_step", "changed_parameter": f"clip({atr}*ATR20/close,{min_step},{max_step})", "strategy": strategy, "universe": copy.deepcopy(base_universe), "history_dir": V2_HISTORY_DIR, "regenerate_universe": False})

    for variant_id, defensive, cyclical in (("position_conservative", (0.03, 0.06, 0.09), (0.02, 0.04, 0.06)), ("position_aggressive", (0.05, 0.10, 0.12), (0.04, 0.08, 0.09))):
        strategy = copy.deepcopy(base_strategy)
        _set_positions(strategy, defensive, cyclical)
        variants.append({"variant_id": variant_id, "variant_group": "position_sizing", "changed_parameter": f"defensive={defensive}, cyclical={cyclical}", "strategy": strategy, "universe": copy.deepcopy(base_universe), "history_dir": V2_HISTORY_DIR, "regenerate_universe": False})
    return variants


def main() -> int:
    configs = load_audit_configs()
    prepare_v2_history(configs)
    features = load_feature_window(DEFAULT_START_DATE, DEFAULT_END_DATE)
    benchmark = load_benchmark_window(DEFAULT_START_DATE, DEFAULT_END_DATE)
    generation_start = _history_generation_start(BASELINE_HISTORY_DIR, DEFAULT_START_DATE, DEFAULT_END_DATE)
    generation_features = load_feature_window(generation_start, DEFAULT_END_DATE, DEFAULT_FEATURES_FILE)

    baseline = run_profile("baseline", features, benchmark, configs, execution_mode="next_bar")
    baseline_annual = float(baseline.metrics["annual_return"])
    rows = []
    for variant in _variants(configs):
        if variant["regenerate_universe"]:
            _generate_v2_history(generation_features, BASELINE_HISTORY_DIR, variant["history_dir"], variant["universe"], configs["metric_map"])
        result = run_profile(
            "combined_v2",
            features,
            benchmark,
            configs,
            execution_mode="next_bar",
            historical_universe_dir=variant["history_dir"],
            strategy_cfg=variant["strategy"],
            universe_cfg=variant["universe"],
        )
        row = metrics_row("combined_v2", "next_bar", result, benchmark)
        row.update({"variant_id": variant["variant_id"], "variant_group": variant["variant_group"], "changed_parameter": variant["changed_parameter"], "baseline_annual_return": baseline_annual})
        rows.append(row)
    frame = pd.DataFrame(rows)
    columns = [
        "variant_id",
        "variant_group",
        "changed_parameter",
        "annual_return",
        "cumulative_return",
        "max_drawdown",
        "sharpe",
        "total_trades",
        "avg_daily_exposure",
        "benchmark_annual_return",
        "excess_annual_return",
        "defensive_pnl",
        "cyclical_pnl",
        "baseline_annual_return",
    ]
    frame = frame.reindex(columns=columns)
    frame.to_csv(ensure_parent("reports/backtest/robustness/sensitivity_metrics.csv"), index=False)

    non_current = frame[frame["variant_id"] != "current_v2"].copy()
    positive_after_tighten = non_current[non_current["variant_id"].str.contains("strict|conservative|tighter")]["annual_return"].gt(0).all()
    loose_drawdown_ok = non_current[non_current["variant_id"].str.contains("loose|aggressive|wider")]["max_drawdown"].ge(-0.18).all()
    near_zero_count = int((non_current["annual_return"].abs() < 0.01).sum())
    under_baseline_count = int((non_current["annual_return"] <= baseline_annual).sum())
    overfit_risk = near_zero_count > len(non_current) / 2 or under_baseline_count > len(non_current) / 2

    lines = [
        "# 参数敏感性测试",
        "",
        "- 口径: combined_v2 next_bar，固定 2023-04-03 到 2026-04-03。",
        "- 这是 one-at-a-time 扰动，不做参数优化，不输出最佳参数，不写回正式配置。",
        f"- baseline next_bar 年化: {pct(baseline_annual)}",
        f"- 小幅收紧后是否仍有正收益: {'是' if positive_after_tighten else '否'}",
        f"- 小幅放宽后是否回撤失控: {'否' if loose_drawdown_ok else '是'}",
        f"- 年化接近 0 的变体数: {near_zero_count}/{len(non_current)}",
        f"- 跑输 baseline 的变体数: {under_baseline_count}/{len(non_current)}",
        f"- 过拟合风险标记: {'是' if overfit_risk else '否'}",
        "",
        "## 变体结果",
        "",
    ]
    for row in frame.to_dict(orient="records"):
        lines.append(f"- {row['variant_id']}: 年化 {pct(row['annual_return'])}，累计 {pct(row['cumulative_return'])}，回撤 {pct(row['max_drawdown'])}，夏普 {row['sharpe']:.2f}，成交 {int(row['total_trades'])}，平均仓位 {pct(row['avg_daily_exposure'])}")
    ensure_parent("reports/backtest/robustness/sensitivity_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
