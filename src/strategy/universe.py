from __future__ import annotations

import os
from collections import Counter
from pathlib import Path

import pandas as pd

from src.strategy.fundamentals import force_exit_reasons
from src.strategy.metric_map import candidate_buckets_for_industry, is_financial_industry, metric_for_industry
from src.strategy.quality import metric_failure_reason, metric_rule_status, metric_value_for_rules
from src.strategy.valuation_resolution import resolve_industry_valuation_quantile, resolve_stock_valuation_quantile
from src.utils.config import resolve_path


def effective_universe_frame(universe_cfg: dict) -> pd.DataFrame:
    stocks = universe_cfg.get("stocks", []) or []
    if not stocks:
        return pd.DataFrame(columns=["symbol"])
    return pd.DataFrame(stocks)


def effective_universe_symbols(universe_cfg: dict) -> list[str]:
    frame = effective_universe_frame(universe_cfg)
    if frame.empty or "symbol" not in frame.columns:
        return []
    return frame["symbol"].astype(str).tolist()


def whitelist_symbols(universe_cfg: dict) -> list[str]:
    return effective_universe_symbols(universe_cfg)


def is_rebalance_day(feature_frame: pd.DataFrame, as_of_date: str, frequency: str) -> bool:
    if feature_frame.empty:
        return True
    dates = sorted(pd.to_datetime(feature_frame["date"].dropna().unique()))
    current = pd.Timestamp(as_of_date)
    same_period_dates = [date for date in dates if date >= current]
    if not same_period_dates:
        return True
    if frequency == "quarterly" and current.month not in {3, 6, 9, 12}:
        return False
    period_end = current.to_period("Q").end_time.normalize() if frequency == "quarterly" else current.to_period("M").end_time.normalize()
    future_same_period = [date for date in dates if date > current and date <= period_end]
    return len(future_same_period) == 0


def next_trading_day(feature_frame: pd.DataFrame, as_of_date: str) -> str:
    if not feature_frame.empty:
        future = sorted(pd.to_datetime(feature_frame.loc[feature_frame["date"] > as_of_date, "date"].unique()))
        if future:
            return future[0].strftime("%Y-%m-%d")
    return (pd.Timestamp(as_of_date) + pd.offsets.BDay(1)).strftime("%Y-%m-%d")


def effective_to_date(as_of_date: str, frequency: str) -> str:
    current = pd.Timestamp(as_of_date)
    if frequency == "quarterly":
        current_quarter_end = current.to_period("Q").end_time.normalize()
        return (current_quarter_end + pd.offsets.QuarterEnd(1)).strftime("%Y-%m-%d")
    current_month_end = current.to_period("M").end_time.normalize()
    return (current_month_end + pd.offsets.MonthEnd(1)).strftime("%Y-%m-%d")


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(numeric):
        return default
    return numeric


def _is_v2_rules(universe_rules_cfg: dict) -> bool:
    return str(universe_rules_cfg.get("profile", universe_rules_cfg.get("methodology_version", ""))).startswith("combined_v2")


def _linear_score(value: float, low: float, high: float, low_score: float, high_score: float) -> float:
    if value <= low:
        return low_score
    if value >= high:
        return high_score
    ratio = (value - low) / max(high - low, 1e-9)
    return low_score + ratio * (high_score - low_score)


def _main_metric_for_bucket(industry: str, bucket: str, metric_map_cfg: dict) -> str:
    if bucket == "cyclical_rotation":
        return "pb"
    return metric_for_industry(industry, metric_map_cfg)


def _main_metric_status(row: pd.Series, main_metric: str) -> str:
    status_column = "pb_rule_status" if main_metric == "pb" else "pe_ttm_rule_status"
    return metric_rule_status(row, status_column)


def _main_metric_history_value(row: pd.Series, main_metric: str) -> float:
    raw_column = f"stock_{main_metric}_history_observations"
    return metric_value_for_rules(row, raw_column, f"{raw_column}_rule_value")


