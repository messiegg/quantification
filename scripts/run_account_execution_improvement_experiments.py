#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.audit_common import (
    DEFAULT_BENCHMARK_FILE,
    DEFAULT_END_DATE,
    DEFAULT_FEATURES_FILE,
    DEFAULT_START_DATE,
    V2_HISTORY_DIR,
    load_audit_configs,
    load_benchmark_window,
    load_feature_window,
    prepare_v2_history,
    run_profile,
)
from scripts.build_account_constraints_report import build_account_constraints_report
from scripts.build_account_suitability_report import build_account_suitability_report
from scripts.report_metadata import config_hash, data_hash, stable_hash
from scripts.run_account_profile_backtests import _apply_strategy_execution, _metrics_payload, _write_effective_configs
from src.strategy.backtest_reports import build_universe_funnel, write_diagnostic_outputs
from src.utils.config import load_yaml, resolve_path


OUT_ROOT = "reports/backtest/account_profiles/executable_raw_experiments"
SUMMARY_JSON = "reports/backtest/account_profiles/executable_raw_improvement_report.json"
SUMMARY_CSV = "reports/backtest/account_profiles/executable_raw_improvement_metrics.csv"
SUMMARY_MD = "reports/backtest/account_profiles/executable_raw_improvement_report.md"


@dataclass(frozen=True)
class Experiment:
    variant_id: str
    category: str
    description: str
    account_overrides: dict[str, Any] = field(default_factory=dict)
    sizing_overrides: dict[str, Any] = field(default_factory=dict)
    execution_overrides: dict[str, Any] = field(default_factory=dict)
    strategy_execution_overrides: dict[str, Any] = field(default_factory=dict)
    recommendation_class: str = "research_only"
    release_eligible: bool = False


def _deepcopy_yaml(path: str) -> dict[str, Any]:
    return copy.deepcopy(load_yaml(path))


def _base_account() -> dict[str, Any]:
    account = _deepcopy_yaml("config/account_profiles/retail_50k_lot_aware.yml")
    account["research_only"] = True
    account["candidate_default"] = False
    return account


def _base_strategy(configs: dict[str, Any]) -> dict[str, Any]:
    execution = _deepcopy_yaml("config/strategy_profiles/retail_50k_lot_aware_execution.yml").get("execution", {})
    strategy = _apply_strategy_execution(configs["v2_strategy"], execution)
    strategy["research_only"] = True
    return strategy


def _apply_experiment(configs: dict[str, Any], experiment: Experiment) -> tuple[dict[str, Any], dict[str, Any]]:
    account = _base_account()
    strategy = _base_strategy(configs)
    account["profile_name"] = experiment.variant_id
    account["account_profile"] = experiment.variant_id
    account["research_only"] = True
    account["candidate_default"] = False
    strategy["profile_name"] = experiment.variant_id
    strategy["research_only"] = True

    account_values = account.setdefault("account", {})
    account_values.update(experiment.account_overrides)
    if "initial_capital" in experiment.account_overrides:
        capital = float(experiment.account_overrides["initial_capital"])
        account_values.setdefault("current_cash", capital)
        account_values.setdefault("latest_total_equity", capital)

    account.setdefault("position_sizing", {}).update(experiment.sizing_overrides)
    account.setdefault("execution", {}).update(experiment.execution_overrides)

    strategy_execution = strategy.setdefault("execution", {})
    strategy_execution.update(experiment.strategy_execution_overrides)
    if "min_trade_value" in experiment.sizing_overrides:
        strategy_execution["min_trade_value"] = experiment.sizing_overrides["min_trade_value"]
    if "round_lot" in experiment.execution_overrides:
        strategy_execution["round_lot"] = experiment.execution_overrides["round_lot"]
    return account, strategy


