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

from scripts.report_metadata import metadata_header, status_from_children, write_json
from src.strategy.metric_map import is_financial_industry
from src.utils.config import load_yaml, resolve_path
from src.utils.storage import read_dataset_flex


JSON_PATH = "reports/audit/universe_integrity.json"
MD_PATH = "reports/audit/universe_integrity.md"


def _safe_float(value: object) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(numeric):
        return None
    return numeric


def _is_missing(value: object) -> bool:
    if value in {None, ""}:
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        output.append(value)
    return output


def _date_value(payload: dict[str, Any]) -> str:
    return str(payload.get("as_of_date") or payload.get("effective_from") or payload.get("generated_at") or "")


def _date_or_none(value: object) -> str | None:
    if _is_missing(value):
        return None
    timestamp = pd.to_datetime(value, errors="coerce")
    if not pd.isna(timestamp):
        return timestamp.strftime("%Y-%m-%d")
    return str(value)


def _hard_filter_thresholds(rules: dict[str, Any], bucket: str) -> dict[str, Any]:
    filters = rules.get("bucket_filters", {}) if isinstance(rules.get("bucket_filters"), dict) else {}
    base = filters.get("base", {}) if isinstance(filters.get("base"), dict) else {}
    bucket_cfg = filters.get(bucket, {}) if isinstance(filters.get(bucket), dict) else {}
    return {**base, **bucket_cfg}


def _check_required(item: dict[str, Any], required_fields: list[str]) -> list[str]:
    missing = []
    aliases = {
        "industry": ("industry", "industry_l1"),
        "market_cap_billion": ("market_cap_billion",),
        "avg_amount_60d_million": ("avg_amount_60d_million",),
        "pb": ("pb",),
        "stock_pb_q_blended": ("stock_pb_q_blended", "stock_q_blended"),
        "industry_pb_q_blended": ("industry_pb_q_blended", "industry_q_blended"),
    }
    for field in required_fields:
        names = aliases.get(field, (field,))
        if all(_is_missing(item.get(name)) for name in names):
            missing.append(field)
    return missing


def _field_value(item: dict[str, Any], field: str) -> Any:
    aliases = {
        "industry": ("industry", "industry_l1"),
        "stock_pb_q_blended": ("stock_pb_q_blended", "stock_q_blended"),
        "industry_pb_q_blended": ("industry_pb_q_blended", "industry_q_blended"),
        "cycle_peak_trap": ("cycle_peak_trap", "cycle_trap"),
    }
    for name in aliases.get(field, (field,)):
        value = item.get(name)
        if not _is_missing(value):
            return value
    return None


def _check_numeric(
    checks: list[dict[str, Any]],
    failures: list[str],
    missing_fields: list[str],
    *,
    item: dict[str, Any],
    field: str,
    threshold_name: str,
    op: str,
    threshold: Any,
    source: str,
    asof: str,
    fail_code: str | None = None,
) -> None:
    threshold_value = _safe_float(threshold)
    value = _safe_float(_field_value(item, field))
    check = {
        "field": field,
        "threshold_name": threshold_name,
        "operator": op,
        "threshold": threshold_value,
        "value": value,
        "source": source,
        "asof": asof or None,
    }
    if threshold_value is None:
        check["status"] = "NOT_CONFIGURED"
        checks.append(check)
        return
    if value is None:
        code = f"missing_{field}"
        check["status"] = "MISSING"
        check["failure_code"] = code
        checks.append(check)
        failures.append(code)
        missing_fields.append(field)
        return
    failed = False
    if op == ">=":
        failed = value < threshold_value
        code = fail_code or f"{field}_below_{threshold_name}"
    elif op == ">":
        failed = value <= threshold_value
        code = fail_code or f"{field}_not_above_{threshold_name}"
    elif op == "<=":
        failed = value > threshold_value
        code = fail_code or f"{field}_above_{threshold_name}"
    elif op == "==":
        failed = value != threshold_value
        code = fail_code or f"{field}_not_equal_{threshold_name}"
    else:
        failed = True
        code = fail_code or f"{field}_unsupported_operator"
    check["status"] = "FAIL" if failed else "PASS"
    if failed:
        check["failure_code"] = code
        failures.append(code)
    checks.append(check)