def _score_row_v2(row: pd.Series, bucket: str, metric_map_cfg: dict) -> dict[str, float]:
    main_metric = _main_metric_for_bucket(str(row["industry"]), bucket, metric_map_cfg)
    is_financial = is_financial_industry(str(row.get("industry", "")), metric_map_cfg)
    stock_pb_q = _safe_float(row.get("stock_pb_q_blended"), default=100.0)
    industry_pb_q = _safe_float(row.get("industry_pb_q_blended"), default=100.0)
    stock_resolution = resolve_stock_valuation_quantile(row, bucket, metric_map_cfg)
    industry_resolution = resolve_industry_valuation_quantile(row, bucket, metric_map_cfg)
    stock_valuation_quantile = stock_resolution.value
    industry_valuation_quantile = industry_resolution.value

    pe_ttm = row.get("pe_ttm")
    pe_valid = not pd.isna(pe_ttm) and _safe_float(pe_ttm) > 0
    if pe_valid and _safe_float(pe_ttm) <= 15:
        pe_or_pb_reasonable_score = 100.0
    elif pe_valid and _safe_float(pe_ttm) <= 25:
        pe_or_pb_reasonable_score = _linear_score(_safe_float(pe_ttm), 15.0, 25.0, 100.0, 60.0)
    elif (not pe_valid) and stock_pb_q <= 40:
        pe_or_pb_reasonable_score = 75.0
    else:
        pe_or_pb_reasonable_score = 50.0

    roe = _safe_float(row.get("roe"), default=float("nan"))
    if pd.isna(roe):
        roe_score = 0.0
    elif bucket == "defensive_dividend":
        roe_score = 100.0 if roe >= 15 else _linear_score(roe, 6.0, 15.0, 60.0, 100.0) if roe >= 6 else 0.0
    else:
        roe_score = 100.0 if roe >= 15 else _linear_score(roe, 3.0, 15.0, 50.0, 100.0) if roe >= 3 else 0.0

    cfo_value = row.get("cfo_ttm")
    if is_financial:
        cfo_score = 60.0
    elif pd.isna(cfo_value):
        cfo_score = 50.0
    else:
        cfo_score = 100.0 if _safe_float(cfo_value) > 0 else 40.0

    debt_value = row.get("debt_to_assets")
    if is_financial:
        debt_score = 60.0
    elif pd.isna(debt_value):
        debt_score = 50.0
    else:
        debt = _safe_float(debt_value)
        if debt <= 60:
            debt_score = 100.0
        elif debt <= 85:
            debt_score = _linear_score(debt, 60.0, 85.0, 100.0, 60.0)
        else:
            debt_score = 0.0

    profit_score = 100.0 if _safe_float(row.get("latest_net_profit")) > 0 else 0.0
    dividend_yield = _safe_float(row.get("dv_ttm"))
    if dividend_yield >= 0.05:
        dividend_score = 100.0
    elif dividend_yield >= 0.025:
        dividend_score = _linear_score(dividend_yield, 0.025, 0.05, 60.0, 100.0)
    else:
        dividend_score = 0.0
    size_score = _safe_float(row.get("market_cap_percentile"))
    liquidity_score = _safe_float(row.get("avg_amount_60d_percentile"))
    cycle_safety_score = 0.0 if bool(row.get("cycle_peak_trap")) else 100.0

    if bucket == "defensive_dividend":
        valuation_score = (
            0.50 * (100.0 - stock_valuation_quantile)
            + 0.30 * (100.0 - industry_valuation_quantile)
            + 0.20 * pe_or_pb_reasonable_score
        )
        quality_score = 0.35 * roe_score + 0.25 * cfo_score + 0.20 * debt_score + 0.20 * profit_score
        leader_score = 0.60 * size_score + 0.40 * liquidity_score
        final_score = 0.35 * valuation_score + 0.30 * quality_score + 0.20 * dividend_score + 0.15 * leader_score
    else:
        valuation_score = 0.55 * (100.0 - stock_pb_q) + 0.45 * (100.0 - industry_pb_q)
        quality_score = 0.40 * roe_score + 0.25 * cfo_score + 0.20 * debt_score + 0.15 * profit_score
        leader_score = 0.70 * size_score + 0.30 * liquidity_score
        final_score = 0.40 * valuation_score + 0.25 * quality_score + 0.20 * leader_score + 0.15 * cycle_safety_score

    return {
        "main_metric": main_metric,
        "stock_main_q_blended": stock_valuation_quantile,
        "industry_main_q_blended": industry_valuation_quantile,
        "stock_valuation_quantile": stock_valuation_quantile,
        "stock_valuation_quantile_source_field": stock_resolution.source_field,
        "stock_valuation_metric": stock_resolution.metric,
        "industry_valuation_quantile": industry_valuation_quantile,
        "industry_valuation_quantile_source_field": industry_resolution.source_field,
        "industry_valuation_metric": industry_resolution.metric,
        "valuation_fallback_used": bool(stock_resolution.fallback_used or industry_resolution.fallback_used),
        "valuation_fallback_reason": ";".join(
            reason
            for reason in (stock_resolution.fallback_reason, industry_resolution.fallback_reason)
            if reason
        ),
        "cheap_score": 100.0 - stock_valuation_quantile,
        "industry_cheap_score": 100.0 - industry_valuation_quantile,
        "size_score": size_score,
        "liquidity_score": liquidity_score,
        "roe_score": roe_score,
        "debt_score": debt_score,
        "cfo_score": cfo_score,
        "profit_score": profit_score,
        "dividend_score": dividend_score,
        "valuation_score": valuation_score,
        "quality_score": quality_score,
        "leader_score": leader_score,
        "cycle_safety_score": cycle_safety_score,
        "final_score": final_score,
    }


