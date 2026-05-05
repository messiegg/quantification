#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.report_metadata import metadata_header, write_json
from src.strategy.metric_map import candidate_buckets_for_industry, metric_for_industry
from src.strategy.universe import (
    _base_filter_reasons,
    _bucket_filter_reasons,
    _score_row,
    build_candidate_pool,
    build_effective_universe,
    effective_universe_frame,
)
from src.utils.config import load_project_configs, load_yaml, resolve_path
from src.utils.storage import read_dataset_flex


OUT_JSON = "reports/audit/universe_shortfall.json"
OUT_MD = "reports/audit/universe_shortfall.md"


def _safe_float(value: object) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(numeric):
        return None
    return numeric


def _date_or_latest(features: pd.DataFrame, requested: str) -> str:
    if requested:
        return requested
    return str(features["date"].max())


def _missing_fields(row: pd.Series, fields: list[str]) -> list[str]:
    missing = []
    for field in fields:
        value = row.get("industry") if field == "industry" else row.get(field)
        if value is None:
            missing.append(field)
            continue
        try:
            is_missing = bool(pd.isna(value))
        except (TypeError, ValueError):
            is_missing = False
        if value == "" or is_missing:
            missing.append(field)
    return missing


def _candidate_diagnostics(
    latest: pd.DataFrame,
    rules: dict[str, Any],
    metric_map: dict[str, Any],
) -> tuple[dict[str, Any], pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    rules_for_filters = dict(rules)
    rules_for_filters["_metric_map_cfg"] = metric_map
    allowed_industries = set(metric_map.get("industry_bucket_candidates", {}).keys()) | set(metric_map.get("industry_bucket_map", {}).keys())
    required_fields = list(rules.get("core_required_fields") or rules.get("bucket_filters", {}).get("base", {}).get("core_required_fields", []))
    for _, row in latest.iterrows():
        industry = str(row.get("industry", ""))
        if industry not in allowed_industries:
            rows.append(
                {
                    "symbol": str(row.get("symbol")),
                    "name": row.get("name"),
                    "industry": industry,
                    "candidate_status": "filtered_out",
                    "stage": "allowed_industry",
                    "failed_filters": ["industry_not_in_metric_map"],
                    "missing_fields": _missing_fields(row, required_fields),
                    "best_score": None,
                    "best_bucket": None,
                }
            )
            continue
        bucket_items = []
        for bucket in candidate_buckets_for_industry(industry, metric_map):
            score = _score_row(row, bucket, rules["scoring"], metric_map, rules)
            main_metric = score.get("main_metric") or metric_for_industry(industry, metric_map)
            base_reasons = _base_filter_reasons(row, rules_for_filters, main_metric, 252)
            bucket_reasons = _bucket_filter_reasons(row, bucket, rules_for_filters, main_metric)
            bucket_items.append(
                {
                    "bucket": bucket,
                    "main_metric": main_metric,
                    "score": _safe_float(score.get("final_score")),
                    "base_filter_reasons": base_reasons,
                    "bucket_filter_reasons": bucket_reasons,
                    "failed_filters": base_reasons + bucket_reasons,
                }
            )
        eligible = [item for item in bucket_items if not item["failed_filters"]]
        best = sorted(bucket_items, key=lambda item: item["score"] if item["score"] is not None else -1e9, reverse=True)[0] if bucket_items else {}
        stage = "candidate_pool" if eligible else "bucket_filter"
        failed = [] if eligible else list(best.get("failed_filters", []))
        if failed and any(reason.endswith("_missing") or reason.startswith("missing_") for reason in failed):
            stage = "data_coverage"
        rows.append(
            {
                "symbol": str(row.get("symbol")),
                "name": row.get("name"),
                "industry": industry,
                "candidate_status": "candidate_pool" if eligible else "filtered_out",
                "stage": stage,
                "failed_filters": failed,
                "missing_fields": _missing_fields(row, required_fields),
                "best_score": best.get("score"),
                "best_bucket": best.get("bucket"),
                "market_cap_billion": _safe_float(row.get("market_cap_billion")),
                "pe": _safe_float(row.get("pe_ttm")),
                "pb": _safe_float(row.get("pb")),
                "dividend_yield": _safe_float(row.get("dv_ttm")),
                "data_asof": row.get("date"),
                "effective_date": row.get("financial_effective_date"),
            }
        )
    frame = pd.DataFrame(rows)
    funnel = {
        "raw_feature_rows": int(len(latest)),
        "allowed_industry_rows": int((frame["stage"] != "allowed_industry").sum()) if not frame.empty else 0,
        "candidate_pool_rows": int((frame["candidate_status"] == "candidate_pool").sum()) if not frame.empty else 0,
        "filtered_out_rows": int((frame["candidate_status"] != "candidate_pool").sum()) if not frame.empty else 0,
        "filter_loss_counts": dict(Counter(reason for reasons in frame.get("failed_filters", pd.Series(dtype=object)) for reason in (reasons or []))) if not frame.empty else {},
        "stage_loss_counts": frame["stage"].value_counts().to_dict() if not frame.empty and "stage" in frame else {},
    }
    return funnel, frame


def _positions_frame(positions_cfg: dict[str, Any]) -> pd.DataFrame:
    positions = positions_cfg.get("positions", [])
    return pd.DataFrame(positions) if positions else pd.DataFrame(columns=["symbol"])


def _would_enter_if(row: dict[str, Any], selected_industry_counts: Counter, rules: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    industry = str(row.get("industry", ""))
    max_per_industry = int(rules.get("max_names_per_industry", rules.get("max_per_industry", 3)))
    if selected_industry_counts[industry] >= max_per_industry:
        reasons.append("if_not_blocked_by_industry_cap")
    score = _safe_float(row.get("final_score"))
    rank = _safe_float(row.get("industry_rank"))
    if score is not None and score < float(rules.get("new_min_score", 55)):
        reasons.append("if_final_score_reached_new_min_score")
    if rank is not None and rank > float(rules.get("new_industry_rank", 4)):
        reasons.append("if_retained_or_new_ranking_allowed")
    if not reasons:
        reasons.append("if_higher_selection_priority_before_target_fill")
    return reasons


def _excluded_rows(candidate_pool: pd.DataFrame, diagnostics: pd.DataFrame, selected: pd.DataFrame, rules: dict[str, Any]) -> list[dict[str, Any]]:
    selected_symbols = set(selected.get("symbol", pd.Series(dtype=str)).astype(str))
    selected_industry_counts = Counter(selected.get("industry", pd.Series(dtype=str)).astype(str)) if not selected.empty else Counter()
    rows: list[dict[str, Any]] = []
    if not candidate_pool.empty:
        excluded = candidate_pool[~candidate_pool["symbol"].astype(str).isin(selected_symbols)].copy()
        excluded = excluded.sort_values(["final_score", "market_cap_billion", "symbol"], ascending=[False, False, True])
        for row in excluded.to_dict(orient="records"):
            rows.append(
                {
                    "symbol": str(row.get("symbol")),
                    "code": str(row.get("symbol")),
                    "name": row.get("name"),
                    "industry": row.get("industry"),
                    "market_cap_billion": _safe_float(row.get("market_cap_billion")),
                    "pe": _safe_float(row.get("pe_ttm")),
                    "pb": _safe_float(row.get("pb")),
                    "dividend_yield": _safe_float(row.get("dv_ttm")),
                    "score": _safe_float(row.get("final_score")),
                    "failed_filters": [],
                    "missing_fields": [],
                    "would_enter_if": _would_enter_if(row, selected_industry_counts, rules),
                    "data_asof": row.get("date") or row.get("as_of_date"),
                    "effective_date": row.get("financial_effective_date"),
                }
            )
    if len(rows) < 30 and not diagnostics.empty:
        filtered = diagnostics[diagnostics["candidate_status"] != "candidate_pool"].copy()
        filtered = filtered.sort_values(["market_cap_billion", "symbol"], ascending=[False, True])
        for row in filtered.to_dict(orient="records"):
            rows.append(
                {
                    "symbol": str(row.get("symbol")),
                    "code": str(row.get("symbol")),
                    "name": row.get("name"),
                    "industry": row.get("industry"),
                    "market_cap_billion": _safe_float(row.get("market_cap_billion")),
                    "pe": _safe_float(row.get("pe")),
                    "pb": _safe_float(row.get("pb")),
                    "dividend_yield": _safe_float(row.get("dividend_yield")),
                    "score": _safe_float(row.get("best_score")),
                    "failed_filters": row.get("failed_filters") or [],
                    "missing_fields": row.get("missing_fields") or [],
                    "would_enter_if": [f"if_filter_passed:{reason}" for reason in (row.get("failed_filters") or [])],
                    "data_asof": row.get("data_asof"),
                    "effective_date": row.get("effective_date"),
                }
            )
            if len(rows) >= 30:
                break
    return rows[:30]


def build_universe_shortfall_report(
    *,
    as_of_date: str = "",
    features_file: str = "data/features/daily_features",
    universe_rules_config: str = "config/universe_rules_v2.yml",
    write_report: bool = True,
) -> dict[str, Any]:
    configs = load_project_configs()
    rules = load_yaml(universe_rules_config)
    features = read_dataset_flex(features_file)
    active_date = _date_or_latest(features, as_of_date or str(configs["universe"].get("as_of_date") or ""))
    latest = features[features["date"].astype(str) == active_date].copy()
    metric_map = configs["metric_map"]
    candidate_pool = build_candidate_pool(latest, rules, metric_map, active_date)
    selected, _ = build_effective_universe(candidate_pool, configs["universe"], _positions_frame(configs["positions"]), rules)
    active_selected = effective_universe_frame(configs["universe"])
    if not active_selected.empty and str(configs["universe"].get("as_of_date", "")) == active_date:
        selected = active_selected.rename(columns={"industry_l1": "industry"}).copy()
    funnel, diagnostics = _candidate_diagnostics(latest, rules, metric_map)
    target = int(rules.get("target_size", rules.get("target_universe_size", 0)))
    floor = int(rules.get("floor_size", rules.get("target_universe_floor", 0)))
    selected_count = int(len(selected))
    shortfall = max(0, target - selected_count)
    stage_counts = funnel.get("stage_loss_counts", {})
    largest_loss_layer = max(stage_counts.items(), key=lambda item: item[1])[0] if stage_counts else ""
    industry_counts = Counter(selected.get("industry", selected.get("industry_l1", pd.Series(dtype=str))).astype(str)) if not selected.empty else Counter()
    excluded = _excluded_rows(candidate_pool, diagnostics, selected, rules)
    industry_cap_blocked = [item for item in excluded if "if_not_blocked_by_industry_cap" in item.get("would_enter_if", [])]
    data_coverage_loss = int(stage_counts.get("data_coverage", 0))
    warnings = []
    if floor <= selected_count < target:
        warnings.append({"code": "UNIVERSE_BELOW_TARGET", "selected_count": selected_count, "target_size": target})
    if data_coverage_loss:
        warnings.append({"code": "DATA_COVERAGE_WARN", "filtered_out_count": data_coverage_loss})
    status = "FAIL" if selected_count < floor else "WARN" if warnings else "PASS"
    payload = {
        **metadata_header(target_trade_date=active_date),
        "status": status,
        "active_date": active_date,
        "universe_file": "config/universe.yml",
        "rules_file": universe_rules_config,
        "target_size": target,
        "floor_size": floor,
        "selected_count": selected_count,
        "shortfall_to_target": shortfall,
        "candidate_pool_raw_count": funnel["raw_feature_rows"],
        "candidate_pool_count": int(len(candidate_pool)),
        "funnel": funnel,
        "largest_loss_layer": largest_loss_layer,
        "industry_counts": dict(industry_counts),
        "industry_cap_blocked_count": len(industry_cap_blocked),
        "market_cap_min": rules.get("bucket_filters", {}).get("base", {}).get("market_cap_billion_min"),
        "top_excluded_candidates": excluded,
        "warnings": warnings,
        "violations": [{"code": "UNIVERSE_UNDER_FLOOR", "selected_count": selected_count, "floor_size": floor}] if selected_count < floor else [],
    }
    if write_report:
        write_json(OUT_JSON, payload)
        _write_md(payload)
    return payload


def _write_md(payload: dict[str, Any]) -> None:
    lines = [
        "# universe shortfall report",
        "",
        f"- status: {payload['status']}",
        f"- active_date: {payload['active_date']}",
        f"- target_size: {payload['target_size']}",
        f"- floor_size: {payload['floor_size']}",
        f"- selected_count: {payload['selected_count']}",
        f"- shortfall_to_target: {payload['shortfall_to_target']}",
        f"- candidate_pool_raw_count: {payload['candidate_pool_raw_count']}",
        f"- candidate_pool_count: {payload['candidate_pool_count']}",
        f"- largest_loss_layer: {payload['largest_loss_layer']}",
        f"- industry_cap_blocked_count: {payload['industry_cap_blocked_count']}",
        "",
        "## funnel",
        "",
    ]
    for key, value in payload["funnel"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## industry counts", ""])
    for key, value in sorted(payload["industry_counts"].items()):
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## top excluded candidates", ""])
    for item in payload["top_excluded_candidates"]:
        lines.append(
            f"- {item['symbol']} {item.get('name') or ''} | {item.get('industry')} | score={item.get('score')} | "
            f"failed={item.get('failed_filters')} | missing={item.get('missing_fields')} | would_enter_if={item.get('would_enter_if')}"
        )
    lines.extend(["", "## warnings", ""])
    lines.extend([f"- {item['code']}: {item}" for item in payload.get("warnings", [])] or ["- none"])
    resolve_path(OUT_MD).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Explain why the active combined_v2 universe is below target size.")
    parser.add_argument("--as-of-date", default="")
    parser.add_argument("--features-file", default="data/features/daily_features")
    parser.add_argument("--universe-rules-config", default="config/universe_rules_v2.yml")
    parser.add_argument("--no-write-report", action="store_true")
    args = parser.parse_args()
    payload = build_universe_shortfall_report(
        as_of_date=args.as_of_date,
        features_file=args.features_file,
        universe_rules_config=args.universe_rules_config,
        write_report=not args.no_write_report,
    )
    return 1 if payload["status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