def _check_boolean(
    checks: list[dict[str, Any]],
    failures: list[str],
    missing_fields: list[str],
    *,
    item: dict[str, Any],
    field: str,
    expected: bool,
    source: str,
    asof: str,
    failure_code: str,
) -> None:
    value = _field_value(item, field)
    check = {
        "field": field,
        "operator": "is",
        "threshold": expected,
        "value": value,
        "source": source,
        "asof": asof or None,
    }
    if _is_missing(value):
        code = f"missing_{field}"
        check["status"] = "MISSING"
        check["failure_code"] = code
        failures.append(code)
        missing_fields.append(field)
    elif bool(value) is not expected:
        check["status"] = "FAIL"
        check["failure_code"] = failure_code
        failures.append(failure_code)
    else:
        check["status"] = "PASS"
    checks.append(check)


def _hard_filter_results(item: dict[str, Any], rules: dict[str, Any], metric_map: dict[str, Any], source: str, asof: str) -> dict[str, Any]:
    bucket = str(item.get("bucket") or "")
    thresholds = _hard_filter_thresholds(rules, bucket)
    failures: list[str] = []
    missing_fields: list[str] = []
    checks: list[dict[str, Any]] = []
    base = (rules.get("bucket_filters", {}) or {}).get("base", {}) or {}
    bucket_cfg = (rules.get("bucket_filters", {}) or {}).get(bucket, {}) or {}

    required_fields = list(rules.get("core_required_fields") or base.get("core_required_fields") or [])
    for field in required_fields:
        value = _field_value(item, field)
        status = "MISSING" if _is_missing(value) else "PASS"
        check = {
            "field": field,
            "operator": "present",
            "threshold": "required",
            "value": value if not _is_missing(value) else None,
            "status": status,
            "source": source,
            "asof": asof or None,
        }
        if status == "MISSING":
            code = f"missing_{field}"
            check["failure_code"] = code
            failures.append(code)
            missing_fields.append(field)
        checks.append(check)

    if base.get("require_industry"):
        value = _field_value(item, "industry")
        if _is_missing(value):
            checks.append(
                {
                    "field": "industry",
                    "operator": "present",
                    "threshold": True,
                    "value": None,
                    "status": "MISSING",
                    "failure_code": "missing_industry",
                    "source": source,
                    "asof": asof or None,
                }
            )
            failures.append("missing_industry")
            missing_fields.append("industry")
    if base.get("require_a_share"):
        _check_boolean(
            checks,
            failures,
            missing_fields,
            item=item,
            field="is_a_share",
            expected=True,
            source=source,
            asof=asof,
            failure_code="not_a_share",
        )
    if base.get("require_not_st"):
        _check_boolean(
            checks,
            failures,
            missing_fields,
            item=item,
            field="is_st",
            expected=False,
            source=source,
            asof=asof,
            failure_code="st",
        )
    if "listed_days_min" in base:
        _check_numeric(
            checks,
            failures,
            missing_fields,
            item=item,
            field="listed_days",
            threshold_name="listed_days_min",
            op=">=",
            threshold=base.get("listed_days_min"),
            source=source,
            asof=asof,
        )
    if "market_cap_billion_min" in base:
        _check_numeric(
            checks,
            failures,
            missing_fields,
            item=item,
            field="market_cap_billion",
            threshold_name="market_cap_billion_min",
            op=">=",
            threshold=base.get("market_cap_billion_min"),
            source=source,
            asof=asof,
        )
    if "avg_amount_60d_million_min" in base:
        _check_numeric(
            checks,
            failures,
            missing_fields,
            item=item,
            field="avg_amount_60d_million",
            threshold_name="avg_amount_60d_million_min",
            op=">=",
            threshold=base.get("avg_amount_60d_million_min"),
            source=source,
            asof=asof,
        )

    for field, threshold_name, op in (
        ("market_cap_billion", "market_cap_billion_min", ">="),
        ("avg_amount_60d_million", "avg_amount_60d_million_min", ">="),
        ("latest_net_profit", "latest_net_profit_min_exclusive", ">"),
        ("roe", "roe_min", ">="),
    ):
        if threshold_name in bucket_cfg:
            _check_numeric(
                checks,
                failures,
                missing_fields,
                item=item,
                field=field,
                threshold_name=threshold_name,
                op=op,
                threshold=bucket_cfg.get(threshold_name),
                source=source,
                asof=asof,
            )

    if bucket == "defensive_dividend":
        if "dv_ttm_min" in bucket_cfg:
            _check_numeric(
                checks,
                failures,
                missing_fields,
                item=item,
                field="dv_ttm",
                threshold_name="dv_ttm_min",
                op=">=",
                threshold=bucket_cfg.get("dv_ttm_min"),
                source=source,
                asof=asof,
            )
        if "debt_to_assets_max" in bucket_cfg:
            industry = str(_field_value(item, "industry") or "")
            if is_financial_industry(industry, metric_map):
                checks.append(
                    {
                        "field": "debt_to_assets",
                        "operator": "<=",
                        "threshold_name": "debt_to_assets_max",
                        "threshold": _safe_float(bucket_cfg.get("debt_to_assets_max")),
                        "value": _safe_float(_field_value(item, "debt_to_assets")),
                        "status": "SKIPPED",
                        "skip_reason": "financial_industry_debt_filter_not_applied",
                        "source": source,
                        "asof": asof or None,
                    }
                )
            else:
                _check_numeric(
                    checks,
                    failures,
                    missing_fields,
                    item=item,
                    field="debt_to_assets",
                    threshold_name="debt_to_assets_max",
                    op="<=",
                    threshold=bucket_cfg.get("debt_to_assets_max"),
                    source=source,
                    asof=asof,
                )
        if "pe_ttm_max_when_primary_metric" in bucket_cfg or "pb_q_blended_max_when_primary_metric" in bucket_cfg:
            pe_value = _safe_float(_field_value(item, "pe_ttm"))
            pe_limit = _safe_float(bucket_cfg.get("pe_ttm_max_when_primary_metric"))
            pb_value = _safe_float(_field_value(item, "pb"))
            pb_min = _safe_float(bucket_cfg.get("pb_min_exclusive"))
            pb_q_value = _safe_float(_field_value(item, "stock_pb_q_blended"))
            pb_q_limit = _safe_float(bucket_cfg.get("pb_q_blended_max_when_primary_metric"))
            pe_ok = pe_value is not None and pe_limit is not None and pe_value > 0 and pe_value <= pe_limit
            pb_ok = (
                pb_value is not None
                and pb_min is not None
                and pb_value > pb_min
                and pb_q_value is not None
                and pb_q_limit is not None
                and pb_q_value <= pb_q_limit
            )
            primary_metric = str(_field_value(item, "main_metric") or "")
            valuation_ok = pb_ok if primary_metric == "pb" else bool(pe_ok or pb_ok)
            valuation_missing = (
                (pe_value is None or pe_limit is None)
                and (pb_value is None or pb_min is None or pb_q_value is None or pb_q_limit is None)
            )
            valuation_check = {
                "field": "valuation",
                "operator": "pe_ttm<=max OR stock_pb_q_blended<=max",
                "threshold": {
                    "pe_ttm_max_when_primary_metric": pe_limit,
                    "pb_min_exclusive": pb_min,
                    "pb_q_blended_max_when_primary_metric": pb_q_limit,
                },
                "value": {"pe_ttm": pe_value, "pb": pb_value, "stock_pb_q_blended": pb_q_value, "main_metric": primary_metric or None},
                "source": source,
                "asof": asof or None,
            }
            if valuation_missing:
                valuation_check["status"] = "MISSING"
                valuation_check["failure_code"] = "missing_valuation_fields"
                failures.append("missing_valuation_fields")
                missing_fields.append("valuation_fields")
            elif valuation_ok:
                valuation_check["status"] = "PASS"
            else:
                valuation_check["status"] = "FAIL"
                valuation_check["failure_code"] = "valuation_above_defensive_threshold"
                failures.append("valuation_above_defensive_threshold")
            checks.append(valuation_check)

    if bucket == "cyclical_rotation":
        if "pb_min_exclusive" in bucket_cfg:
            _check_numeric(
                checks,
                failures,
                missing_fields,
                item=item,
                field="pb",
                threshold_name="pb_min_exclusive",
                op=">",
                threshold=bucket_cfg.get("pb_min_exclusive"),
                source=source,
                asof=asof,
            )
        if "pb_q_blended_max" in bucket_cfg:
            _check_numeric(
                checks,
                failures,
                missing_fields,
                item=item,
                field="stock_pb_q_blended",
                threshold_name="pb_q_blended_max",
                op="<=",
                threshold=bucket_cfg.get("pb_q_blended_max"),
                source=source,
                asof=asof,
                fail_code="stock_pb_q_blended_above_pb_q_blended_max",
            )
        rank_value = _safe_float(_field_value(item, "industry_market_cap_rank"))
        pct_value = _safe_float(_field_value(item, "industry_market_cap_percentile"))
        rank_limit = _safe_float(bucket_cfg.get("market_cap_industry_rank_top_n"))
        pct_limit = _safe_float(bucket_cfg.get("market_cap_industry_rank_top_pct"))
        leader_ok = (rank_value is not None and rank_limit is not None and rank_value <= rank_limit) or (
            pct_value is not None and pct_limit is not None and pct_value <= pct_limit
        )
        leader_missing = (rank_value is None or rank_limit is None) and (pct_value is None or pct_limit is None)
        leader_check = {
            "field": "industry_leader",
            "operator": "rank<=top_n OR percentile<=top_pct",
            "threshold": {"market_cap_industry_rank_top_n": rank_limit, "market_cap_industry_rank_top_pct": pct_limit},
            "value": {"industry_market_cap_rank": rank_value, "industry_market_cap_percentile": pct_value},
            "source": source,
            "asof": asof or None,
        }
        if leader_missing:
            leader_check["status"] = "MISSING"
            leader_check["failure_code"] = "missing_industry_leader_fields"
            failures.append("missing_industry_leader_fields")
            missing_fields.append("industry_leader_fields")
        elif leader_ok:
            leader_check["status"] = "PASS"
        else:
            leader_check["status"] = "FAIL"
            leader_check["failure_code"] = "industry_leader"
            failures.append("industry_leader")
        checks.append(leader_check)
        cycle_value = _field_value(item, "cycle_peak_trap")
        if not _is_missing(cycle_value):
            checks.append(
                {
                    "field": "cycle_peak_trap",
                    "operator": "is",
                    "threshold": False,
                    "value": bool(cycle_value),
                    "status": "FAIL" if bool(cycle_value) else "PASS",
                    "failure_code": "cycle_trap" if bool(cycle_value) else None,
                    "source": source,
                    "asof": asof or None,
                }
            )
            if bool(cycle_value):
                failures.append("cycle_trap")

    return {
        "checks": checks,
        "failed_filters": _dedupe(failures),
        "missing_fields": _dedupe(missing_fields),
    }