def _score_row(
    row: pd.Series,
    bucket: str,
    scoring_cfg: dict,
    metric_map_cfg: dict,
    universe_rules_cfg: dict | None = None,
) -> dict[str, float]:
    if universe_rules_cfg and _is_v2_rules(universe_rules_cfg):
        return _score_row_v2(row, bucket, metric_map_cfg)
    main_metric = _main_metric_for_bucket(str(row["industry"]), bucket, metric_map_cfg)
    stock_main_q_blended = _safe_float(row.get(f"stock_{main_metric}_q_blended"), default=100.0)
    industry_main_q_blended = _safe_float(row.get(f"industry_{main_metric}_q_blended"), default=100.0)
    cheap_score = 100.0 - stock_main_q_blended
    industry_cheap_score = 100.0 - industry_main_q_blended
    size_score = _safe_float(row.get("market_cap_percentile"))
    liquidity_score = _safe_float(row.get("avg_amount_60d_percentile"))
    roe_score = _safe_float(row.get("roe_percentile"))
    debt_score = 100.0 - _safe_float(row.get("debt_to_assets_percentile"))
    cfo_score = 100.0 if _safe_float(row.get("cfo_ttm")) > 0 else 0.0
    dividend_score = _safe_float(row.get("dv_ttm_percentile"))
    pe_ttm_percentile_if_available = _safe_float(row.get("stock_pe_ttm_q_blended"), default=50.0)
    profit_positive_stability_score = _safe_float(row.get("profit_positive_stability_score"))
    stock_pb_q_blended = _safe_float(row.get("stock_pb_q_blended"), default=100.0)
    industry_pb_q_blended = _safe_float(row.get("industry_pb_q_blended"), default=100.0)

    if bucket == "defensive_dividend":
        valuation_score = (
            cheap_score * float(scoring_cfg[bucket]["valuation"]["cheap_score"])
            + industry_cheap_score * float(scoring_cfg[bucket]["valuation"]["industry_cheap_score"])
            + dividend_score * float(scoring_cfg[bucket]["valuation"]["dividend_score"])
            + (100.0 - pe_ttm_percentile_if_available) * float(scoring_cfg[bucket]["valuation"]["pe_discount_score"])
        )
        quality_score = (
            roe_score * float(scoring_cfg[bucket]["quality"]["roe_score"])
            + cfo_score * float(scoring_cfg[bucket]["quality"]["cfo_score"])
            + debt_score * float(scoring_cfg[bucket]["quality"]["debt_score"])
            + dividend_score * float(scoring_cfg[bucket]["quality"]["dividend_score"])
        )
        leader_score = (
            size_score * float(scoring_cfg[bucket]["leader"]["size_score"])
            + liquidity_score * float(scoring_cfg[bucket]["leader"]["liquidity_score"])
        )
        final_score = (
            valuation_score * float(scoring_cfg[bucket]["final"]["valuation_score_def"])
            + quality_score * float(scoring_cfg[bucket]["final"]["quality_score_def"])
            + leader_score * float(scoring_cfg[bucket]["final"]["leader_score_def"])
        )
        cycle_safety_score = 100.0
    else:
        valuation_score = (
            (100.0 - stock_pb_q_blended) * float(scoring_cfg[bucket]["valuation"]["stock_pb_cheap_score"])
            + (100.0 - industry_pb_q_blended) * float(scoring_cfg[bucket]["valuation"]["industry_pb_cheap_score"])
        )
        quality_score = (
            roe_score * float(scoring_cfg[bucket]["quality"]["roe_score"])
            + cfo_score * float(scoring_cfg[bucket]["quality"]["cfo_score"])
            + debt_score * float(scoring_cfg[bucket]["quality"]["debt_score"])
            + profit_positive_stability_score * float(scoring_cfg[bucket]["quality"]["profit_positive_stability_score"])
        )
        leader_score = (
            size_score * float(scoring_cfg[bucket]["leader"]["size_score"])
            + liquidity_score * float(scoring_cfg[bucket]["leader"]["liquidity_score"])
        )
        cycle_safety_score = 0.0 if bool(row.get("cycle_peak_trap")) else 100.0
        final_score = (
            valuation_score * float(scoring_cfg[bucket]["final"]["valuation_score_cyc"])
            + quality_score * float(scoring_cfg[bucket]["final"]["quality_score_cyc"])
            + leader_score * float(scoring_cfg[bucket]["final"]["leader_score_cyc"])
            + cycle_safety_score * float(scoring_cfg[bucket]["final"]["cycle_safety_score"])
        )
    return {
        "main_metric": main_metric,
        "stock_main_q_blended": stock_main_q_blended,
        "industry_main_q_blended": industry_main_q_blended,
        "cheap_score": cheap_score,
        "industry_cheap_score": industry_cheap_score,
        "size_score": size_score,
        "liquidity_score": liquidity_score,
        "roe_score": roe_score,
        "debt_score": debt_score,
        "cfo_score": cfo_score,
        "dividend_score": dividend_score,
        "valuation_score": valuation_score,
        "quality_score": quality_score,
        "leader_score": leader_score,
        "cycle_safety_score": cycle_safety_score,
        "final_score": final_score,
    }


def _base_filter_reasons(row: pd.Series, universe_rules_cfg: dict, main_metric: str, trading_days: int) -> list[str]:
    base_cfg = universe_rules_cfg["bucket_filters"]["base"]
    reasons: list[str] = []
    if base_cfg.get("require_a_share") and not bool(row.get("is_a_share", False)):
        reasons.append("not_a_share")
    if base_cfg.get("require_not_st") and bool(row.get("is_st", False)):
        reasons.append("st")
    if _safe_float(row.get("listed_days")) < float(base_cfg["listed_days_min"]):
        reasons.append("listed_days")
    min_history_years = int(base_cfg.get("main_metric_history_years_min", 0))
    if min_history_years > 0:
        min_history_obs = min_history_years * int(trading_days)
        main_metric_status = _main_metric_status(row, main_metric)
        main_metric_history = _main_metric_history_value(row, main_metric)
        if pd.isna(main_metric_history):
            reasons.append(metric_failure_reason(main_metric, main_metric_status) if main_metric_status != "ok" else "main_metric_history")
        elif float(main_metric_history) < min_history_obs:
            if main_metric_status in {"ttm_non_positive", "equity_non_positive"}:
                reasons.append(metric_failure_reason(main_metric, main_metric_status))
            else:
                reasons.append("main_metric_history")
    if _safe_float(row.get("avg_amount_60d_million")) < float(base_cfg["avg_amount_60d_million_min"]):
        reasons.append("avg_amount_60d_million")
    if _safe_float(row.get("market_cap_billion")) < float(base_cfg["market_cap_billion_min"]):
        reasons.append("market_cap_billion")
    if base_cfg.get("require_industry") and not row.get("industry"):
        reasons.append("industry")
    if _is_v2_rules(universe_rules_cfg):
        required_fields = base_cfg.get("core_required_fields") or ["industry", "market_cap_billion", "avg_amount_60d_million", "pb"]
        for field in required_fields:
            if field == "industry":
                missing = not row.get("industry")
            else:
                missing = pd.isna(row.get(field))
            if missing:
                reasons.append(f"{field}_missing")
    elif not bool(row.get("core_fields_complete", False)):
        reasons.append("core_fields_missing")
    return reasons


