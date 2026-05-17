#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.audit_common import DEFAULT_END_DATE, DEFAULT_START_DATE, load_audit_configs, load_benchmark_window, load_feature_window
from scripts.run_50k_core_experiments import (
    DEFAULT_EVALUATION,
    CoreParams,
    _params_from_config,
    _prepare_feature_by_date,
    _pct,
    _safe_float,
    evaluate_hard_conditions,
    evaluate_neighborhood_robustness,
    run_core_backtest,
)
from src.utils.config import load_yaml, resolve_path


CONFIG_PATH = "config/strategy_v2_50k_core.yml"
STAGE1_DIR = "reports/backtest/50k_core"
OUT_DIR = "reports/backtest/50k_core/repair"
MAX_REPAIR_VARIANTS = 24

REQUIRED_REPAIR_OUTPUTS = [
    "repair_experiment_metrics.csv",
    "repair_experiment_report.md",
    "repair_best_candidate.yml",
    "repair_observation_candidate.md",
    "repair_neighborhood_robustness.md",
    "repair_comparison_vs_stage1.md",
    "repair_warnings.json",
]


@dataclass(frozen=True)
class RepairVariant:
    name: str
    params: CoreParams
    mechanism: str
    research_only: bool = True
    auto_trading_approved: bool = False
    broker_integration_enabled: bool = False
    llm_decision_allowed: bool = False
    writes_real_trades: bool = False
    release_profile_replacement: bool = False


def _base_params() -> CoreParams:
    return CoreParams(
        max_positions=5,
        max_tranches=1,
        target_universe_size=8,
        cash_reserve_ratio=0.10,
        max_single_stock_weight=0.18,
        max_new_positions_per_day=1,
        max_adds_per_day=0,
        industry_max_positions=2,
        defensive_core_min_positions=3,
        cyclical_max_positions=0,
        lot_notional_max_ratio_to_target_budget=1.00,
        score_gap_threshold=8,
        max_replacements_per_month=1,
        risk_on_target_exposure=0.85,
        neutral_target_exposure=0.60,
        risk_off_target_exposure=0.25,
        module_control="disable_both",
        replacement_enabled=True,
        cyclical_overlay_enabled=True,
        repair_label="stage2_base",
    )


def _with(base: CoreParams, label: str, mechanism: str, **overrides: Any) -> RepairVariant:
    params = CoreParams(**{**base.__dict__, **overrides, "repair_label": label})
    return RepairVariant(name=params.variant_id, params=params, mechanism=mechanism)


def build_repair_variants() -> list[RepairVariant]:
    base = _base_params()
    variants: list[RepairVariant] = []
    variants.append(_with(base, "monthly_review", "risk_on_cash_utilization", monthly_rebalance_review_enabled=True, target_cash_ratio=0.35))
    for gap in [6, 8, 10]:
        for min_days in [20, 40]:
            for rpm in [1, 2]:
                variants.append(
                    _with(
                        base,
                        f"rep_gap{gap}_hold{min_days}_rpm{rpm}",
                        "replacement_repair",
                        score_gap_threshold=gap,
                        min_holding_days_before_replacement=min_days,
                        max_replacements_per_month=rpm,
                    )
                )
    variants.extend(
        [
            _with(
                base,
                "partial_derisk_hardtrend",
                "partial_derisk",
                partial_derisk_enabled=True,
                module_control="disable_high_dividend_supplement",
            ),
            _with(base, "cyclical_watch_only", "cyclical_sleeve", cyclical_max_positions=0, cyclical_overlay_enabled=False),
            _with(base, "cyclical_one_strict", "cyclical_sleeve", cyclical_max_positions=1, cyclical_overlay_enabled=True),
            _with(base, "disable_both_control", "module_control", module_control="disable_both"),
        ]
    )
    dedup: list[RepairVariant] = []
    seen: set[str] = set()
    for item in variants:
        if item.name not in seen:
            dedup.append(item)
            seen.add(item.name)
    return dedup[:MAX_REPAIR_VARIANTS]


def _public_row(row: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if not key.startswith("_")}


def _score_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    public = []
    for row in rows:
        payload = _public_row(row)
        payload.update(evaluate_hard_conditions(payload, DEFAULT_EVALUATION))
        public.append(payload)
    frame = pd.DataFrame(public)
    if frame.empty:
        return frame
    return frame.sort_values(["pass_hard_conditions", "annual_return", "sharpe", "max_drawdown"], ascending=[False, False, False, False]).reset_index(drop=True)