def _override_config(rules: dict[str, Any]) -> dict[str, dict[str, Any]]:
    overrides = rules.get("manual_overrides") or rules.get("retained_overrides") or []
    if isinstance(overrides, dict):
        return {str(key): value for key, value in overrides.items() if isinstance(value, dict)}
    result: dict[str, dict[str, Any]] = {}
    if isinstance(overrides, list):
        for item in overrides:
            if isinstance(item, dict) and item.get("symbol"):
                result[str(item["symbol"])] = item
    return result


def _selected_reason(item: dict[str, Any]) -> str:
    return str(item.get("selected_reason") or item.get("selected_as") or item.get("change_tag") or "")


def _load_feature_snapshot(features_file: str | None, active_date: str) -> pd.DataFrame:
    if not features_file:
        return pd.DataFrame()
    frame = read_dataset_flex(features_file)
    if frame.empty or "symbol" not in frame.columns:
        return pd.DataFrame()
    if active_date and "date" in frame.columns:
        frame = frame[frame["date"].astype(str) == str(active_date)].copy()
    return frame.drop_duplicates(subset=["symbol"], keep="last")


def _feature_lookup(frame: pd.DataFrame) -> dict[str, dict[str, Any]]:
    if frame.empty or "symbol" not in frame.columns:
        return {}
    return {str(row.get("symbol")): row for row in frame.to_dict(orient="records")}