def _bucket_filter_reasons(row: pd.Series, bucket: str, universe_rules_cfg: dict, main_metric: str) -> list[str]:
    cfg = universe_rules_cfg["bucket_filters"][bucket]
    reasons: list[str] = []
    if _safe_float(row.get("market_cap_billion")) < float(cfg["market_cap_billion_min"]):
        reasons.append("market_cap_billion")
    if _safe_float(row.get("avg_amount_60d_million")) < float(cfg["avg_amount_60d_million_min"]):
        reasons.append("avg_amount_60d_million")
    if _safe_float(row.get("latest_net_profit")) <= float(cfg["latest_net_profit_min_exclusive"]):
        reasons.append("latest_net_profit")
    roe_status = metric_rule_status(row, "roe_rule_status")
    roe_value = metric_value_for_rules(row, "roe", "roe_rule_value")
    if pd.isna(roe_value) or float(roe_value) < float(cfg["roe_min"]):
        reasons.append(metric_failure_reason("roe", roe_status))
    if _is_v2_rules(universe_rules_cfg):
        industry = str(row.get("industry", ""))
        is_financial = is_financial_industry(industry, universe_rules_cfg.get("_metric_map_cfg", {}))
        if bucket == "defensive_dividend":
            if _safe_float(row.get("dv_ttm")) < float(cfg["dv_ttm_min"]):
                reasons.append("dv_ttm")
            if not is_financial:
                debt_value = row.get("debt_to_assets")
                if not pd.isna(debt_value) and _safe_float(debt_value) > float(cfg["debt_to_assets_max"]):
                    reasons.append("debt_to_assets")
            pe_value = row.get("pe_ttm")
            pe_valid = not pd.isna(pe_value) and _safe_float(pe_value) > 0
            pb_value = row.get("pb")
            pb_valid = not pd.isna(pb_value) and _safe_float(pb_value) > float(cfg["pb_min_exclusive"])
            pb_q = metric_value_for_rules(row, "stock_pb_q_blended", "stock_pb_q_blended_rule_value")
            pb_ok = pb_valid and not pd.isna(pb_q) and float(pb_q) <= float(cfg["pb_q_blended_max_when_primary_metric"])
            if main_metric == "pe_ttm" and not (pe_valid and _safe_float(pe_value) <= float(cfg["pe_ttm_max_when_primary_metric"]) or pb_ok):
                reasons.append("valuation")
            if main_metric == "pb" and not pb_ok:
                reasons.append("pb_q_blended")
        else:
            pb_value = row.get("pb")
            pb_q = metric_value_for_rules(row, "stock_pb_q_blended", "stock_pb_q_blended_rule_value")
            if pd.isna(pb_value) or _safe_float(pb_value) <= float(cfg["pb_min_exclusive"]):
                reasons.append("pb")
            if pd.isna(pb_q) or float(pb_q) > float(cfg["pb_q_blended_max"]):
                reasons.append("pb_q_blended")
            market_cap_rank = _safe_float(row.get("industry_market_cap_rank"), default=10**9)
            market_cap_pct = _safe_float(row.get("industry_market_cap_percentile"), default=1.0)
            if not (
                market_cap_rank <= float(cfg["market_cap_industry_rank_top_n"])
                or market_cap_pct <= float(cfg["market_cap_industry_rank_top_pct"])
            ):
                reasons.append("industry_leader")
            if bool(row.get("cycle_peak_trap", False)):
                reasons.append("cycle_trap")
        return reasons

    if bucket == "defensive_dividend":
        cfo_status = metric_rule_status(row, "cfo_ttm_rule_status")
        cfo_value = metric_value_for_rules(row, "cfo_ttm", "cfo_ttm_rule_value")
        if pd.isna(cfo_value) or float(cfo_value) <= float(cfg["cfo_ttm_min_exclusive"]):
            reasons.append(metric_failure_reason("cfo_ttm", cfo_status))
        if _safe_float(row.get("debt_to_assets"), default=10**9) > float(cfg["debt_to_assets_max"]):
            reasons.append("debt_to_assets")
        if _safe_float(row.get("dv_ttm")) < float(cfg["dv_ttm_min"]):
            reasons.append("dv_ttm")
        if main_metric == "pe_ttm":
            pe_status = metric_rule_status(row, "pe_ttm_rule_status")
            pe_ttm = metric_value_for_rules(row, "pe_ttm", "pe_ttm_rule_value")
            if pd.isna(pe_ttm) or float(pe_ttm) <= 0 or float(pe_ttm) > float(cfg["pe_ttm_max_when_primary_metric"]):
                reasons.append(metric_failure_reason("pe_ttm", pe_status))
        if main_metric == "pb":
            pb_status = metric_rule_status(row, "pb_rule_status")
            pb_value = metric_value_for_rules(row, "pb", "pb_rule_value")
            pb_q_blended = metric_value_for_rules(row, "stock_pb_q_blended", "stock_pb_q_blended_rule_value")
            if (
                pd.isna(pb_value)
                or float(pb_value) <= float(cfg["pb_min_exclusive"])
                or pd.isna(pb_q_blended)
                or float(pb_q_blended) > float(cfg["pb_q_blended_max_when_primary_metric"])
            ):
                reasons.append(metric_failure_reason("pb_q_blended", pb_status))
    else:
        pb_status = metric_rule_status(row, "pb_rule_status")
        pb_value = metric_value_for_rules(row, "pb", "pb_rule_value")
        if pd.isna(pb_value) or float(pb_value) <= float(cfg["pb_min_exclusive"]):
            reasons.append(metric_failure_reason("pb", pb_status))
        market_cap_rank = _safe_float(row.get("industry_market_cap_rank"), default=10**9)
        market_cap_pct = _safe_float(row.get("industry_market_cap_percentile"), default=1.0)
        if not (
            market_cap_rank <= float(cfg["market_cap_industry_rank_top_n"])
            or market_cap_pct <= float(cfg["market_cap_industry_rank_top_pct"])
        ):
            reasons.append("industry_leader")
        if bool(row.get("cycle_peak_trap", False)):
            reasons.append("cycle_trap")
    return reasons


