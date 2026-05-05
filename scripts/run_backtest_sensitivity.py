#!/usr/bin/env python3
from __future__ import annotations

import copy
import argparse
import signal
import sys
import time
from contextlib import contextmanager
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
from scripts.report_metadata import metadata_header, stable_hash, status_from_children, write_json
from src.utils.config import resolve_path


CI_VARIANT_IDS = {
    "current_v2",
    "universe_large",
    "defensive_valuation_strict",
    "cyclical_pb_strict",
    "holding_shorter",
    "grid_tighter",
    "position_conservative",
}
MODE_WINDOWS = {
    "ci": ("2025-04-03", DEFAULT_END_DATE),
    "full": (DEFAULT_START_DATE, DEFAULT_END_DATE),
}
MODE_TIMEOUT_SECONDS = {"ci": 240, "full": 1800}


class VariantTimeoutError(TimeoutError):
    pass


@contextmanager
def _variant_timeout(seconds: int):
    if seconds <= 0:
        yield
        return
    previous_handler = signal.getsignal(signal.SIGALRM)

    def _handle_timeout(signum, frame):  # noqa: ANN001
        raise VariantTimeoutError(f"variant exceeded timeout_seconds={seconds}")

    signal.signal(signal.SIGALRM, _handle_timeout)
    signal.alarm(int(seconds))
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous_handler)


def _history_dir_has_json(path_like: str | Path) -> bool:
    path = Path(resolve_path(path_like))
    return path.exists() and any(path.glob("*.json"))


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


def _select_variants(variants: list[dict], mode: str) -> list[dict]:
    if mode == "ci":
        selected = [variant for variant in variants if variant["variant_id"] in CI_VARIANT_IDS]
        selected_ids = {variant["variant_id"] for variant in selected}
        missing = sorted(CI_VARIANT_IDS - selected_ids)
        if missing:
            raise ValueError(f"CI sensitivity variant set missing variants: {missing}")
        return selected
    return variants


def _sum_column(frame: pd.DataFrame | None, column: str) -> int:
    if frame is None or frame.empty or column not in frame.columns:
        return 0
    return int(pd.to_numeric(frame[column], errors="coerce").fillna(0).sum())


def _frame_path_hash(frame: pd.DataFrame | None, columns: list[str]) -> str:
    if frame is None or frame.empty:
        return stable_hash([])
    available = [column for column in columns if column in frame.columns]
    if not available:
        return stable_hash([])
    work = frame[available].copy().sort_values(available).reset_index(drop=True)
    return stable_hash(work.to_dict(orient="records"))


def _action_signature_by_day(frame: pd.DataFrame | None) -> dict[str, list[str]]:
    if frame is None or frame.empty or "date" not in frame.columns:
        return {}
    columns = [column for column in ["ts_code", "symbol", "side", "action", "shares", "amount"] if column in frame.columns]
    output: dict[str, list[str]] = {}
    for date, group in frame.groupby("date", sort=True):
        rows = []
        for row in group[columns].to_dict(orient="records"):
            rows.append("|".join(str(row.get(column, "")) for column in columns))
        output[str(date)] = sorted(rows)
    return output


def _position_signature_by_day(nav: pd.DataFrame | None) -> dict[str, str]:
    if nav is None or nav.empty or "date" not in nav.columns:
        return {}
    output = {}
    for row in nav.to_dict(orient="records"):
        output[str(row.get("date"))] = stable_hash(
            {
                "holdings_count": row.get("holdings_count"),
                "exposure": round(float(row.get("exposure", 0.0) or 0.0), 8),
                "cash": round(float(row.get("cash", 0.0) or 0.0), 4),
            }
        )
    return output


def _changed_days(base: dict[str, object], variant: dict[str, object]) -> int:
    days = set(base) | set(variant)
    return sum(1 for day in days if base.get(day) != variant.get(day))


def _history_hash(history_dir: str | Path) -> str:
    path = Path(resolve_path(history_dir))
    if not path.exists():
        return stable_hash([])
    rows = []
    for item in sorted(path.glob("*.json")):
        rows.append({"name": item.name, "sha256": stable_hash(item.read_text(encoding="utf-8"))})
    return stable_hash(rows)


