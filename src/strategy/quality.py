from __future__ import annotations

import math

import pandas as pd


RULE_STATUS_SOURCE_MISSING = "source_missing"
RULE_STATUS_INSUFFICIENT_HISTORY = "insufficient_history"
RULE_STATUS_TTM_NON_POSITIVE = "ttm_non_positive"
RULE_STATUS_EQUITY_NON_POSITIVE = "equity_non_positive"


def _as_float(value: object, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(numeric):
        return default
    return numeric


def _as_float_or_nan(value: object) -> float:
    if value is None:
        return math.nan
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return math.nan
    if math.isnan(numeric):
        return math.nan
    return numeric


def metric_rule_status(row: dict | pd.Series, status_column: str, default: str = "ok") -> str:
    status = row.get(status_column)
    if status is None or pd.isna(status):
        return default
    value = str(status).strip()
    return value if value else default


def metric_value_for_rules(row: dict | pd.Series, raw_column: str, rule_column: str | None = None) -> float:
    if rule_column:
        rule_value = _as_float_or_nan(row.get(rule_column))
        if not math.isnan(rule_value):
            return rule_value
    return _as_float_or_nan(row.get(raw_column))


def metric_failure_reason(metric: str, status: str) -> str:
    if status in {
        RULE_STATUS_SOURCE_MISSING,
        RULE_STATUS_INSUFFICIENT_HISTORY,
        RULE_STATUS_TTM_NON_POSITIVE,
        RULE_STATUS_EQUITY_NON_POSITIVE,
    }:
        return f"{metric}_{status}"
    return metric


def percentile_rank(series: pd.Series, current: float | None = None) -> float:
    values = pd.to_numeric(series, errors="coerce").dropna()
    if values.empty:
        return 0.0
    if current is None:
        current = float(values.iloc[-1])
    return float((values <= float(current)).sum() / len(values) * 100.0)


def evaluate_quality(row: dict | pd.Series, filters_cfg: dict) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    row = dict(row)
    if float(row.get("listed_days", 0)) < float(filters_cfg.get("listed_days_min", 0)):
        reasons.append("listed_days")
    if bool(filters_cfg.get("not_st_required")) and not bool(row.get("not_st", False)):
        reasons.append("not_st")
    if float(row.get("market_cap_billion", 0)) < float(filters_cfg.get("market_cap_billion_min", 0)):
        reasons.append("market_cap")
    if float(row.get("avg_amount_60d_million", 0)) < float(filters_cfg.get("avg_amount_60d_million_min", 0)):
        reasons.append("avg_amount_60d_million")
    roe_status = metric_rule_status(row, "roe_rule_status")
    roe_value = metric_value_for_rules(row, "roe", "roe_rule_value")
    if math.isnan(roe_value) or roe_value < float(filters_cfg.get("roe_min", 0)):
        reasons.append(metric_failure_reason("roe", roe_status))
    if float(row.get("latest_net_profit", 0)) <= float(filters_cfg.get("latest_net_profit_min_exclusive", -10**18)):
        reasons.append("latest_net_profit")
    cfo_status = metric_rule_status(row, "cfo_ttm_rule_status")
    cfo_value = metric_value_for_rules(row, "cfo_ttm", "cfo_ttm_rule_value")
    if "cfo_ttm_min_exclusive" in filters_cfg and (
        math.isnan(cfo_value) or cfo_value <= float(filters_cfg["cfo_ttm_min_exclusive"])
    ):
        reasons.append(metric_failure_reason("cfo_ttm", cfo_status))
    if "debt_to_assets_max" in filters_cfg and float(row.get("debt_to_assets", 10**9)) > float(
        filters_cfg["debt_to_assets_max"]
    ):
        reasons.append("debt_to_assets")
    if "dv_ttm_min" in filters_cfg and float(row.get("dv_ttm", 0)) < float(filters_cfg["dv_ttm_min"]):
        reasons.append("dv_ttm")
    pb_status = metric_rule_status(row, "pb_rule_status")
    pb_value = metric_value_for_rules(row, "pb", "pb_rule_value")
    if "pb_min_exclusive" in filters_cfg and (math.isnan(pb_value) or pb_value <= float(filters_cfg["pb_min_exclusive"])):
        reasons.append(metric_failure_reason("pb", pb_status))
    if "pe_ttm_max_when_primary_metric" in filters_cfg and row.get("main_metric") == "pe_ttm":
        pe_status = metric_rule_status(row, "pe_ttm_rule_status")
        pe_ttm = metric_value_for_rules(row, "pe_ttm", "pe_ttm_rule_value")
        if math.isnan(pe_ttm) or pe_ttm <= 0 or pe_ttm > float(filters_cfg["pe_ttm_max_when_primary_metric"]):
            reasons.append(metric_failure_reason("pe_ttm", pe_status))
    if "pb_q_blended_max_when_primary_metric" in filters_cfg and row.get("main_metric") == "pb":
        pb_status = metric_rule_status(row, "pb_rule_status")
        pb_value = metric_value_for_rules(row, "pb", "pb_rule_value")
        pb_q_blended = metric_value_for_rules(row, "stock_pb_q_blended", "stock_pb_q_blended_rule_value")
        if (
            math.isnan(pb_value)
            or pb_value <= 0
            or math.isnan(pb_q_blended)
            or pb_q_blended > float(filters_cfg["pb_q_blended_max_when_primary_metric"])
        ):
            reasons.append(metric_failure_reason("pb_q_blended", pb_status))
    return (len(reasons) == 0, reasons)


def roe_percentile_in_last_12_quarters(latest_row: dict | pd.Series, history_frame: pd.DataFrame, lookback_quarters: int = 12) -> float:
    latest = dict(latest_row)
    if history_frame.empty:
        return 0.0
    ordered = history_frame.sort_values("date").tail(int(lookback_quarters))
    if ordered.empty:
        return 0.0
    latest_roe = latest.get("roe")
    if latest_roe is None or pd.isna(latest_roe):
        if "roe" not in ordered.columns or ordered["roe"].dropna().empty:
            return 0.0
        latest_roe = ordered["roe"].dropna().iloc[-1]
    return percentile_rank(ordered["roe"], current=float(latest_roe))


def is_cycle_peak_trap(latest_row: dict | pd.Series, history_frame: pd.DataFrame, cycle_cfg: dict, trading_days: int) -> bool:
    del trading_days
    latest = dict(latest_row)
    pe_q_blended = latest.get("pe_q_blended")
    if pe_q_blended is None or pd.isna(pe_q_blended):
        pe_q_blended = latest.get("stock_pe_ttm_q_blended", latest.get("pe_ttm_quantile_3y"))
    if pe_q_blended is None or pd.isna(pe_q_blended):
        return False
    roe_pct = latest.get("roe_pct_in_last_12_quarters")
    if roe_pct is None or pd.isna(roe_pct):
        roe_pct = roe_percentile_in_last_12_quarters(latest, history_frame, int(cycle_cfg.get("lookback_quarters", 12)))
    primary_trigger = bool(
        float(pe_q_blended) <= float(cycle_cfg["pe_q_blended_max_primary"])
        and float(roe_pct) >= float(cycle_cfg["roe_pct_in_last_12_quarters_min_primary"])
    )
    secondary_trigger = bool(
        float(pe_q_blended) <= float(cycle_cfg["pe_q_blended_max_secondary"])
        and float(roe_pct) >= float(cycle_cfg["roe_pct_in_last_12_quarters_min_secondary"])
    )
    return primary_trigger or secondary_trigger