def build_candidate_pool(feature_snapshot: pd.DataFrame, universe_rules_cfg: dict, metric_map_cfg: dict, as_of_date: str) -> pd.DataFrame:
    if feature_snapshot.empty:
        return feature_snapshot.copy()
    snapshot = feature_snapshot.copy()
    rules_for_filters = dict(universe_rules_cfg)
    rules_for_filters["_metric_map_cfg"] = metric_map_cfg
    allowed_industries = set(metric_map_cfg.get("industry_bucket_candidates", {}).keys()) | set(metric_map_cfg.get("industry_bucket_map", {}).keys())
    snapshot = snapshot[snapshot["industry"].isin(allowed_industries)].copy()
    snapshot["as_of_date"] = as_of_date
    snapshot["defensive_final_score"] = pd.NA
    snapshot["cyclical_final_score"] = pd.NA
    snapshot["selected_bucket"] = pd.NA
    snapshot["alternate_bucket"] = pd.NA
    snapshot["selected_bucket_reason"] = pd.NA
    snapshot["base_filter_reasons"] = [[] for _ in range(len(snapshot))]
    snapshot["bucket_filter_reasons"] = [[] for _ in range(len(snapshot))]
    snapshot["candidate_status"] = "filtered_out"
    trading_days = 252
    for idx, row in snapshot.iterrows():
        industry = row.get("industry")
        bucket_scores: dict[str, dict[str, float]] = {}
        eligible_buckets: dict[str, list[str]] = {}
        for bucket in candidate_buckets_for_industry(industry, metric_map_cfg):
            score = _score_row(row, bucket, universe_rules_cfg["scoring"], metric_map_cfg, universe_rules_cfg)
            main_metric = score["main_metric"]
            base_reasons = _base_filter_reasons(row, rules_for_filters, main_metric, trading_days)
            bucket_reasons = _bucket_filter_reasons(row, bucket, rules_for_filters, main_metric)
            bucket_scores[bucket] = score
            eligible_buckets[bucket] = base_reasons + bucket_reasons
            if bucket == "defensive_dividend":
                snapshot.at[idx, "defensive_final_score"] = score["final_score"]
            if bucket == "cyclical_rotation":
                snapshot.at[idx, "cyclical_final_score"] = score["final_score"]
        eligible = {bucket: reasons for bucket, reasons in eligible_buckets.items() if not reasons}
        if not eligible:
            first_bucket = next(iter(bucket_scores)) if bucket_scores else "defensive_dividend"
            snapshot.at[idx, "base_filter_reasons"] = _base_filter_reasons(
                row,
                rules_for_filters,
                bucket_scores.get(first_bucket, {}).get("main_metric", metric_for_industry(industry, metric_map_cfg)),
                trading_days,
            )
            snapshot.at[idx, "bucket_filter_reasons"] = eligible_buckets.get(first_bucket, [])
            continue

        if len(eligible) == 1:
            chosen_bucket = next(iter(eligible))
            snapshot.at[idx, "selected_bucket_reason"] = "single_bucket"
        else:
            defensive_score = bucket_scores["defensive_dividend"]["final_score"]
            cyclical_score = bucket_scores["cyclical_rotation"]["final_score"]
            if defensive_score > cyclical_score:
                chosen_bucket = "defensive_dividend"
                snapshot.at[idx, "alternate_bucket"] = "cyclical_rotation"
            elif cyclical_score > defensive_score:
                chosen_bucket = "cyclical_rotation"
                snapshot.at[idx, "alternate_bucket"] = "defensive_dividend"
            elif _safe_float(row.get("dv_ttm")) >= 0.04 and _safe_float(row.get("roe")) >= 8:
                chosen_bucket = "defensive_dividend"
                snapshot.at[idx, "alternate_bucket"] = "cyclical_rotation"
            else:
                chosen_bucket = "cyclical_rotation"
                snapshot.at[idx, "alternate_bucket"] = "defensive_dividend"
            snapshot.at[idx, "selected_bucket_reason"] = "overlap_bucket_score"
        score = bucket_scores[chosen_bucket]
        for key, value in score.items():
            snapshot.at[idx, key] = value
        snapshot.at[idx, "selected_bucket"] = chosen_bucket
        snapshot.at[idx, "bucket"] = chosen_bucket
        snapshot.at[idx, "main_metric"] = score["main_metric"]
        snapshot.at[idx, "stock_q_5y"] = row.get(f"stock_{score['main_metric']}_q_5y")
        snapshot.at[idx, "stock_q_10y"] = row.get(f"stock_{score['main_metric']}_q_10y")
        snapshot.at[idx, "stock_q_blended"] = row.get(f"stock_{score['main_metric']}_q_blended")
        snapshot.at[idx, "industry_q_5y"] = row.get(f"industry_{score['main_metric']}_q_5y")
        snapshot.at[idx, "industry_q_10y"] = row.get(f"industry_{score['main_metric']}_q_10y")
        snapshot.at[idx, "industry_q_blended"] = row.get(f"industry_{score['main_metric']}_q_blended")
        snapshot.at[idx, "candidate_status"] = "candidate_pool"

    candidates = snapshot[snapshot["candidate_status"] == "candidate_pool"].copy()
    if candidates.empty:
        return candidates
    candidates["industry_rank"] = candidates.groupby("industry")["final_score"].rank(method="first", ascending=False)
    candidates["industry_size_median"] = candidates.groupby("industry")["size_score"].transform("median")
    candidates["industry_liquidity_median"] = candidates.groupby("industry")["liquidity_score"].transform("median")
    return candidates.sort_values(["industry", "industry_rank", "symbol"]).reset_index(drop=True)