def _experiments() -> list[Experiment]:
    return [
        Experiment(
            "baseline_50k_lot_aware",
            "baseline",
            "当前 50k lot-aware release/default 研究复现口径。",
            recommendation_class="current_default_reference",
            release_eligible=True,
        ),
        Experiment(
            "no_lot_aware_50k",
            "execution_mechanism",
            "关闭 lot-aware 和 pending，观察整手前置规划本身的贡献。",
            strategy_execution_overrides={"lot_aware_sizing": False, "pending_add_state": False, "duplicate_blocked_signal_suppression": False},
        ),
        Experiment(
            "min_trade_1000_50k",
            "min_trade_value",
            "把最小成交额从 1500 降到 1000，隔离最小成交额门槛影响。",
            sizing_overrides={"min_trade_value": 1000},
        ),
        Experiment(
            "min_trade_500_50k",
            "min_trade_value",
            "把最小成交额从 1500 降到 500，作为最小成交额敏感性上限。",
            sizing_overrides={"min_trade_value": 500},
        ),
        Experiment(
            "capital_100k_lot_aware",
            "capital_scale",
            "本金、现金、权益同步提高到 100k，其他 50k lot-aware 执行规则保持不变。",
            account_overrides={"initial_capital": 100000, "current_cash": 100000, "latest_total_equity": 100000},
        ),
        Experiment(
            "capital_200k_lot_aware",
            "capital_scale",
            "本金、现金、权益同步提高到 200k，其他 50k lot-aware 执行规则保持不变。",
            account_overrides={"initial_capital": 200000, "current_cash": 200000, "latest_total_equity": 200000},
        ),
        Experiment(
            "daily_limits_3_5",
            "daily_limits",
            "每日新开 3 只、加仓 5 次，作为日内节流放宽上限。",
            strategy_execution_overrides={"max_new_positions_per_day": 3, "max_adds_per_day": 5},
        ),
        Experiment(
            "max_positions_12_50k",
            "portfolio_capacity",
            "50k 下把最大持仓数从 8 提到 12，测试 MAX_POSITIONS_LIMIT 是否主导 raw 分母。",
            strategy_execution_overrides={"max_positions": 12, "equal_weight_target_universe_size": 12},
            recommendation_class="more_positions_same_capital",
        ),
        Experiment(
            "max_positions_20_50k",
            "portfolio_capacity",
            "50k 下把最大持仓数从 8 提到 20，作为固定本金下持仓容量上限。",
            strategy_execution_overrides={"max_positions": 20, "equal_weight_target_universe_size": 20},
            recommendation_class="more_positions_same_capital",
        ),
        Experiment(
            "capital_200k_maxpos20",
            "capital_and_capacity",
            "本金 200k 且最大持仓 20，测试资金规模和持仓容量同时放宽后的可执行上限。",
            account_overrides={"initial_capital": 200000, "current_cash": 200000, "latest_total_equity": 200000},
            strategy_execution_overrides={"max_positions": 20, "equal_weight_target_universe_size": 20, "max_new_positions_per_day": 3, "max_adds_per_day": 5},
            recommendation_class="research_only_reference_scale",
        ),
        Experiment(
            "max_single_20pct",
            "single_name_capacity",
            "单票上限提高到 20%，作为单票容量放宽上限。",
            sizing_overrides={"max_single_stock_weight": 0.20},
            recommendation_class="high_concentration",
        ),
        Experiment(
            "tranche_5_10_15_max15",
            "position_sizing",
            "目标分层 5%/10%/15%，单票上限 15%，测试更少更大的单票执行。",
            sizing_overrides={"tranche_weights": {1: 0.05, 2: 0.10, 3: 0.15}, "max_single_stock_weight": 0.15},
            strategy_execution_overrides={"max_positions": 6, "equal_weight_target_universe_size": 6},
            recommendation_class="higher_concentration",
        ),
        Experiment(
            "round_lot_1_upper_bound",
            "invalid_upper_bound",
            "取消 100 股整手约束的理论上限，仅用于估计整手制度造成的最大损耗。",
            execution_overrides={"round_lot": 1},
            strategy_execution_overrides={"round_lot": 1},
            recommendation_class="invalid_for_a_share",
        ),
    ]