def _load_baseline_annual_return() -> tuple[float | None, str]:
    metrics_path = resolve_path("reports/backtest/compare_combined_vs_v2_metrics.csv")
    if not metrics_path.exists():
        return None, "missing compare_combined_vs_v2_metrics.csv"
    frame = pd.read_csv(metrics_path)
    if "strategy" not in frame.columns or "annual_return" not in frame.columns:
        return None, "compare metrics missing strategy/annual_return columns"
    baseline = frame[frame["strategy"].astype(str) == "baseline"]
    if baseline.empty:
        return None, "compare metrics missing baseline row"
    value = pd.to_numeric(baseline.iloc[0].get("annual_return"), errors="coerce")
    if pd.isna(value):
        return None, "baseline annual_return is not numeric"
    return float(value), str(metrics_path)


def _result_trace(result, history_dir: str | Path) -> dict:
    diagnostics = result.daily_diagnostics if result.daily_diagnostics is not None else pd.DataFrame()
    blocked = result.blocked_signals if result.blocked_signals is not None else pd.DataFrame()
    trades = result.trades_detailed if result.trades_detailed is not None else pd.DataFrame()
    nav = result.nav if result.nav is not None else pd.DataFrame()
    return {
        "candidate_count": _sum_column(diagnostics, "decision_scope_size"),
        "universe_count": float(pd.to_numeric(diagnostics.get("effective_universe_size", pd.Series(dtype=float)), errors="coerce").fillna(0).mean())
        if not diagnostics.empty
        else 0.0,
        "raw_buy_signal_count": _sum_column(diagnostics, "raw_buy_signal_count"),
        "raw_sell_signal_count": _sum_column(diagnostics, "raw_sell_signal_count"),
        "executable_buy_count": _sum_column(diagnostics, "executable_buy_count"),
        "executable_sell_count": _sum_column(diagnostics, "executable_sell_count"),
        "blocked_signal_count": int(len(blocked)),
        "turnover": float(result.metrics.get("turnover", 0.0)),
        "average_exposure": float(result.metrics.get("avg_daily_exposure", 0.0)),
        "action_path_hash": _frame_path_hash(trades, ["date", "ts_code", "side", "action", "shares", "amount"]),
        "position_path_hash": _frame_path_hash(nav, ["date", "cash", "exposure", "holdings_count"]),
        "equity_curve_hash": _frame_path_hash(nav, ["date", "nav"]),
        "universe_path_hash": _history_hash(history_dir),
        "action_by_day": _action_signature_by_day(trades),
        "position_by_day": _position_signature_by_day(nav),
    }


def classify_parameter_binding(
    *,
    changed_params: list[str],
    base_config_hash: str,
    variant_config_hash: str,
    base_trace: dict,
    variant_trace: dict,
) -> tuple[str, str]:
    if changed_params and variant_config_hash == base_config_hash:
        return "FAIL", "PARAM_NOT_WIRED"
    same_paths = (
        variant_trace["action_path_hash"] == base_trace["action_path_hash"]
        and variant_trace["position_path_hash"] == base_trace["position_path_hash"]
        and variant_trace["equity_curve_hash"] == base_trace["equity_curve_hash"]
    )
    if not same_paths:
        return "BINDING", ""
    if not changed_params:
        return "BASELINE", ""
    if (
        variant_trace["raw_buy_signal_count"] == base_trace["raw_buy_signal_count"]
        and variant_trace["raw_sell_signal_count"] == base_trace["raw_sell_signal_count"]
    ):
        return "NON_BINDING", "NO_SIGNAL_COVERAGE"
    if (
        variant_trace["raw_buy_signal_count"] != base_trace["raw_buy_signal_count"]
        or variant_trace["raw_sell_signal_count"] != base_trace["raw_sell_signal_count"]
    ) and variant_trace["blocked_signal_count"] >= base_trace["blocked_signal_count"]:
        return "NON_BINDING", "BLOCKED_BY_ACCOUNT_CONSTRAINT"
    return "NON_BINDING", "UNKNOWN"