def _build_effective_universe_v2(
    candidate_pool: pd.DataFrame,
    previous_universe_cfg: dict,
    current_holdings: pd.DataFrame,
    universe_rules_cfg: dict,
) -> tuple[pd.DataFrame, list[dict]]:
    previous = effective_universe_frame(previous_universe_cfg)
    previous_symbols = set(previous.get("symbol", pd.Series(dtype=str)).astype(str))
    held_symbols = set(current_holdings.get("symbol", pd.Series(dtype=str)).astype(str))
    if candidate_pool.empty:
        return candidate_pool.copy(), []

    rules = universe_rules_cfg
    selected: list[dict] = []
    selected_symbols: set[str] = set()
    industry_counts: Counter = Counter()
    max_per_industry = int(rules.get("max_names_per_industry", rules.get("max_per_industry", 3)))
    target_size = int(rules.get("target_size", rules.get("target_universe_size", 36)))
    floor_size = int(rules.get("floor_size", rules.get("target_universe_floor", 24)))
    ceiling_size = int(rules.get("ceiling_size", rules.get("target_universe_ceiling", 48)))
    bucket_targets = rules.get("bucket_targets", {})

    pool = candidate_pool.sort_values(["final_score", "market_cap_billion", "symbol"], ascending=[False, False, True]).copy()

    def add_row(row: pd.Series, selected_as: str) -> bool:
        symbol = str(row["symbol"])
        industry = str(row.get("industry", ""))
        if symbol in selected_symbols or len(selected) >= ceiling_size:
            return False
        if industry_counts[industry] >= max_per_industry:
            return False
        item = row.to_dict()
        item["selected_as"] = selected_as
        selected.append(item)
        selected_symbols.add(symbol)
        industry_counts[industry] += 1
        return True

    retained = pool[
        pool["symbol"].astype(str).isin(previous_symbols)
        & (pd.to_numeric(pool["final_score"], errors="coerce") >= float(rules.get("retained_min_score", 50)))
        & (
            (pd.to_numeric(pool["industry_rank"], errors="coerce") <= float(rules.get("retained_industry_rank", 6)))
            | (pd.to_numeric(pool["final_score"], errors="coerce") >= float(rules.get("retained_any_rank_score", 60)))
        )
    ].copy()
    for _, row in retained.iterrows():
        add_row(row, "retained")

    new_entries = pool[
        ~pool["symbol"].astype(str).isin(selected_symbols)
        & (pd.to_numeric(pool["final_score"], errors="coerce") >= float(rules.get("new_min_score", 55)))
        & (pd.to_numeric(pool["industry_rank"], errors="coerce") <= float(rules.get("new_industry_rank", 4)))
    ].copy()

    for bucket, target_cfg in bucket_targets.items():
        minimum = int(target_cfg.get("min", 0))
        bucket_rows = new_entries[new_entries["bucket"] == bucket]
        while sum(1 for item in selected if item.get("bucket") == bucket) < minimum:
            added = False
            for _, row in bucket_rows.iterrows():
                if add_row(row, "new_entry"):
                    added = True
                    break
            if not added:
                break

    for _, row in new_entries.iterrows():
        bucket = str(row.get("bucket"))
        maximum = int(bucket_targets.get(bucket, {}).get("max", ceiling_size))
        if sum(1 for item in selected if item.get("bucket") == bucket) >= maximum:
            continue
        add_row(row, "new_entry")
        if len(selected) >= target_size:
            break

    if len(selected) < floor_size:
        supplement = pool[
            ~pool["symbol"].astype(str).isin(selected_symbols)
            & (pd.to_numeric(pool["final_score"], errors="coerce") >= float(rules.get("floor_fill_min_score", 52)))
        ].copy()
        for _, row in supplement.iterrows():
            add_row(row, "floor_fill")
            if len(selected) >= floor_size:
                break

    selected_frame = pd.DataFrame(selected)
    if selected_frame.empty:
        return selected_frame, []
    selected_frame = selected_frame.sort_values(
        ["bucket", "industry", "industry_rank", "final_score", "symbol"],
        ascending=[True, True, True, False, True],
    ).reset_index(drop=True)

    changes: list[dict] = []
    selected_symbols = set(selected_frame["symbol"].astype(str))
    for row in selected_frame.to_dict(orient="records"):
        changes.append(
            {
                "symbol": row["symbol"],
                "name": row.get("name", row["symbol"]),
                "industry": row.get("industry"),
                "change_tag": "retained" if row["symbol"] in previous_symbols else "added",
                "selected_as": row.get("selected_as"),
                "final_score": round(_safe_float(row.get("final_score")), 4),
            }
        )

    previous_frame = previous.copy()
    if not previous_frame.empty:
        for row in previous_frame.to_dict(orient="records"):
            symbol = str(row["symbol"])
            if symbol in selected_symbols:
                continue
            reasons = force_exit_reasons(row, universe_rules_cfg)
            if reasons:
                change_tag = "forced_exit"
            elif symbol in held_symbols and bool(universe_rules_cfg.get("freeze_removed_holdings", True)):
                change_tag = "demoted_to_frozen"
            else:
                change_tag = "removed"
            changes.append(
                {
                    "symbol": symbol,
                    "name": row.get("name", symbol),
                    "industry": row.get("industry_l1", row.get("industry")),
                    "change_tag": change_tag,
                    "selected_as": None,
                    "final_score": round(_safe_float(row.get("final_score")), 4),
                    "force_exit_reasons": reasons,
                }
            )
    return selected_frame, sorted(changes, key=lambda item: (item["change_tag"], item["symbol"]))