def _enrich_constituent(item: dict[str, Any], feature_row: dict[str, Any] | None, active_date: str, features_file: str | None) -> dict[str, Any]:
    enriched = dict(item)
    if not feature_row:
        enriched["feature_row_found"] = False
        enriched["data_source"] = "config/universe.yml"
        enriched["data_path"] = "config/universe.yml"
        return enriched
    enriched["feature_row_found"] = True
    enriched["feature_data_path"] = features_file
    enriched["feature_data_asof"] = str(feature_row.get("date") or active_date)
    preserve_if_present = {"bucket", "main_metric", "stock_q_blended", "industry_q_blended"}
    for field in (
        "name",
        "industry",
        "industry_l1",
        "bucket",
        "main_metric",
        "market_cap_billion",
        "avg_amount_60d_million",
        "pb",
        "pe_ttm",
        "roe",
        "dv_ttm",
        "latest_net_profit",
        "debt_to_assets",
        "cfo_ttm",
        "stock_pb_q_blended",
        "industry_pb_q_blended",
        "stock_pe_ttm_q_blended",
        "industry_pe_ttm_q_blended",
        "stock_q_blended",
        "industry_q_blended",
        "industry_market_cap_rank",
        "industry_market_cap_percentile",
        "listed_days",
        "is_a_share",
        "is_st",
        "cycle_peak_trap",
        "effective_date",
        "announcement_date",
        "report_date",
    ):
        if field in preserve_if_present and not _is_missing(enriched.get(field)):
            continue
        value = feature_row.get(field)
        if not _is_missing(value):
            enriched[field] = value
    if _is_missing(enriched.get("industry_l1")) and not _is_missing(enriched.get("industry")):
        enriched["industry_l1"] = enriched.get("industry")
    if _is_missing(enriched.get("industry")) and not _is_missing(enriched.get("industry_l1")):
        enriched["industry"] = enriched.get("industry_l1")
    if _is_missing(enriched.get("data_asof")):
        enriched["data_asof"] = enriched.get("feature_data_asof")
    enriched["data_source"] = "data/features/daily_features;config/universe.yml"
    enriched["data_path"] = features_file or "data/features/daily_features"
    return enriched