def _stage1_best(stage1_dir: str | Path = STAGE1_DIR) -> dict[str, Any]:
    path = resolve_path(Path(stage1_dir) / "core_experiment_metrics.csv")
    if not path.exists():
        return {}
    frame = pd.read_csv(path)
    if frame.empty:
        return {}
    return frame.sort_values(["annual_return", "sharpe", "max_drawdown"], ascending=[False, False, False]).iloc[0].to_dict()


def write_repair_outputs(rows: list[dict[str, Any]], stage1_best: dict[str, Any] | None = None, output_dir: str | Path | None = None) -> dict[str, Any]:
    out_dir = resolve_path(output_dir or OUT_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    frame = _score_frame(rows)
    frame.to_csv(out_dir / "repair_experiment_metrics.csv", index=False)
    candidates = frame[frame["pass_hard_conditions"].astype(bool)] if not frame.empty else pd.DataFrame()
    best = candidates.iloc[0].to_dict() if not candidates.empty else (frame.iloc[0].to_dict() if not frame.empty else {})
    hard_best = candidates.iloc[0].to_dict() if not candidates.empty else {}
    neighbors = [row for row in frame.to_dict(orient="records") if row.get("variant") != best.get("variant")][:8] if best else []
    robustness = evaluate_neighborhood_robustness(hard_best or best, neighbors, DEFAULT_EVALUATION) if best else {"status": "FRAGILE", "neighbor_count": 0, "support_count_excluding_best": 0, "neighbors": []}
    summary = {
        "status": "HAS_REPAIR_CANDIDATE" if hard_best else "NO_REPAIR_CANDIDATE",
        "experiment_count": int(len(frame)),
        "hard_condition_pass_count": int(len(candidates)),
        "best_candidate": hard_best or best,
        "robustness": robustness["status"],
        "research_only": True,
        "release_profile_replacement": False,
        "auto_trading_approved": False,
        "broker_integration_enabled": False,
        "llm_decision_allowed": False,
        "writes_real_trades": False,
    }
    (out_dir / "repair_best_candidate.yml").write_text(yaml.safe_dump(hard_best or {"status": "NO_REPAIR_CANDIDATE", "closest_attempt": best}, allow_unicode=True, sort_keys=False), encoding="utf-8")
    _write_report(out_dir / "repair_experiment_report.md", frame, summary, stage1_best or {})
    _write_observation(out_dir / "repair_observation_candidate.md", hard_best, summary)
    _write_robustness(out_dir / "repair_neighborhood_robustness.md", robustness)
    _write_comparison(out_dir / "repair_comparison_vs_stage1.md", best, stage1_best or {})
    warnings = {
        "research_only": True,
        "auto_trading_approved": False,
        "release_profile_replacement": False,
        "hard_condition_pass_count": int(len(candidates)),
        "repair_variant_count": int(len(frame)),
        "notes": [
            "future_return diagnostics are not used in repair execution",
            "repair overlays do not change default release profile",
        ],
    }
    (out_dir / "repair_warnings.json").write_text(json.dumps(warnings, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    missing = [name for name in REQUIRED_REPAIR_OUTPUTS if not (out_dir / name).exists()]
    if missing:
        raise RuntimeError(f"missing repair outputs: {missing}")
    return summary


def _write_report(path: Path, frame: pd.DataFrame, summary: dict[str, Any], stage1_best: dict[str, Any]) -> None:
    lines = [
        "# 50k core repair experiment report",
        "",
        "- research_only: true",
        "- auto_trading_approved: false",
        "- release_profile_replacement: false",
        f"- status: {summary['status']}",
        f"- experiment_count: {summary['experiment_count']}",
        f"- hard_condition_pass_count: {summary['hard_condition_pass_count']}",
        "",
        "## 修复动机",
        "",
        "- 来自 stage1 诊断：Sharpe、回撤、交易密度和 risk-on cash drag 是主要阻断。",
        "- repair 不放宽硬条件，只测试 monthly review、replacement 参数、partial de-risk、cyclical sleeve 和模块 overlay。",
        "",
        "## top variants",
        "",
    ]
    if frame.empty:
        lines.append("No repair rows.")
    else:
        cols = [
            "variant",
            "annual_return",
            "max_drawdown",
            "sharpe",
            "total_trades",
            "avg_cash_ratio_in_risk_on",
            "replacement_count",
            "pass_hard_conditions",
            "fail_reasons",
        ]
        lines.append(frame[[col for col in cols if col in frame.columns]].head(24).to_markdown(index=False))
        closest = frame.iloc[0].to_dict()
        lines.extend(
            [
                "",
                "## closest gap",
                "",
                f"- closest_variant: {closest.get('variant')}",
                f"- annual_return: {_pct(closest.get('annual_return', 0.0))}",
                f"- max_drawdown: {_pct(closest.get('max_drawdown', 0.0))}",
                f"- sharpe: {_safe_float(closest.get('sharpe')):.4f}",
                f"- total_trades: {_safe_float(closest.get('total_trades')):.0f}",
                f"- fail_reasons: {closest.get('fail_reasons')}",
            ]
        )
    lines.extend(
        [
            "",
            "## overtrading and safety",
            "",
            "- total_trades must remain between 20 and 60 under original hard conditions.",
            "- no broker integration, no real trades, no LLM decision authority.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_observation(path: Path, best: dict[str, Any], summary: dict[str, Any]) -> None:
    if best:
        lines = [
            "# repair observation candidate",
            "",
            f"- candidate_variant: {best.get('variant')}",
            "- frozen_for: paper_trading_observation_only",
            "- research_only: true",
            "- auto_trading_approved: false",
            "- broker_integration_enabled: false",
            "- llm_decision_allowed: false",
        ]
    else:
        lines = [
            "# repair observation candidate",
            "",
            "- candidate_variant: none",
            "- reason: no repair variant passed original hard conditions",
            "- research_only: true",
            "- auto_trading_approved: false",
        ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_robustness(path: Path, robustness: dict[str, Any]) -> None:
    lines = [
        "# repair neighborhood robustness",
        "",
        f"- status: {robustness.get('status', 'FRAGILE')}",
        f"- neighbor_count: {robustness.get('neighbor_count', 0)}",
        f"- support_count_excluding_best: {robustness.get('support_count_excluding_best', 0)}",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_comparison(path: Path, repair_best: dict[str, Any], stage1_best: dict[str, Any]) -> None:
    lines = ["# repair comparison vs stage1", ""]
    if repair_best and stage1_best:
        lines.extend(
            [
                f"- stage1_variant: {stage1_best.get('variant')}",
                f"- repair_variant: {repair_best.get('variant')}",
                f"- annual_delta: {_pct(_safe_float(repair_best.get('annual_return')) - _safe_float(stage1_best.get('annual_return')))}",
                f"- max_drawdown_delta: {_pct(_safe_float(repair_best.get('max_drawdown')) - _safe_float(stage1_best.get('max_drawdown')))}",
                f"- sharpe_delta: {_safe_float(repair_best.get('sharpe')) - _safe_float(stage1_best.get('sharpe')):.4f}",
                f"- total_trades_delta: {_safe_float(repair_best.get('total_trades')) - _safe_float(stage1_best.get('total_trades')):.0f}",
                f"- avg_cash_ratio_in_risk_on_delta: {_pct(_safe_float(repair_best.get('avg_cash_ratio_in_risk_on')) - _safe_float(stage1_best.get('avg_cash_ratio_in_risk_on')))}",
            ]
        )
    else:
        lines.append("Missing stage1 or repair rows.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_repair_experiments(max_variants: int | None = None) -> dict[str, Any]:
    config = load_yaml(CONFIG_PATH)
    configs = load_audit_configs()
    features = load_feature_window(DEFAULT_START_DATE, DEFAULT_END_DATE)
    benchmark = load_benchmark_window(DEFAULT_START_DATE, DEFAULT_END_DATE)
    feature_by_date, _approx = _prepare_feature_by_date(features, configs)
    variants = build_repair_variants()
    if max_variants is not None:
        variants = variants[: min(int(max_variants), MAX_REPAIR_VARIANTS)]
    rows = []
    for idx, variant in enumerate(variants, start=1):
        print(f"[50k_core_repair] {idx:03d}/{len(variants):03d} {variant.name}", flush=True)
        row = run_core_backtest(variant.params, feature_by_date=feature_by_date, benchmark=benchmark, configs=configs)
        public = _public_row(row)
        public.update(
            {
                "repair_mechanism": variant.mechanism,
                "research_only": True,
                "auto_trading_approved": False,
                "broker_integration_enabled": False,
                "llm_decision_allowed": False,
                "writes_real_trades": False,
                "release_profile_replacement": False,
            }
        )
        rows.append(public)
    return write_repair_outputs(rows, stage1_best=_stage1_best())


def main() -> int:
    parser = argparse.ArgumentParser(description="Run second-stage 50k core repair experiments.")
    parser.add_argument("--max-variants", type=int, default=None)
    args = parser.parse_args()
    summary = run_repair_experiments(args.max_variants)
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