def build_effective_universe(
    candidate_pool: pd.DataFrame,
    previous_universe_cfg: dict,
    current_holdings: pd.DataFrame,
    universe_rules_cfg: dict,
) -> tuple[pd.DataFrame, list[dict]]:
    if _is_v2_rules(universe_rules_cfg):
        return _build_effective_universe_v2(candidate_pool, previous_universe_cfg, current_holdings, universe_rules_cfg)
    previous = effective_universe_frame(previous_universe_cfg)
    previous_symbols = set(previous.get("symbol", pd.Series(dtype=str)).astype(str))
    held_symbols = set(current_holdings.get("symbol", pd.Series(dtype=str)).astype(str))
    if candidate_pool.empty:
        return candidate_pool.copy(), []

    rules = universe_rules_cfg
    selected_rows: list[pd.Series] = []
    for industry, group in candidate_pool.groupby("industry", sort=True):
        group = group.sort_values(["industry_rank", "final_score", "symbol"], ascending=[True, False, True]).copy()
        incumbents = group[
            group["symbol"].isin(previous_symbols) & (group["industry_rank"] <= int(rules["incumbent_keep_rank"]))
        ].copy()
        incumbents["selected_as"] = "retained"

        rank1 = group[group["industry_rank"] == 1].copy()
        if not rank1.empty and _safe_float(rank1.iloc[0]["final_score"]) >= float(rules["min_final_score"]):
            if rank1.iloc[0]["symbol"] not in set(incumbents["symbol"]):
                rank1["selected_as"] = "new_entry"
                incumbents = pd.concat([incumbents, rank1], ignore_index=True)

        rank2 = group[group["industry_rank"] == 2].copy()
        if not rank2.empty:
            first_score = _safe_float(group.iloc[0]["final_score"])
            second = rank2.iloc[0]
            second_allowed = bool(
                _safe_float(second["final_score"]) >= float(rules["min_second_name_score"])
                and abs(first_score - _safe_float(second["final_score"])) <= float(rules["max_rank_gap_for_second_name"])
                and _safe_float(second["size_score"]) >= _safe_float(second["industry_size_median"])
                and _safe_float(second["liquidity_score"]) >= _safe_float(second["industry_liquidity_median"])
            )
            if second_allowed and second["symbol"] not in set(incumbents["symbol"]):
                rank2["selected_as"] = "new_entry"
                incumbents = pd.concat([incumbents, rank2], ignore_index=True)

        incumbents = incumbents.sort_values(["selected_as", "industry_rank", "final_score", "symbol"], ascending=[True, True, False, True])
        selected_rows.extend(incumbents.head(int(rules["max_per_industry"])).to_dict(orient="records"))

    selected = pd.DataFrame(selected_rows).drop_duplicates(subset=["symbol"], keep="first")
    if selected.empty:
        return selected, []

    ceiling = int(rules["target_universe_ceiling"])
    if len(selected) > ceiling:
        selected = selected.sort_values(
            ["selected_as", "industry_rank", "final_score", "symbol"],
            ascending=[True, True, False, True],
        ).head(ceiling)
    selected = selected.sort_values(["industry", "industry_rank", "final_score", "symbol"], ascending=[True, True, False, True]).reset_index(drop=True)

    changes: list[dict] = []
    selected_symbols = set(selected["symbol"].astype(str))
    for row in selected.to_dict(orient="records"):
        changes.append(
            {
                "symbol": row["symbol"],
                "name": row.get("name", row["symbol"]),
                "industry": row.get("industry"),
                "change_tag": "retained" if row["symbol"] in previous_symbols else "added",
                "selected_as": row.get("selected_as"),
                "final_score": round(_safe_float(row.get("final_score")), 4),
            }
        )

    previous_frame = previous.copy()
    if not previous_frame.empty:
        for row in previous_frame.to_dict(orient="records"):
            symbol = str(row["symbol"])
            if symbol in selected_symbols:
                continue
            reasons = force_exit_reasons(row, universe_rules_cfg)
            if reasons:
                change_tag = "forced_exit"
            elif symbol in held_symbols and bool(universe_rules_cfg.get("freeze_removed_holdings", True)):
                change_tag = "demoted_to_frozen"
            else:
                change_tag = "removed"
            changes.append(
                {
                    "symbol": symbol,
                    "name": row.get("name", symbol),
                    "industry": row.get("industry_l1", row.get("industry")),
                    "change_tag": change_tag,
                    "selected_as": None,
                    "final_score": round(_safe_float(row.get("final_score")), 4),
                    "force_exit_reasons": reasons,
                }
            )
    return selected, sorted(changes, key=lambda item: (item["change_tag"], item["symbol"]))