def build_universe_integrity_report(
    *,
    universe_file: str = "config/universe.yml",
    rules_file: str = "config/universe_rules_v2.yml",
    features_file: str | None = "data/features/daily_features",
    mode: str = "strict",
    write_report: bool = True,
    universe_payload: dict[str, Any] | None = None,
    rules_payload: dict[str, Any] | None = None,
    feature_frame: pd.DataFrame | None = None,
) -> dict[str, Any]:
    universe = universe_payload if universe_payload is not None else load_yaml(universe_file)
    rules = rules_payload if rules_payload is not None else load_yaml(rules_file)
    metric_map = load_yaml("config/metric_map.yml")
    stocks = universe.get("stocks", []) or []
    target_size = int(rules.get("target_size", rules.get("target_universe_size", 0)) or 0)
    floor_size = int(rules.get("floor_size", rules.get("target_universe_floor", 0)) or 0)
    ceiling_size = int(rules.get("ceiling_size", rules.get("target_universe_ceiling", 10**9)) or 10**9)
    max_per_industry = int(rules.get("max_per_industry", rules.get("max_names_per_industry", 10**9)) or 10**9)
    base_filters = (rules.get("bucket_filters", {}) or {}).get("base", {}) or {}
    overrides = _override_config(rules)
    allow_research_underfill = bool(rules.get("allow_underfilled_universe_for_research", False))
    violations: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    constituents: list[dict[str, Any]] = []
    active_date = _date_value(universe)
    should_load_features = feature_frame is not None or (universe_payload is None and features_file)
    feature_snapshot = feature_frame if feature_frame is not None else _load_feature_snapshot(features_file, active_date) if should_load_features else pd.DataFrame()
    feature_rows = _feature_lookup(feature_snapshot)

    selected_count = len(stocks)
    if floor_size and selected_count < floor_size:
        severity = "WARN" if mode == "research" and allow_research_underfill else "FAIL"
        target = warnings if severity == "WARN" else violations
        target.append(
            {
                "code": "UNIVERSE_UNDER_FLOOR",
                "message": "selected universe count is below configured floor",
                "expected": f">={floor_size}",
                "actual": selected_count,
                "source": f"{universe_file};{rules_file}",
            }
        )
    elif target_size and selected_count < target_size:
        warnings.append(
            {
                "code": "UNIVERSE_BELOW_TARGET",
                "message": "selected universe count is below configured target but above floor",
                "expected": f">={target_size}",
                "actual": selected_count,
                "source": f"{universe_file};{rules_file}",
            }
        )
    if selected_count > ceiling_size:
        violations.append(
            {
                "code": "UNIVERSE_ABOVE_CEILING",
                "message": "selected universe count is above configured ceiling",
                "expected": f"<={ceiling_size}",
                "actual": selected_count,
                "source": f"{universe_file};{rules_file}",
            }
        )

    industry_counts = Counter(str(item.get("industry_l1") or item.get("industry") or "UNKNOWN") for item in stocks)
    for industry, count in sorted(industry_counts.items()):
        if count > max_per_industry:
            violations.append(
                {
                    "code": "INDUSTRY_CAP_EXCEEDED",
                    "message": "selected universe exceeds max_per_industry",
                    "expected": max_per_industry,
                    "actual": count,
                    "industry": industry,
                    "source": rules_file,
                }
            )

    for item in stocks:
        symbol = str(item.get("symbol") or item.get("code") or "")
        enriched = _enrich_constituent(item, feature_rows.get(symbol), active_date, features_file)
        retained = str(item.get("selected_as", "")).lower() == "retained"
        manual_override = str(item.get("selected_as", "")).lower() in {"manual_override", "override"} or symbol in overrides
        hard_results = _hard_filter_results(
            enriched,
            rules,
            metric_map,
            enriched.get("data_path") or universe_file,
            str(enriched.get("data_asof") or universe.get("as_of_date") or ""),
        )
        failed_filters = hard_results["failed_filters"]
        missing = hard_results["missing_fields"]
        override = overrides.get(symbol, {})
        override_has_basis = bool(override.get("reason") and (override.get("effective_date") or override.get("as_of_date")))
        if should_load_features and symbol not in feature_rows:
            violations.append(
                {
                    "code": "FEATURE_ROW_MISSING",
                    "symbol": symbol,
                    "message": "selected constituent has no matching feature row for active date",
                    "active_date": active_date,
                    "source": features_file,
                }
            )
        if missing:
            violations.append(
                {
                    "code": "MISSING_KEY_FIELDS",
                    "symbol": symbol,
                    "message": "selected constituent misses required fields",
                    "fields": missing,
                    "source": enriched.get("data_path") or universe_file,
                }
            )
        if failed_filters:
            if manual_override and override_has_basis:
                warnings.append(
                    {
                        "code": "HARD_FILTER_OVERRIDE_USED",
                        "symbol": symbol,
                        "message": "hard filter violation allowed by explicit override",
                        "failed_filters": failed_filters,
                        "override_reason": override.get("reason"),
                        "override_effective_date": override.get("effective_date") or override.get("as_of_date"),
                        "source": rules_file,
                    }
                )
            else:
                violations.append(
                    {
                        "code": "HARD_FILTER_VIOLATION",
                        "symbol": symbol,
                        "message": "selected constituent violates hard filters without explicit override basis",
                        "failed_filters": failed_filters,
                        "selected_as": item.get("selected_as"),
                        "source": enriched.get("data_path") or universe_file,
                    }
                )
        if manual_override and not override_has_basis:
            violations.append(
                {
                    "code": "MANUAL_OVERRIDE_WITHOUT_BASIS",
                    "symbol": symbol,
                    "message": "manual override/retained override lacks reason and effective date",
                    "selected_as": item.get("selected_as"),
                    "source": rules_file,
                }
            )
        constituents.append(
            {
                "symbol": symbol,
                "code": symbol,
                "name": enriched.get("name"),
                "industry": enriched.get("industry_l1") or enriched.get("industry"),
                "bucket": enriched.get("bucket"),
                "market_cap_billion": _field_value(enriched, "market_cap_billion"),
                "pe": _field_value(enriched, "pe_ttm"),
                "pb": _field_value(enriched, "pb"),
                "dividend_yield": _field_value(enriched, "dv_ttm"),
                "roe": _field_value(enriched, "roe"),
                "latest_net_profit": _field_value(enriched, "latest_net_profit"),
                "debt_to_assets": _field_value(enriched, "debt_to_assets"),
                "selected_reason": _selected_reason(enriched),
                "retained": retained,
                "manual_override": manual_override,
                "override_reason": override.get("reason") if override else None,
                "override_effective_date": override.get("effective_date") or override.get("as_of_date") if override else None,
                "failed_filters": failed_filters,
                "missing_fields": missing,
                "hard_filter_results": hard_results,
                "data_source": enriched.get("data_source") or universe_file,
                "data_path": enriched.get("data_path") or universe_file,
                "data_asof": enriched.get("data_asof") or universe.get("as_of_date"),
                "effective_date": universe.get("effective_from"),
                "financial_effective_date": _date_or_none(enriched.get("effective_date") or enriched.get("financial_effective_date")),
            }
        )

    status = status_from_children(["FAIL" if violations else "WARN" if warnings else "PASS"])
    payload = {
        **metadata_header(
            requested_date=str(universe.get("as_of_date", "")),
            target_trade_date=str(universe.get("as_of_date", "")),
            extra_config_paths=[universe_file, rules_file],
        ),
        "status": status,
        "checked_at": metadata_header()["generated_at"],
        "git_commit": metadata_header()["git_commit"],
        "universe_file": universe_file,
        "rules_file": rules_file,
        "features_file": features_file,
        "active_date": active_date,
        "target_trade_date": str(universe.get("as_of_date", "")),
        "selected_count": selected_count,
        "target_size": target_size,
        "floor": floor_size,
        "ceiling": ceiling_size,
        "max_per_industry": max_per_industry,
        "market_cap_billion_min": base_filters.get("market_cap_billion_min"),
        "hard_filter_thresholds": rules.get("bucket_filters", {}),
        "retained_rules": {
            "retained_min_score": rules.get("retained_min_score"),
            "retained_industry_rank": rules.get("retained_industry_rank"),
            "retained_any_rank_score": rules.get("retained_any_rank_score"),
        },
        "violations": violations,
        "warnings": warnings,
        "constituents": constituents,
    }
    if write_report:
        write_json(JSON_PATH, payload)
        _write_md(payload, MD_PATH)
    return payload