def _output_paths(mode: str) -> dict[str, str]:
    suffix = "" if mode == "ci" else "_full"
    return {
        "csv": f"reports/backtest/robustness/sensitivity_metrics{suffix}.csv",
        "json": f"reports/backtest/robustness/sensitivity_report{suffix}.json",
        "md": f"reports/backtest/robustness/sensitivity_report{suffix}.md",
        "partial_json": f"reports/backtest/robustness/sensitivity_report{suffix}.partial.json",
    }


def _variant_config_hash(variant: dict, configs: dict) -> str:
    return stable_hash(
        {
            "strategy": variant["strategy"],
            "universe": variant["universe"],
            "account": configs["account"],
        }
    )


def _error_row(variant: dict, configs: dict, base_config_hash: str, error: str, elapsed_seconds: float) -> dict:
    changed_params = [] if variant["variant_id"] == "current_v2" else [variant["changed_parameter"]]
    variant_config_hash = _variant_config_hash(variant, configs)
    return {
        "variant_id": variant["variant_id"],
        "variant_group": variant["variant_group"],
        "changed_parameter": variant["changed_parameter"],
        "changed_params": changed_params,
        "base_config_hash": base_config_hash,
        "variant_config_hash": variant_config_hash,
        "candidate_count": 0,
        "universe_count": 0,
        "raw_buy_signal_count": 0,
        "raw_sell_signal_count": 0,
        "executable_buy_count": 0,
        "executable_sell_count": 0,
        "blocked_signal_count": 0,
        "annual_return": None,
        "cumulative_return": None,
        "max_drawdown": None,
        "sharpe": None,
        "total_trades": 0,
        "avg_daily_exposure": None,
        "turnover": None,
        "average_exposure": None,
        "action_path_hash": "",
        "position_path_hash": "",
        "equity_curve_hash": "",
        "changed_action_days_count": 0,
        "changed_position_days_count": 0,
        "changed_universe_days_count": 0,
        "parameter_binding_status": "ERROR",
        "non_binding_reason": "ERROR",
        "variant_run_status": "ERROR",
        "error": error,
        "elapsed_seconds": round(elapsed_seconds, 3),
    }


def _write_partial_report(rows: list[dict], mode: str, start_date: str, end_date: str, timeout_seconds: int) -> None:
    paths = _output_paths(mode)
    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame.to_csv(ensure_parent(paths["csv"]), index=False)
    write_json(
        paths["partial_json"],
        {
            **metadata_header(),
            "status": "RUNNING",
            "mode": mode,
            "start_date": start_date,
            "end_date": end_date,
            "variant_timeout_seconds": timeout_seconds,
            "completed_variant_count": len(rows),
            "variants": rows,
        },
    )


def _pct_or_missing(value: object) -> str:
    try:
        if pd.isna(value):
            return "missing"
        return pct(float(value))
    except (TypeError, ValueError):
        return "missing"