def _write_variant_report(out_dir: Path, payload: dict[str, Any]) -> None:
    (out_dir / "metrics.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    pd.DataFrame([payload]).to_csv(out_dir / "metrics.csv", index=False)


def _numeric(value: object, default: float = 0.0) -> float:
    try:
        if value is None or pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _ratio_text(value: object) -> str:
    if value is None or pd.isna(value):
        return "None"
    return f"{float(value):.2%}"


def _summary_row(payload: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    ratio = _numeric(payload.get("executable_raw_buy_ratio"))
    base_ratio = _numeric(baseline.get("executable_raw_buy_ratio"))
    executable = int(payload.get("executable_buy_count") or 0)
    base_executable = int(baseline.get("executable_buy_count") or 0)
    max_dd = _numeric(payload.get("max_drawdown"))
    base_dd = _numeric(baseline.get("max_drawdown"))
    return {
        "variant": payload["profile_id"],
        "category": payload["experiment_category"],
        "description": payload["experiment_description"],
        "recommendation_class": payload["recommendation_class"],
        "release_eligible": bool(payload["release_eligible"]),
        "initial_capital": payload.get("initial_capital"),
        "min_trade_value": payload.get("min_trade_value"),
        "round_lot": payload.get("round_lot"),
        "max_single_stock_weight": payload.get("max_single_stock_weight"),
        "tranche_weights": payload.get("tranche_weights"),
        "portfolio_max_positions": payload.get("portfolio_max_positions"),
        "max_new_positions_per_day": payload.get("max_new_positions_per_day"),
        "max_adds_per_day": payload.get("max_adds_per_day"),
        "lot_aware_sizing": payload.get("lot_aware_sizing"),
        "pending_add_state_enabled": payload.get("pending_add_state_enabled"),
        "raw_buy_signal_count": payload.get("raw_buy_signal_count"),
        "unique_raw_buy_intent_count": payload.get("unique_raw_buy_intent_count"),
        "repeat_raw_buy_intent_count": payload.get("repeat_raw_buy_intent_count"),
        "repeat_raw_buy_intent_ratio": payload.get("repeat_raw_buy_intent_ratio"),
        "account_feasible_buy_signal_count": payload.get("account_feasible_buy_signal_count"),
        "executable_buy_count": executable,
        "executable_new_position_buy_count": payload.get("executable_new_position_buy_count"),
        "executable_add_buy_count": payload.get("executable_add_buy_count"),
        "executable_raw_buy_ratio": payload.get("executable_raw_buy_ratio"),
        "executable_unique_raw_intent_ratio": payload.get("executable_unique_raw_intent_ratio"),
        "delta_executable_raw_buy_ratio": ratio - base_ratio,
        "delta_executable_buy_count": executable - base_executable,
        "executable_account_feasible_buy_ratio": payload.get("executable_account_feasible_buy_ratio"),
        "pending_buy_intent_count": payload.get("pending_buy_intent_count"),
        "full_portfolio_raw_buy_intent_count": payload.get("full_portfolio_raw_buy_intent_count"),
        "full_portfolio_raw_buy_intent_ratio": payload.get("full_portfolio_raw_buy_intent_ratio"),
        "new_position_raw_intent_count": payload.get("new_position_raw_intent_count"),
        "add_position_raw_intent_count": payload.get("add_position_raw_intent_count"),
        "lot_size_zero_block_count": payload.get("lot_size_zero_block_count"),
        "price_too_high_for_account_lot_count": payload.get("price_too_high_for_account_lot_count"),
        "cash_insufficient_for_one_lot_count": payload.get("cash_insufficient_for_one_lot_count"),
        "lot_size_accumulation_required_count": payload.get("lot_size_accumulation_required_count"),
        "max_positions_block_ratio": payload.get("max_positions_block_ratio"),
        "cash_block_ratio": payload.get("cash_block_ratio"),
        "annual_return": payload.get("annual_return"),
        "cumulative_return": payload.get("cumulative_return"),
        "max_drawdown": payload.get("max_drawdown"),
        "delta_max_drawdown": max_dd - base_dd,
        "average_exposure": payload.get("average_exposure"),
        "max_exposure": payload.get("max_exposure"),
        "average_positions": payload.get("average_positions"),
        "max_positions_seen": payload.get("max_positions_seen"),
        "turnover": payload.get("turnover"),
        "transaction_cost_as_pct_of_initial_capital": payload.get("transaction_cost_as_pct_of_initial_capital"),
        "buy_trades": payload.get("buy_trades"),
        "total_trades": payload.get("total_trades"),
        "status": payload.get("status"),
        "warnings": payload.get("warnings"),
        "violations": payload.get("violations"),
    }


def _top(rows: list[dict[str, Any]], *, include_invalid: bool = False, only_50k: bool = False) -> dict[str, Any]:
    candidates = []
    for row in rows:
        if not include_invalid and row["category"] == "invalid_upper_bound":
            continue
        if only_50k and int(float(row.get("initial_capital") or 0)) != 50000:
            continue
        candidates.append(row)
    if not candidates:
        return {}
    return max(candidates, key=lambda item: _numeric(item.get("executable_raw_buy_ratio")))


def _write_summary(payload: dict[str, Any]) -> None:
    json_path = resolve_path(SUMMARY_JSON)
    csv_path = resolve_path(SUMMARY_CSV)
    md_path = resolve_path(SUMMARY_MD)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    pd.DataFrame(payload["rows"]).to_csv(csv_path, index=False)

    rows = sorted(payload["rows"], key=lambda item: _numeric(item.get("executable_raw_buy_ratio")), reverse=True)
    baseline = payload["baseline"]
    best_valid = payload["best_valid"]
    best_50k = payload["best_50k_realistic"]
    best_any = payload["best_any_including_invalid"]
    lines = [
        "# executable/raw 改善实验报告",
        "",
        "- status: RESEARCH_ONLY",
        "- default_release_profile_unchanged: actual_50k_lot_aware",
        "- release_account_profile_unchanged: retail_50k_lot_aware",
        "- auto_trading_approved: false",
        "- broker_integration_enabled: false",
        "- llm_decision_allowed: false",
        "- not production ready",
        f"- baseline_exec_raw: {_ratio_text(baseline.get('executable_raw_buy_ratio'))}",
        f"- best_valid_variant: {best_valid.get('variant')} ({_ratio_text(best_valid.get('executable_raw_buy_ratio'))})",
        f"- best_50k_realistic_variant: {best_50k.get('variant')} ({_ratio_text(best_50k.get('executable_raw_buy_ratio'))})",
        f"- best_any_including_invalid: {best_any.get('variant')} ({_ratio_text(best_any.get('executable_raw_buy_ratio'))})",
        "",
        "## 结论",
        "",
        (
            f"- 当前默认 50k lot-aware 为基线，executable/raw={_ratio_text(baseline.get('executable_raw_buy_ratio'))}，"
            f"executable={baseline.get('executable_buy_count')}。"
        ),
        (
            f"- 不含取消整手的有效实验里，最高的是 {best_valid.get('variant')}，"
            f"executable/raw={_ratio_text(best_valid.get('executable_raw_buy_ratio'))}，"
            f"比基线提高 {_ratio_text(best_valid.get('delta_executable_raw_buy_ratio'))}。"
        ),
        (
            f"- 仍限定 50k 和 100 股整手时，最高的是 {best_50k.get('variant')}，"
            f"executable/raw={_ratio_text(best_50k.get('executable_raw_buy_ratio'))}，"
            f"recommendation_class={best_50k.get('recommendation_class')}。"
        ),
        (
            f"- {best_any.get('variant')} 是理论上限，因为它取消 100 股整手约束；"
            "该结果不能作为 A 股默认 release 口径。"
            if best_any.get("category") == "invalid_upper_bound"
            else "- 理论上限实验没有超过有效实验。"
        ),
        "",
        "## 50k feasibility conclusion",
        "",
        "- 当前 50k lot-aware 默认 profile 不应升级为 PASS；默认 executable/raw 仍显著低于 25% guard。",
        "- 低风险参数修改不能把 executable/raw 推近 25%；降低最小成交额、提高单票上限、放宽日内限制在本轮都没有形成有效改善。",
        "- max_positions_20_50k 虽然提高执行率，但通过显著提高暴露和回撤换来，不应作为低风险修复。",
        "- capital_200k_maxpos20 是研究上限，不是默认 release 方案，也不能替代 50k lot-aware 默认口径。",
        "- 取消整手约束是无效的 A 股理论上限测试，不能作为实盘方案。",
        "- 下一步如果坚持 50k，应优先做 observation/paper trading，而不是继续参数放宽。",
        "- 如果要实盘化，应考虑提高资金规模、降低目标股票数、重新设计专门适配 50k 的候选池，或接受这是研究/观察系统而不是 50k 可执行交易系统。",
        "",
        "## 排名表",
        "",
        "| rank | variant | category | class | capital | min_trade | lot | max_single | max_pos | raw | feasible | executable | exec/raw | delta | max_dd | exposure | status |",
        "|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for idx, row in enumerate(rows, start=1):
        lines.append(
            "| {rank} | {variant} | {category} | {klass} | {capital} | {min_trade} | {lot} | {max_single} | {max_pos} | "
            "{raw} | {feasible} | {executable} | {ratio} | {delta} | {max_dd} | {exposure} | {status} |".format(
                rank=idx,
                variant=row["variant"],
                category=row["category"],
                klass=row["recommendation_class"],
                capital=row["initial_capital"],
                min_trade=row["min_trade_value"],
                lot=row["round_lot"],
                max_single=row["max_single_stock_weight"],
                max_pos=row["portfolio_max_positions"],
                raw=row["raw_buy_signal_count"],
                feasible=row["account_feasible_buy_signal_count"],
                executable=row["executable_buy_count"],
                ratio=_ratio_text(row["executable_raw_buy_ratio"]),
                delta=_ratio_text(row["delta_executable_raw_buy_ratio"]),
                max_dd=f"{_numeric(row['max_drawdown']):.2%}",
                exposure=f"{_numeric(row['max_exposure']):.2%}",
                status=row["status"],
            )
        )
    lines.extend(
        [
            "",
            "## 方法判断",
            "",
            "- 提高本金本身会改善一手可买性；如果同时提高最大持仓容量，才会显著缓解 MAX_POSITIONS_LIMIT 对 raw 分母的压制。",
            "- 本轮结果显示，50k 内部单独降低最小成交额、提高单票上限或放宽每日新开/加仓次数，改善都很有限；主瓶颈不是 1500 元最小成交额。",
            "- 目标分层放大可能增加可行信号，但也会抬高 raw 分母和集中度，不等于 executable/raw 变好。",
            "- 取消整手约束只能说明理论损耗上限，不是可落地方案。",
            "- 本报告只评估账户执行约束，不新增策略想法，不改变 action_enum 的规则驱动来源。",
        ]
    )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_experiments(
    *,
    start_date: str = DEFAULT_START_DATE,
    end_date: str = DEFAULT_END_DATE,
    features_file: str = DEFAULT_FEATURES_FILE,
    benchmark_file: str = DEFAULT_BENCHMARK_FILE,
    output_root: str = OUT_ROOT,
    reuse_existing: bool = False,
) -> dict[str, Any]:
    configs = load_audit_configs()
    prepare_v2_history(configs, end_date=end_date, features_file=features_file, start_date=start_date)
    features = load_feature_window(start_date, end_date, features_file)
    benchmark = load_benchmark_window(start_date, end_date, benchmark_file)
    universe, scores = build_universe_funnel(features, V2_HISTORY_DIR, configs["v2_universe"], configs["metric_map"])
    out_root = resolve_path(output_root)
    out_root.mkdir(parents=True, exist_ok=True)

    payloads: list[dict[str, Any]] = []
    for experiment in _experiments():
        out_dir = out_root / experiment.variant_id
        out_dir.mkdir(parents=True, exist_ok=True)
        metrics_path = out_dir / "metrics.json"
        if reuse_existing and metrics_path.exists():
            cached = json.loads(metrics_path.read_text(encoding="utf-8"))
            if "executable_unique_raw_intent_ratio" in cached and "block_reason_breakdown" in cached:
                payloads.append(cached)
                continue
        account, strategy = _apply_experiment(configs, experiment)
        account_path, strategy_path = _write_effective_configs(out_dir, account, strategy)
        result = run_profile(
            "combined_v2",
            features,
            benchmark,
            configs,
            execution_mode="next_bar",
            historical_universe_dir=V2_HISTORY_DIR,
            strategy_cfg=strategy,
            universe_cfg=configs["v2_universe"],
            account_cfg=account,
        )
        paths = write_diagnostic_outputs(experiment.variant_id, result, universe, output_dir=out_dir, candidate_scores=scores)
        result.nav.to_csv(out_dir / "equity_curve.csv", index=False)
        (result.trade_list if result.trade_list is not None else pd.DataFrame()).to_csv(out_dir / "trade_list.csv", index=False)
        account_report = build_account_constraints_report(
            signal_funnel_path=str(paths["signal_funnel"].relative_to(ROOT)),
            blocked_signals_path=str(paths["blocked_signals"].relative_to(ROOT)),
            trades_path=str(paths["trades_detailed"].relative_to(ROOT)),
            account_config=str(account_path.relative_to(ROOT)),
            strategy_config=str(strategy_path.relative_to(ROOT)),
            output_json=str((out_dir / "account_constraints_report.json").relative_to(ROOT)),
            output_md=str((out_dir / "account_constraints_report.md").relative_to(ROOT)),
            write_report=True,
        )
        build_account_suitability_report(
            account_config=str(account_path.relative_to(ROOT)),
            strategy_config=str(strategy_path.relative_to(ROOT)),
            signal_funnel_path=str(paths["signal_funnel"].relative_to(ROOT)),
            blocked_signals_path=str(paths["blocked_signals"].relative_to(ROOT)),
            trades_path=str(paths["trades_detailed"].relative_to(ROOT)),
            output_json=str((out_dir / "account_suitability_report.json").relative_to(ROOT)),
            output_md=str((out_dir / "account_suitability_report.md").relative_to(ROOT)),
            write_report=True,
        )
        payload = _metrics_payload(
            profile_id=experiment.variant_id,
            result=result,
            account=account,
            strategy=strategy,
            account_report=account_report,
            account_config_path=account_path,
            strategy_config_path=strategy_path,
            start_date=start_date,
            end_date=end_date,
            research_only=True,
            account_profile_path=str(account_path.relative_to(ROOT)),
            strategy_profile_path=str(strategy_path.relative_to(ROOT)),
        )
        payload.update(
            {
                "experiment_category": experiment.category,
                "experiment_description": experiment.description,
                "recommendation_class": experiment.recommendation_class,
                "release_eligible": bool(experiment.release_eligible),
                "max_single_stock_weight": account.get("position_sizing", {}).get("max_single_stock_weight"),
                "tranche_weights": account.get("position_sizing", {}).get("tranche_weights"),
                "max_new_positions_per_day": strategy.get("execution", {}).get("max_new_positions_per_day"),
                "max_adds_per_day": strategy.get("execution", {}).get("max_adds_per_day"),
                "profile_config_hash": stable_hash({"experiment": experiment.variant_id, "account": account, "strategy_execution": strategy.get("execution", {})}),
                "config_hash": config_hash([account_path, strategy_path, "config/universe_rules_v2.yml", "config/metric_map.yml"]),
                "data_hash": data_hash(),
            }
        )
        _write_variant_report(out_dir, payload)
        payloads.append(payload)

    baseline = next(item for item in payloads if item["profile_id"] == "baseline_50k_lot_aware")
    rows = [_summary_row(item, baseline) for item in payloads]
    summary = {
        "status": "RESEARCH_ONLY",
        "start_date": start_date,
        "end_date": end_date,
        "output_root": output_root,
        "default_release_profile_unchanged": "actual_50k_lot_aware",
        "release_account_profile_unchanged": "retail_50k_lot_aware",
        "auto_trading_approved": False,
        "broker_integration_enabled": False,
        "llm_decision_allowed": False,
        "not_production_ready": True,
        "baseline": next(row for row in rows if row["variant"] == "baseline_50k_lot_aware"),
        "best_valid": _top(rows, include_invalid=False),
        "best_50k_realistic": _top(rows, include_invalid=False, only_50k=True),
        "best_any_including_invalid": _top(rows, include_invalid=True),
        "rows": rows,
    }
    _write_summary(summary)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run research-only executable/raw improvement experiments for combined_v2.")
    parser.add_argument("--start-date", default=DEFAULT_START_DATE)
    parser.add_argument("--end-date", default=DEFAULT_END_DATE)
    parser.add_argument("--features-file", default=DEFAULT_FEATURES_FILE)
    parser.add_argument("--benchmark-file", default=DEFAULT_BENCHMARK_FILE)
    parser.add_argument("--output-root", default=OUT_ROOT)
    parser.add_argument("--reuse-existing", action="store_true", help="Reuse completed per-variant metrics.json files.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_experiments(
        start_date=args.start_date,
        end_date=args.end_date,
        features_file=args.features_file,
        benchmark_file=args.benchmark_file,
        output_root=args.output_root,
        reuse_existing=args.reuse_existing,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
