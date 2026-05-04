from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import pandas as pd

from src.strategy.metric_map import metric_for_industry_optional


@dataclass(frozen=True)
class ValuationQuantileResolution:
    value: float
    source_field: str
    metric: str
    fallback_used: bool
    fallback_reason: str
    available_date: str
    source_max_date: str


def _get(row: Mapping | pd.Series, key: str, default: object = None) -> object:
    try:
        if isinstance(row, pd.Series):
            return row.get(key, default)
        return row.get(key, default)
    except AttributeError:
        return default


def _safe_float(value: object, default: float | None = None) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(numeric):
        return default
    return numeric


def _date_value(row: Mapping | pd.Series, *keys: str) -> str:
    for key in keys:
        value = _get(row, key)
        if value is None or pd.isna(value):
            continue
        return str(value)
    return ""


def _metric_for_bucket(row: Mapping | pd.Series, bucket: str, metric_map_cfg: dict | None) -> tuple[str, bool, str]:
    if bucket == "cyclical_rotation":
        return "pb", False, ""

    industry = str(_get(row, "industry", "") or "")
    metric = None
    if metric_map_cfg:
        metric = metric_for_industry_optional(industry, metric_map_cfg)
        if metric is None:
            metric = (metric_map_cfg.get("bucket_default_metric", {}) or {}).get(bucket)
    if metric is None:
        metric = _get(row, "main_metric") or _get(row, "universe_main_metric")
    if metric not in {"pb", "pe_ttm"}:
        metric = "pe_ttm"

    pe_ttm = _get(row, "pe_ttm")
    if metric == "pe_ttm" and pd.isna(pe_ttm):
        return "pb", True, "pe_ttm_missing_fallback_to_pb"
    return str(metric), False, ""


def _resolve_quantile(
    row: Mapping | pd.Series,
    bucket: str,
    metric_map_cfg: dict | None,
    scope: str,
) -> ValuationQuantileResolution:
    metric, metric_fallback, metric_reason = _metric_for_bucket(row, bucket, metric_map_cfg)
    preferred_field = f"{scope}_{metric}_q_blended" if scope == "stock" else f"industry_{metric}_q_blended"
    generic_field = f"{scope}_valuation_quantile"
    broad_alias = f"{scope}_q_blended" if scope == "stock" else "industry_q_blended"

    fallback_used = metric_fallback
    fallback_reason_parts = [metric_reason] if metric_reason else []
    for field in (preferred_field, generic_field, broad_alias):
        value = _safe_float(_get(row, field), None)
        if value is not None:
            if field != preferred_field:
                fallback_used = True
                fallback_reason_parts.append(f"{preferred_field}_missing_used_{field}")
            return ValuationQuantileResolution(
                value=value,
                source_field=field,
                metric=metric,
                fallback_used=fallback_used,
                fallback_reason=";".join(fallback_reason_parts),
                available_date=_date_value(row, "available_date", "date"),
                source_max_date=_date_value(row, f"{preferred_field}_source_max_date", "source_max_date"),
            )

    fallback_reason_parts.append(f"{preferred_field}_missing")
    return ValuationQuantileResolution(
        value=100.0,
        source_field="",
        metric=metric,
        fallback_used=True,
        fallback_reason=";".join(fallback_reason_parts),
        available_date=_date_value(row, "available_date", "date"),
        source_max_date=_date_value(row, f"{preferred_field}_source_max_date", "source_max_date"),
    )


def resolve_stock_valuation_quantile(
    row: Mapping | pd.Series,
    bucket: str,
    metric_map_cfg: dict | None,
) -> ValuationQuantileResolution:
    return _resolve_quantile(row, bucket, metric_map_cfg, "stock")


def resolve_industry_valuation_quantile(
    row: Mapping | pd.Series,
    bucket: str,
    metric_map_cfg: dict | None,
) -> ValuationQuantileResolution:
    return _resolve_quantile(row, bucket, metric_map_cfg, "industry")