def _float_or_none(value: object) -> float | None:
    try:
        if pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_or_zero(value: object) -> int:
    try:
        if pd.isna(value):
            return 0
        return int(value)
    except (TypeError, ValueError):
        return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run combined_v2 parameter sensitivity checks.")
    parser.add_argument(
        "--mode",
        choices=["ci", "full"],
        default="full",
        help="Sensitivity scope. ci runs a bounded core subset for release guard; full runs all variants.",
    )
    parser.add_argument("--start-date", default="", help="Override the mode's default backtest start date.")
    parser.add_argument("--end-date", default="", help="Override the mode's default backtest end date.")
    parser.add_argument(
        "--variant-timeout-seconds",
        type=int,
        default=0,
        help="Per-variant timeout. Defaults are mode-specific; 0 means use the mode default.",
    )
    parser.add_argument(
        "--refresh-universe-history",
        action="store_true",
        help="Regenerate cached historical universe files before running sensitivity variants.",
    )
    parser.add_argument(
        "--record-failed-run",
        default="",
        help="Write a fail-closed sensitivity report for an attempted run that did not complete.",
    )
    args = parser.parse_args(argv)
    paths = _output_paths(args.mode)
    default_start, default_end = MODE_WINDOWS[args.mode]
    start_date = args.start_date or default_start
    end_date = args.end_date or default_end
    timeout_seconds = args.variant_timeout_seconds or MODE_TIMEOUT_SECONDS[args.mode]

    if args.record_failed_run:
        baseline_annual, baseline_annual_source = _load_baseline_annual_return()
        payload = {
            **metadata_header(),
            "status": "FAIL",
            "mode": args.mode,
            "failure_reason": args.record_failed_run,
            "base_config_hash": "",
            "baseline_annual_return": baseline_annual,
            "baseline_annual_return_source": baseline_annual_source,
            "non_binding_parameters": [],
            "all_core_parameters_non_binding": False,
            "unknown_non_binding_count": 0,
            "variants": [],
        }
        write_json(paths["json"], payload)
        ensure_parent(paths["md"]).write_text(
            "\n".join(
                [
                    "# 参数敏感性测试",
                    "",
                    "- sensitivity_status: FAIL",
                    f"- mode: {args.mode}",
                    f"- failure_reason: {args.record_failed_run}",
                    "- full sensitivity run did not complete locally; release guard must fail closed.",
                    f"- baseline next_bar 年化: {pct(baseline_annual) if baseline_annual is not None else 'missing'}",
                    f"- baseline 年化来源: {baseline_annual_source}",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        return 1

    configs = load_audit_configs()
    if args.refresh_universe_history or not _history_dir_has_json(V2_HISTORY_DIR):
        prepare_v2_history(configs, end_date=end_date, start_date=start_date)
    features = load_feature_window(start_date, end_date)
    benchmark = load_benchmark_window(start_date, end_date)
    variants = _select_variants(_variants(configs), args.mode)
    needs_generation_features = any(
        variant["regenerate_universe"] and (args.refresh_universe_history or not _history_dir_has_json(variant["history_dir"]))
        for variant in variants
    )
    generation_features = None
    if needs_generation_features:
        generation_start = _history_generation_start(BASELINE_HISTORY_DIR, start_date, end_date)
        generation_features = load_feature_window(generation_start, end_date, DEFAULT_FEATURES_FILE)

    baseline_annual, baseline_annual_source = _load_baseline_annual_return()
    rows: list[dict] = []
    base_trace: dict | None = None
    base_config_hash = _variant_config_hash(variants[0], configs) if variants else ""
    for variant in variants:
        started = time.monotonic()
        print(f"[sensitivity:{args.mode}] start {variant['variant_id']}", flush=True)
        if variant["variant_id"] != "current_v2" and base_trace is None:
            row = _error_row(
                variant,
                configs,
                base_config_hash,
                "base_trace_missing_after_current_v2_failure",
                time.monotonic() - started,
            )
            rows.append(row)
            _write_partial_report(rows, args.mode, start_date, end_date, timeout_seconds)
            print(f"[sensitivity:{args.mode}] error {variant['variant_id']} base_trace_missing", flush=True)
            continue
        try:
            with _variant_timeout(timeout_seconds):
                if variant["regenerate_universe"] and (args.refresh_universe_history or not _history_dir_has_json(variant["history_dir"])):
                    assert generation_features is not None
                    _generate_v2_history(
                        generation_features,
                        BASELINE_HISTORY_DIR,
                        variant["history_dir"],
                        variant["universe"],
                        configs["metric_map"],
                    )
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
        except Exception as exc:
            row = _error_row(variant, configs, base_config_hash, f"{type(exc).__name__}: {exc}", time.monotonic() - started)
            rows.append(row)
            _write_partial_report(rows, args.mode, start_date, end_date, timeout_seconds)
            print(f"[sensitivity:{args.mode}] error {variant['variant_id']} {type(exc).__name__}: {exc}", flush=True)
            continue

        changed_params = [] if variant["variant_id"] == "current_v2" else [variant["changed_parameter"]]
        variant_config_hash = _variant_config_hash(variant, configs)
        trace = _result_trace(result, variant["history_dir"])
        if variant["variant_id"] == "current_v2":
            base_trace = trace
            base_config_hash = variant_config_hash
            binding_status, binding_reason = "BASELINE", ""
            changed_action_days_count = 0
            changed_position_days_count = 0
            changed_universe_days_count = 0
        else:
            assert base_trace is not None
            binding_status, binding_reason = classify_parameter_binding(
                changed_params=changed_params,
                base_config_hash=base_config_hash,
                variant_config_hash=variant_config_hash,
                base_trace=base_trace,
                variant_trace=trace,
            )
            changed_action_days_count = _changed_days(base_trace["action_by_day"], trace["action_by_day"])
            changed_position_days_count = _changed_days(base_trace["position_by_day"], trace["position_by_day"])
            changed_universe_days_count = 0 if trace["universe_path_hash"] == base_trace["universe_path_hash"] else 1
        row = metrics_row("combined_v2", "next_bar", result, benchmark)
        row.update(
            {
                "variant_id": variant["variant_id"],
                "variant_group": variant["variant_group"],
                "changed_parameter": variant["changed_parameter"],
                "changed_params": changed_params,
                "base_config_hash": base_config_hash,
                "variant_config_hash": variant_config_hash,
                "candidate_count": trace["candidate_count"],
                "universe_count": trace["universe_count"],
                "raw_buy_signal_count": trace["raw_buy_signal_count"],
                "raw_sell_signal_count": trace["raw_sell_signal_count"],
                "executable_buy_count": trace["executable_buy_count"],
                "executable_sell_count": trace["executable_sell_count"],
                "blocked_signal_count": trace["blocked_signal_count"],
                "turnover": trace["turnover"],
                "average_exposure": trace["average_exposure"],
                "action_path_hash": trace["action_path_hash"],
                "position_path_hash": trace["position_path_hash"],
                "equity_curve_hash": trace["equity_curve_hash"],
                "changed_action_days_count": changed_action_days_count,
                "changed_position_days_count": changed_position_days_count,
                "changed_universe_days_count": changed_universe_days_count,
                "parameter_binding_status": binding_status,
                "non_binding_reason": binding_reason,
                "variant_run_status": "PASS",
                "error": "",
                "elapsed_seconds": round(time.monotonic() - started, 3),
                "baseline_annual_return": baseline_annual,
                "baseline_annual_return_source": baseline_annual_source,
            }
        )
        rows.append(row)
        _write_partial_report(rows, args.mode, start_date, end_date, timeout_seconds)
        print(f"[sensitivity:{args.mode}] done {variant['variant_id']} binding={binding_status}", flush=True)
    frame = pd.DataFrame(rows)
    columns = [
        "variant_id",
        "variant_group",
        "changed_parameter",
        "base_config_hash",
        "variant_config_hash",
        "changed_params",
        "candidate_count",
        "universe_count",
        "raw_buy_signal_count",
        "raw_sell_signal_count",
        "executable_buy_count",
        "executable_sell_count",
        "blocked_signal_count",
        "annual_return",
        "cumulative_return",
        "max_drawdown",
        "sharpe",
        "total_trades",
        "avg_daily_exposure",
        "turnover",
        "average_exposure",
        "action_path_hash",
        "position_path_hash",
        "equity_curve_hash",
        "changed_action_days_count",
        "changed_position_days_count",
        "changed_universe_days_count",
        "parameter_binding_status",
        "non_binding_reason",
        "variant_run_status",
        "error",
        "elapsed_seconds",
        "benchmark_annual_return",
        "excess_annual_return",
        "defensive_pnl",
        "cyclical_pnl",
        "baseline_annual_return",
        "baseline_annual_return_source",
    ]
    frame = frame.reindex(columns=columns)
    frame.to_csv(ensure_parent(paths["csv"]), index=False)

    non_current = frame[frame["variant_id"] != "current_v2"].copy()
    annual_numeric = pd.to_numeric(non_current.get("annual_return", pd.Series(dtype=float)), errors="coerce")
    drawdown_numeric = pd.to_numeric(non_current.get("max_drawdown", pd.Series(dtype=float)), errors="coerce")
    positive_after_tighten = annual_numeric[non_current["variant_id"].str.contains("strict|conservative|tighter", na=False)].gt(0).all()
    loose_drawdown_ok = drawdown_numeric[non_current["variant_id"].str.contains("loose|aggressive|wider", na=False)].ge(-0.18).all()
    near_zero_count = int((annual_numeric.abs() < 0.01).sum())
    under_baseline_count = int((annual_numeric <= baseline_annual).sum()) if baseline_annual is not None else 0
    overfit_risk = near_zero_count > len(non_current) / 2 or (baseline_annual is not None and under_baseline_count > len(non_current) / 2)
    non_binding = non_current[non_current["parameter_binding_status"].isin(["NON_BINDING", "FAIL", "ERROR"])].copy()
    unknown = non_current[non_current["non_binding_reason"] == "UNKNOWN"].copy()
    errors = non_current[non_current["parameter_binding_status"] == "ERROR"].copy()
    all_core_non_binding = bool(
        not non_current.empty
        and non_current["parameter_binding_status"].isin(["NON_BINDING", "FAIL", "ERROR"]).all()
    )
    overall_status = "FAIL" if all_core_non_binding or not unknown.empty or not errors.empty else "WARN" if not non_binding.empty else "PASS"
    non_binding_parameters = sorted(set(non_binding["variant_group"].astype(str)))
    payload = {
        **metadata_header(),
        "status": overall_status,
        "mode": args.mode,
        "start_date": start_date,
        "end_date": end_date,
        "variant_timeout_seconds": timeout_seconds,
        "ci_core_variant_ids": sorted(CI_VARIANT_IDS),
        "universe_history_refresh": bool(args.refresh_universe_history),
        "baseline_annual_return": baseline_annual,
        "baseline_annual_return_source": baseline_annual_source,
        "base_config_hash": base_config_hash,
        "non_binding_parameters": non_binding_parameters,
        "all_core_parameters_non_binding": all_core_non_binding,
        "unknown_non_binding_count": int(len(unknown)),
        "error_variant_count": int(len(errors)),
        "variants": frame.to_dict(orient="records"),
    }
    write_json(paths["json"], payload)

    lines = [
        "# 参数敏感性测试",
        "",
        f"- 口径: combined_v2 next_bar，固定 {start_date} 到 {end_date}。",
        f"- mode: {args.mode}",
        f"- variant_timeout_seconds: {timeout_seconds}",
        "- 这是 one-at-a-time 扰动，不做参数优化，不输出最佳参数，不写回正式配置。",
        f"- sensitivity_status: {overall_status}",
        f"- non_binding_parameters: {', '.join(non_binding_parameters) if non_binding_parameters else 'none'}",
        f"- unknown_non_binding_count: {len(unknown)}",
        f"- error_variant_count: {len(errors)}",
        f"- baseline next_bar 年化: {pct(baseline_annual) if baseline_annual is not None else 'missing'}",
        f"- baseline 年化来源: {baseline_annual_source}",
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
        sharpe = _float_or_none(row.get("sharpe"))
        sharpe_text = f"{sharpe:.2f}" if sharpe is not None else "missing"
        lines.append(
            f"- {row['variant_id']}: 年化 {_pct_or_missing(row.get('annual_return'))}，累计 {_pct_or_missing(row.get('cumulative_return'))}，回撤 {_pct_or_missing(row.get('max_drawdown'))}，夏普 {sharpe_text}，成交 {_int_or_zero(row.get('total_trades'))}，平均仓位 {_pct_or_missing(row.get('avg_daily_exposure'))}，binding={row['parameter_binding_status']}，reason={row['non_binding_reason'] or 'n/a'}，changed_action_days={_int_or_zero(row.get('changed_action_days_count'))}，run_status={row.get('variant_run_status') or 'PASS'}"
        )
    ensure_parent(paths["md"]).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 1 if overall_status == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