def serialize_universe_payload(
    selected: pd.DataFrame,
    changes: list[dict],
    as_of_date: str,
    effective_from: str,
    effective_to: str,
    frequency: str,
    methodology_version: str,
    rebalance_day: bool,
) -> dict:
    stocks = []
    for row in selected.to_dict(orient="records"):
        item = {
            "symbol": row["symbol"],
            "name": row.get("name", row["symbol"]),
            "bucket": row.get("bucket"),
            "industry_l1": row.get("industry"),
            "main_metric": row.get("main_metric"),
            "final_score": round(_safe_float(row.get("final_score")), 4),
            "stock_q_blended": round(_safe_float(row.get("stock_q_blended")), 4),
            "industry_q_blended": round(_safe_float(row.get("industry_q_blended")), 4),
            "roe": round(_safe_float(row.get("roe")), 4),
            "dv_ttm": round(_safe_float(row.get("dv_ttm")), 4),
            "market_cap_billion": round(_safe_float(row.get("market_cap_billion")), 4),
            "avg_amount_60d_million": round(_safe_float(row.get("avg_amount_60d_million")), 4),
            "industry_rank": int(_safe_float(row.get("industry_rank"), default=0)),
            "selected_as": row.get("selected_as", "new_entry"),
            "cycle_trap": bool(row.get("cycle_peak_trap", False)),
            "force_exit_reasons": force_exit_reasons(row, {"force_exit_rules": [], "prolonged_data_failure_days": 10, "long_suspension_days": 20}),
        }
        if str(methodology_version).startswith("combined_v2"):
            item.update(
                {
                    "alternate_bucket": row.get("alternate_bucket"),
                    "valuation_score": round(_safe_float(row.get("valuation_score")), 4),
                    "quality_score": round(_safe_float(row.get("quality_score")), 4),
                    "leader_score": round(_safe_float(row.get("leader_score")), 4),
                    "dividend_score": round(_safe_float(row.get("dividend_score")), 4),
                    "cycle_safety_score": round(_safe_float(row.get("cycle_safety_score")), 4),
                }
            )
        stocks.append(item)
    return {
        "generated_at": os.environ.get("QUANTILE_FIXED_GENERATED_AT", pd.Timestamp.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")),
        "as_of_date": as_of_date,
        "effective_from": effective_from,
        "effective_to": effective_to,
        "methodology_version": methodology_version,
        "rebalance_frequency": frequency,
        "rebalance_day": rebalance_day,
        "stocks": stocks,
        "changes": changes,
    }


def universe_report_payload(candidate_pool: pd.DataFrame, selected: pd.DataFrame, changes: list[dict], payload: dict) -> dict:
    change_counts = Counter(change["change_tag"] for change in changes)
    return {
        "as_of_date": payload["as_of_date"],
        "rebalance_day": payload["rebalance_day"],
        "effective_from": payload["effective_from"],
        "effective_to": payload["effective_to"],
        "methodology_version": payload["methodology_version"],
        "candidate_pool_size": int(len(candidate_pool)),
        "effective_universe_size": int(len(selected)),
        "change_counts": dict(change_counts),
        "changes": changes,
        "stocks": payload["stocks"],
    }


def write_universe_outputs(payload: dict, report_payload: dict) -> dict[str, Path]:
    universe_path = resolve_path("config/universe.yml")
    latest_md = resolve_path("reports/universe/latest.md")
    latest_json = resolve_path("reports/universe/latest.json")
    history_json = resolve_path(f"data/curated/universe_history/{payload['effective_from']}.json")
    for path in (universe_path, latest_md, latest_json, history_json):
        path.parent.mkdir(parents=True, exist_ok=True)

    import json
    import yaml

    universe_path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
    latest_json.write_text(json.dumps(report_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    history_json.write_text(json.dumps(report_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        f"# Effective Universe ({payload['as_of_date']})",
        "",
        f"- Rebalance day: {'yes' if payload['rebalance_day'] else 'no'}",
        f"- Effective from: {payload['effective_from']}",
        f"- Effective to: {payload['effective_to']}",
        f"- Candidate pool: {report_payload['candidate_pool_size']}",
        f"- Effective universe: {report_payload['effective_universe_size']}",
        "",
        "## Universe",
        "",
    ]
    if payload["stocks"]:
        for item in payload["stocks"]:
            lines.append(
                f"- {item['symbol']} {item['name']} | {item['bucket']} | {item['industry_l1']} | score={item['final_score']:.2f} | rank={item['industry_rank']} | {item['selected_as']}"
            )
    else:
        lines.append("- 无有效成分")
    if report_payload["changes"]:
        lines.extend(["", "## Diff", ""])
        for change in report_payload["changes"]:
            lines.append(f"- {change['change_tag']}: {change['symbol']} {change.get('name', '')}".rstrip())
    latest_md.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return {
        "universe_yml": universe_path,
        "latest_md": latest_md,
        "latest_json": latest_json,
        "history_json": history_json,
    }