def _write_md(payload: dict[str, Any], path_like: str | Path) -> None:
    path = resolve_path(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# universe integrity audit",
        "",
        f"- status: {payload['status']}",
        f"- checked_at: {payload['checked_at']}",
        f"- git_commit: {payload['git_commit']}",
        f"- config_hash: {payload['config_hash']}",
        f"- universe_file: {payload['universe_file']}",
        f"- rules_file: {payload['rules_file']}",
        f"- active_date: {payload['active_date']}",
        f"- selected_count: {payload['selected_count']}",
        f"- target/floor/ceiling: {payload['target_size']} / {payload['floor']} / {payload['ceiling']}",
        f"- max_per_industry: {payload['max_per_industry']}",
        f"- market_cap_billion_min: {payload['market_cap_billion_min']}",
        "",
        "## FAIL",
        "",
    ]
    lines.extend(
        [
            f"- {item['code']}: {item.get('symbol', item.get('industry', ''))} {item['message']} actual={item.get('actual', item.get('failed_filters', item.get('fields', '')))}"
            for item in payload.get("violations", [])
        ]
        or ["- 无"]
    )
    lines.extend(["", "## WARN", ""])
    lines.extend(
        [
            f"- {item['code']}: {item.get('symbol', '')} {item['message']} actual={item.get('actual', item.get('failed_filters', ''))}"
            for item in payload.get("warnings", [])
        ]
        or ["- 无"]
    )
    lines.extend(["", "## Constituents", ""])
    for item in payload.get("constituents", []):
        failed = ",".join(item.get("failed_filters") or []) or "none"
        lines.append(
            f"- {item['symbol']} {item.get('name') or ''} | {item.get('industry') or ''} | {item.get('bucket') or ''} | market_cap_billion={item.get('market_cap_billion')} | selected_reason={item.get('selected_reason')} | failed_filters={failed}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit active effective universe integrity.")
    parser.add_argument("--universe-file", default="config/universe.yml")
    parser.add_argument("--rules-file", default="config/universe_rules_v2.yml")
    parser.add_argument("--features-file", default="data/features/daily_features")
    parser.add_argument("--mode", choices=["strict", "research"], default="strict")
    parser.add_argument("--no-write-report", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_universe_integrity_report(
        universe_file=args.universe_file,
        rules_file=args.rules_file,
        features_file=args.features_file,
        mode=args.mode,
        write_report=not args.no_write_report,
    )
    return 1 if report["status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
