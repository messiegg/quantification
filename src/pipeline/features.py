from __future__ import annotations

import math

import numpy as np
import pandas as pd

from src.strategy.metric_map import bucket_for_industry_optional, metric_for_industry_optional
from src.strategy.quality import evaluate_quality, is_cycle_peak_trap, percentile_rank
from src.strategy.valuation import add_quantile_columns, latest_quantiles, trailing_quantile

RULE_UNCOMPUTABLE_SENTINEL = -999999999.0


def _calendar_dates(
    trade_calendar: pd.DataFrame | None,
    benchmark_daily: pd.DataFrame | None,
) -> pd.Index:
    source = trade_calendar if trade_calendar is not None and not trade_calendar.empty else benchmark_daily
    if source is None or source.empty or "date" not in source.columns:
        return pd.Index([])
    dates = pd.to_datetime(source["date"], errors="coerce").dropna().drop_duplicates().sort_values()
    if dates.empty:
        return pd.Index([])
    return pd.Index(dates[dates.dt.weekday < 5])


def _compute_listed_days_from_calendar(
    ordered: pd.DataFrame,
    stock_list: pd.DataFrame | None,
    trade_calendar: pd.DataFrame | None,
    benchmark_daily: pd.DataFrame | None,
) -> tuple[pd.Series, pd.Series]:
    trade_dates = _calendar_dates(trade_calendar, benchmark_daily)
    if trade_dates.empty:
        empty = pd.Series(pd.NA, index=ordered.index, dtype="Float64")
        return empty, pd.Series(pd.NA, index=ordered.index, dtype="string")
    earliest_price = ordered.groupby("code", as_index=False)["date"].min().rename(columns={"date": "first_price_date"})
    earliest_price["code"] = earliest_price["code"].astype(str)
    merged = ordered[["code", "date"]].merge(earliest_price, how="left", on="code")
    merged["first_price_date"] = pd.to_datetime(merged["first_price_date"], errors="coerce")
    merged["listed_date"] = pd.NaT
    if stock_list is not None and not stock_list.empty and "listed_date" in stock_list.columns:
        listed_dates = stock_list[["code", "listed_date"]].drop_duplicates(subset=["code"]).copy()
        listed_dates["code"] = listed_dates["code"].astype(str)
        listed_dates["listed_date"] = pd.to_datetime(listed_dates["listed_date"], errors="coerce")
        merged = merged.merge(listed_dates, how="left", on="code", suffixes=("", "_stock"))
        if "listed_date_stock" in merged.columns:
            merged["listed_date"] = merged["listed_date_stock"]
            merged = merged.drop(columns=["listed_date_stock"])
    merged["calendar_start_date"] = merged["listed_date"].fillna(merged["first_price_date"])
    current_positions = trade_dates.searchsorted(pd.to_datetime(merged["date"], errors="coerce"), side="right")
    listed_positions = trade_dates.searchsorted(merged["calendar_start_date"].fillna(trade_dates[0]), side="left")
    values = current_positions - listed_positions
    values = np.where(merged["calendar_start_date"].isna(), np.nan, np.maximum(values, 0))
    source = np.where(
        merged["listed_date"].notna(),
        "listed_date_trade_calendar",
        np.where(merged["first_price_date"].notna(), "first_price_trade_calendar", pd.NA),
    )
    return pd.Series(values, index=ordered.index, dtype="Float64"), pd.Series(source, index=ordered.index, dtype="string")


def compute_price_features(
    price_frame: pd.DataFrame,
    stock_list: pd.DataFrame | None = None,
    trade_calendar: pd.DataFrame | None = None,
    benchmark_daily: pd.DataFrame | None = None,
) -> pd.DataFrame:
    ordered = price_frame.sort_values(["code", "date"]).copy()
    grouped = ordered.groupby("code", group_keys=False)
    for window in (20, 60, 120, 200, 250):
        ordered[f"ma{window}"] = grouped["close"].transform(lambda series, window=window: series.rolling(window, min_periods=1).mean())
    ordered["prev_close"] = grouped["close"].shift(1)
    ordered["tr"] = (
        pd.concat(
            [
                ordered["high"] - ordered["low"],
                (ordered["high"] - ordered["prev_close"]).abs(),
                (ordered["low"] - ordered["prev_close"]).abs(),
            ],
            axis=1,
        )
        .max(axis=1)
    )
    ordered["atr20"] = grouped["tr"].transform(lambda series: series.rolling(20, min_periods=1).mean())
    ordered["avg_amount_60d_million"] = grouped["amount"].transform(lambda series: series.rolling(60, min_periods=1).mean()) / 1e6
    listed_days_from_calendar, listed_days_source = _compute_listed_days_from_calendar(
        ordered,
        stock_list=stock_list,
        trade_calendar=trade_calendar,
        benchmark_daily=benchmark_daily,
    )
    ordered["listed_days"] = listed_days_from_calendar.fillna(grouped.cumcount() + 1)
    ordered["listed_days_source"] = listed_days_source.fillna("price_row_count_fallback")
    ordered["ma20_slope_10d"] = grouped["ma20"].transform(lambda series: series.pct_change(10))
    ordered["ma60_slope_20d"] = grouped["ma60"].transform(lambda series: series.pct_change(20))
    ordered["ma120_slope_20d"] = grouped["ma120"].transform(lambda series: series.pct_change(20))
    return ordered.drop(columns=["prev_close", "tr"])


def _quantile_windows(strategy_cfg: dict) -> dict[str, int]:
    return {
        "q_5y": int(strategy_cfg["valuation"]["windows_years"]["q_5y"] * strategy_cfg["valuation"]["trading_days_per_year"]),
        "q_10y": int(strategy_cfg["valuation"]["windows_years"]["q_10y"] * strategy_cfg["valuation"]["trading_days_per_year"]),
    }


def _compute_metric_quantile_panel(
    frame: pd.DataFrame,
    entity_col: str,
    metric_col: str,
    value_col: str,
    date_col: str,
    strategy_cfg: dict,
    prefix: str,
) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    selected = frame[[entity_col, metric_col, date_col, value_col]].copy()
    selected[metric_col] = selected[metric_col].astype(str)
    selected["entity_metric_id"] = selected[entity_col].astype(str) + "|" + selected[metric_col]
    selected[value_col] = pd.to_numeric(selected[value_col], errors="coerce")
    selected = selected.dropna(subset=[value_col, date_col])
    weighted = add_quantile_columns(
        selected,
        entity_col="entity_metric_id",
        value_col=value_col,
        date_col=date_col,
        windows=_quantile_windows(strategy_cfg),
        blended_weights=strategy_cfg["valuation"]["blended_weights"],
    )
    weighted["history_observations"] = weighted.groupby("entity_metric_id").cumcount() + 1
    pivot = weighted.pivot_table(
        index=[entity_col, date_col],
        columns=metric_col,
        values=[value_col, "q_5y", "q_10y", "q_blended", "history_observations"],
        aggfunc="last",
    )
    pivot.columns = [
        f"{prefix}_{metric}" if value_name == value_col else f"{prefix}_{metric}_{value_name}"
        for value_name, metric in pivot.columns
    ]
    return pivot.reset_index()


def _compute_latest_metric_quantiles(
    frame: pd.DataFrame,
    entity_col: str,
    metric_col: str,
    value_col: str,
    date_col: str,
    strategy_cfg: dict,
    prefix: str,
) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    selected = frame[[entity_col, metric_col, date_col, value_col]].copy()
    selected[metric_col] = selected[metric_col].astype(str)
    selected[date_col] = pd.to_datetime(selected[date_col], errors="coerce").dt.strftime("%Y-%m-%d")
    selected[value_col] = pd.to_numeric(selected[value_col], errors="coerce")
    selected = selected.dropna(subset=[entity_col, metric_col, date_col, value_col])
    if selected.empty:
        return pd.DataFrame(columns=[entity_col, date_col])

    windows = _quantile_windows(strategy_cfg)
    blended_weights = strategy_cfg["valuation"]["blended_weights"]
    rows: list[dict[str, object]] = []
    grouped = selected.sort_values([entity_col, metric_col, date_col]).groupby([entity_col, metric_col], sort=False)
    for (entity, metric), group in grouped:
        values = pd.to_numeric(group[value_col], errors="coerce").dropna()
        if values.empty:
            continue
        q_values = {
            label: trailing_quantile(values.tail(window))
            for label, window in windows.items()
        }
        q_blended = sum(float(q_values[label]) * float(weight) for label, weight in blended_weights.items())
        rows.append(
            {
                entity_col: entity,
                metric_col: metric,
                date_col: str(group.iloc[-1][date_col]),
                value_col: float(values.iloc[-1]),
                "q_5y": q_values["q_5y"],
                "q_10y": q_values["q_10y"],
                "q_blended": q_blended,
                "history_observations": int(len(values)),
            }
        )
    if not rows:
        return pd.DataFrame(columns=[entity_col, date_col])

    latest = pd.DataFrame(rows)
    pivot = latest.pivot_table(
        index=[entity_col, date_col],
        columns=metric_col,
        values=[value_col, "q_5y", "q_10y", "q_blended", "history_observations"],
        aggfunc="last",
    )
    pivot.columns = [
        f"{prefix}_{metric}" if value_name == value_col else f"{prefix}_{metric}_{value_name}"
        for value_name, metric in pivot.columns
    ]
    return pivot.reset_index()


def compute_stock_quantiles(valuation_frame: pd.DataFrame, strategy_cfg: dict) -> pd.DataFrame:
    if valuation_frame.empty:
        return valuation_frame.copy()
    selected = valuation_frame.copy()
    if "metric" not in selected.columns:
        metric_columns = [column for column in ("pb", "pe_ttm") if column in selected.columns]
        stacked_frames: list[pd.DataFrame] = []
        entity_col = "code" if "code" in selected.columns else "symbol"
        for metric in metric_columns:
            frame = selected[[entity_col, "date", metric]].rename(columns={entity_col: "code", metric: "metric_value"}).copy()
            frame["metric"] = metric
            stacked_frames.append(frame)
        if not stacked_frames:
            return pd.DataFrame(columns=["code", "date"])
        selected = pd.concat(stacked_frames, ignore_index=True)
    else:
        selected = selected.rename(columns={"value": "metric_value"})
    return _compute_latest_metric_quantiles(
        selected,
        entity_col="code",
        metric_col="metric",
        value_col="metric_value",
        date_col="date",
        strategy_cfg=strategy_cfg,
        prefix="stock",
    )


def compute_stock_quantile_panel(valuation_frame: pd.DataFrame, strategy_cfg: dict) -> pd.DataFrame:
    if valuation_frame.empty:
        return valuation_frame.copy()
    selected = valuation_frame.copy()
    if "metric" not in selected.columns:
        metric_columns = [column for column in ("pb", "pe_ttm") if column in selected.columns]
        stacked_frames: list[pd.DataFrame] = []
        entity_col = "code" if "code" in selected.columns else "symbol"
        for metric in metric_columns:
            frame = selected[[entity_col, "date", metric]].rename(columns={entity_col: "code", metric: "metric_value"}).copy()
            frame["metric"] = metric
            stacked_frames.append(frame)
        if not stacked_frames:
            return pd.DataFrame(columns=["code", "date"])
        selected = pd.concat(stacked_frames, ignore_index=True)
    else:
        selected = selected.rename(columns={"value": "metric_value"})
    panel = _compute_metric_quantile_panel(
        selected,
        entity_col="code",
        metric_col="metric",
        value_col="metric_value",
        date_col="date",
        strategy_cfg=strategy_cfg,
        prefix="stock",
    )
    return panel


def compute_industry_quantiles(industry_frame: pd.DataFrame, strategy_cfg: dict, metric: str) -> pd.DataFrame:
    if industry_frame.empty:
        return industry_frame.copy()
    selected = industry_frame.copy()
    selected["industry_code"] = selected["industry_code"].astype(str).str.replace(".SI", "", regex=False)
    if "metric" not in selected.columns:
        metric_columns = [column for column in ("pb", "pe_ttm") if column in selected.columns]
        stacked_frames: list[pd.DataFrame] = []
        for metric_name in metric_columns:
            frame = selected[["industry_code", "date", metric_name]].rename(columns={metric_name: "metric_value"}).copy()
            frame["metric"] = metric_name
            stacked_frames.append(frame)
        if not stacked_frames:
            return pd.DataFrame(columns=["industry_code", "date"])
        selected = pd.concat(stacked_frames, ignore_index=True)
    else:
        selected = selected.rename(columns={"value": "metric_value"})
    panel = _compute_latest_metric_quantiles(
        selected,
        entity_col="industry_code",
        metric_col="metric",
        value_col="metric_value",
        date_col="date",
        strategy_cfg=strategy_cfg,
        prefix="industry",
    )
    industry_names = industry_frame[["industry_code", "industry_name"]].drop_duplicates()
    industry_names["industry_code"] = industry_names["industry_code"].astype(str).str.replace(".SI", "", regex=False)
    return panel.merge(industry_names, how="left", on="industry_code")


def compute_industry_quantile_panel(industry_frame: pd.DataFrame, strategy_cfg: dict, metric_map_cfg: dict) -> pd.DataFrame:
    if industry_frame.empty:
        return industry_frame.copy()
    selected = industry_frame.copy()
    selected["industry_code"] = selected["industry_code"].astype(str).str.replace(".SI", "", regex=False)
    if "metric" not in selected.columns:
        metric_columns = [column for column in ("pb", "pe_ttm") if column in selected.columns]
        stacked_frames: list[pd.DataFrame] = []
        for metric in metric_columns:
            frame = selected[["industry_code", "industry_name", "date", metric]].rename(columns={metric: "metric_value"}).copy()
            frame["metric"] = metric
            stacked_frames.append(frame)
        if not stacked_frames:
            return pd.DataFrame(columns=["industry_code", "date"])
        selected = pd.concat(stacked_frames, ignore_index=True)
    else:
        selected = selected.rename(columns={"value": "metric_value"})
    panel = _compute_metric_quantile_panel(
        selected,
        entity_col="industry_code",
        metric_col="metric",
        value_col="metric_value",
        date_col="date",
        strategy_cfg=strategy_cfg,
        prefix="industry",
    )
    industry_names = industry_frame[["industry_code", "industry_name"]].drop_duplicates()
    return panel.merge(industry_names, how="left", on="industry_code")


def _annual_profit_positive_years(group: pd.DataFrame) -> pd.Series:
    annual = group[group["report_month_day"] == "12-31"][["report_date", "latest_net_profit"]].copy()
    if annual.empty:
        return pd.Series(0, index=group.index, dtype=float)
    counts: list[float] = []
    annual = annual.sort_values("report_date")
    for report_date in pd.to_datetime(group["report_date"]):
        subset = annual[pd.to_datetime(annual["report_date"]) <= report_date].tail(3)
        counts.append(float((pd.to_numeric(subset["latest_net_profit"], errors="coerce") > 0).sum()))
    return pd.Series(counts, index=group.index, dtype=float)


def _quarter_index(report_date: pd.Series) -> pd.Series:
    months = pd.to_datetime(report_date, errors="coerce").dt.month
    return months.map({3: 1, 6: 2, 9: 3, 12: 4})


def _single_quarter_series(group: pd.DataFrame, value_column: str) -> pd.Series:
    numeric = pd.to_numeric(group[value_column], errors="coerce")
    quarter_index = _quarter_index(group["report_date"])
    years = pd.to_datetime(group["report_date"], errors="coerce").dt.year
    result = pd.Series(pd.NA, index=group.index, dtype="Float64")
    for year in sorted(years.dropna().unique()):
        mask = years == year
        year_idx = group.index[mask]
        if year_idx.empty:
            continue
        year_values = numeric.loc[year_idx]
        year_quarters = quarter_index.loc[year_idx]
        previous_cumulative = None
        previous_quarter = None
        for idx, quarter, value in zip(year_idx, year_quarters, year_values, strict=False):
            if pd.isna(value):
                result.loc[idx] = pd.NA
                continue
            if quarter == 1 or previous_cumulative is None or previous_quarter is None or quarter <= previous_quarter:
                single_value = float(value)
            else:
                single_value = float(value) - float(previous_cumulative)
            result.loc[idx] = single_value
            previous_cumulative = float(value)
            previous_quarter = int(quarter) if pd.notna(quarter) else previous_quarter
    return result


def _aligned_group_series(frame: pd.DataFrame, group_col: str, builder) -> pd.Series:
    grouped = frame.groupby(group_col, group_keys=False).apply(builder)
    if isinstance(grouped, pd.DataFrame):
        grouped = grouped.stack(future_stack=True)
    return grouped.reset_index(level=0, drop=True).reindex(frame.index)


def prepare_financial_effective_frame(financials: pd.DataFrame, strategy_cfg: dict) -> pd.DataFrame:
    if financials.empty:
        return financials.copy()
    fallback_days = int(strategy_cfg["financial_effective_date"]["fallback_days"])
    ordered = financials.sort_values(["code", "report_date", "announcement_date"]).copy()
    ordered["report_date"] = pd.to_datetime(ordered["report_date"])
    ordered["announcement_date"] = pd.to_datetime(ordered["announcement_date"], errors="coerce")
    ordered["effective_date"] = ordered["announcement_date"].fillna(ordered["report_date"] + pd.Timedelta(days=fallback_days))
    ordered["date"] = ordered["effective_date"].dt.strftime("%Y-%m-%d")
    ordered["latest_net_profit"] = pd.to_numeric(ordered["net_profit"], errors="coerce")
    ordered["equity_effective"] = pd.to_numeric(ordered.get("equity"), errors="coerce")
    ordered["net_profit_quarter"] = _aligned_group_series(ordered, "code", lambda frame: _single_quarter_series(frame, "net_profit"))
    ordered["cfo_quarter"] = _aligned_group_series(ordered, "code", lambda frame: _single_quarter_series(frame, "cfo"))
    ordered["net_profit_ttm_effective"] = ordered.groupby("code")["net_profit_quarter"].transform(
        lambda series: pd.to_numeric(series, errors="coerce").rolling(4, min_periods=4).sum()
    )
    ordered["cfo_ttm"] = ordered.groupby("code")["cfo_quarter"].transform(
        lambda series: pd.to_numeric(series, errors="coerce").rolling(4, min_periods=4).sum()
    )
    ordered["reported_quarters_4q_count"] = ordered.groupby("code")["report_date"].transform(
        lambda series: pd.to_datetime(series, errors="coerce").rolling(4, min_periods=1).count()
    )
    ordered["net_profit_quarter_non_null_4q_count"] = ordered.groupby("code")["net_profit_quarter"].transform(
        lambda series: pd.to_numeric(series, errors="coerce").rolling(4, min_periods=1).count()
    )
    ordered["cfo_quarter_non_null_4q_count"] = ordered.groupby("code")["cfo_quarter"].transform(
        lambda series: pd.to_numeric(series, errors="coerce").rolling(4, min_periods=1).count()
    )
    ordered["net_profit_ttm_rule_status"] = "ok"
    ordered.loc[
        ordered["net_profit_ttm_effective"].isna() & ordered["reported_quarters_4q_count"].lt(4),
        "net_profit_ttm_rule_status",
    ] = "insufficient_history"
    ordered.loc[
        ordered["net_profit_ttm_effective"].isna() & ordered["reported_quarters_4q_count"].ge(4),
        "net_profit_ttm_rule_status",
    ] = "source_missing"
    ordered["cfo_ttm_rule_status"] = "ok"
    ordered.loc[
        ordered["cfo_ttm"].isna() & ordered["reported_quarters_4q_count"].lt(4),
        "cfo_ttm_rule_status",
    ] = "insufficient_history"
    ordered.loc[
        ordered["cfo_ttm"].isna() & ordered["reported_quarters_4q_count"].ge(4),
        "cfo_ttm_rule_status",
    ] = "source_missing"
    ordered["roe"] = pd.to_numeric(ordered["roe"], errors="coerce")
    roe_fillable = ordered["roe"].isna() & ordered["equity_effective"].gt(0) & ordered["latest_net_profit"].notna()
    ordered.loc[roe_fillable, "roe"] = (
        pd.to_numeric(ordered.loc[roe_fillable, "latest_net_profit"], errors="coerce")
        / pd.to_numeric(ordered.loc[roe_fillable, "equity_effective"], errors="coerce")
        * 100.0
    )
    ordered["roe_rule_status"] = "ok"
    ordered.loc[
        ordered["roe"].isna() & ordered["equity_effective"].notna() & ordered["latest_net_profit"].notna() & ordered["equity_effective"].le(0),
        "roe_rule_status",
    ] = "equity_non_positive"
    ordered.loc[
        ordered["roe"].isna() & ordered["roe_rule_status"].eq("ok"),
        "roe_rule_status",
    ] = "source_missing"
    ordered["debt_to_assets"] = pd.to_numeric(ordered["debt_to_assets"], errors="coerce")
    ordered["dv_ttm"] = pd.to_numeric(ordered.get("dv_ttm"), errors="coerce")
    ordered["report_month_day"] = ordered["report_date"].dt.strftime("%m-%d")
    profit_positive = ordered.groupby("code").apply(_annual_profit_positive_years)
    if isinstance(profit_positive, pd.DataFrame):
        profit_positive = profit_positive.stack()
    ordered["profit_positive_years_3y"] = profit_positive.reset_index(level=0, drop=True).reindex(ordered.index).astype(float)
    ordered["profit_positive_stability_score"] = ordered["profit_positive_years_3y"] / 3.0 * 100.0
    ordered["roe_pct_in_last_12_quarters"] = ordered.groupby("code")["roe"].transform(
        lambda series: series.rolling(12, min_periods=1).apply(
            lambda values: percentile_rank(pd.Series(values), current=float(values.iloc[-1])),
            raw=False,
        )
    )
    return ordered


def _merge_asof_by_key(left: pd.DataFrame, right: pd.DataFrame, by: str) -> pd.DataFrame:
    if right.empty:
        return left.copy()
    left_ordered = left.copy()
    right_ordered = right.copy()
    left_ordered["date"] = pd.to_datetime(left_ordered["date"]).dt.floor("D").astype("datetime64[ns]")
    right_ordered["date"] = pd.to_datetime(right_ordered["date"]).dt.floor("D").astype("datetime64[ns]")
    left_ordered = left_ordered.sort_values(["date", by]).copy()
    right_ordered = right_ordered.sort_values(["date", by]).copy()
    merged = pd.merge_asof(left_ordered, right_ordered, on="date", by=by, direction="backward")
    merged["date"] = merged["date"].dt.strftime("%Y-%m-%d")
    return merged


def _cross_sectional_percentiles(frame: pd.DataFrame, column: str, higher_is_better: bool = True) -> pd.Series:
    numeric = pd.to_numeric(frame[column], errors="coerce")
    pct = numeric.rank(method="average", pct=True)
    values = pct * 100.0
    return values if higher_is_better else 100.0 - values


def _cross_sectional_percentiles_by_date(frame: pd.DataFrame, column: str, higher_is_better: bool = True) -> pd.Series:
    numeric = pd.to_numeric(frame[column], errors="coerce")
    pct = numeric.groupby(frame["date"]).rank(method="average", pct=True)
    values = pct * 100.0
    return values if higher_is_better else 100.0 - values


def _financial_fresh_until_date(value: object) -> pd.Timestamp:
    report_date = pd.to_datetime(value, errors="coerce")
    if pd.isna(report_date):
        return pd.NaT
    quarter = int(((int(report_date.month) - 1) // 3) + 1)
    year = int(report_date.year)
    if quarter == 1:
        return pd.Timestamp(year=year, month=8, day=31)
    if quarter == 2:
        return pd.Timestamp(year=year, month=10, day=31)
    if quarter in {3, 4}:
        return pd.Timestamp(year=year + 1, month=4, day=30)
    return report_date


def _compute_core_data_stale_days(date_series: pd.Series, report_date_series: pd.Series, effective_date_series: pd.Series) -> pd.Series:
    as_of_dates = pd.to_datetime(date_series, errors="coerce")
    report_dates = pd.to_datetime(report_date_series, errors="coerce")
    effective_dates = pd.to_datetime(effective_date_series, errors="coerce")
    fresh_until = report_dates.map(_financial_fresh_until_date)
    anchor = fresh_until.where(fresh_until.notna(), effective_dates)
    stale_days = (as_of_dates - anchor).dt.days
    stale_days = stale_days.where(anchor.notna(), pd.NA)
    return stale_days.clip(lower=0)


def _coalesce_metric_quantiles(frame: pd.DataFrame, metric: str) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
    return (
        pd.to_numeric(frame.get(f"stock_{metric}_q_5y"), errors="coerce"),
        pd.to_numeric(frame.get(f"stock_{metric}_q_10y"), errors="coerce"),
        pd.to_numeric(frame.get(f"stock_{metric}_q_blended"), errors="coerce"),
        pd.to_numeric(frame.get(f"stock_{metric}_history_observations"), errors="coerce"),
    )


def _select_main_metric_series(
    main_metric: pd.Series,
    pb_values: pd.Series | None,
    pe_values: pd.Series | None,
) -> pd.Series:
    result = pd.Series(np.nan, index=main_metric.index, dtype=float)
    if pb_values is not None:
        pb_numeric = pd.to_numeric(pb_values, errors="coerce")
        result.loc[main_metric.eq("pb")] = pb_numeric.loc[main_metric.eq("pb")]
    if pe_values is not None:
        pe_numeric = pd.to_numeric(pe_values, errors="coerce")
        result.loc[main_metric.eq("pe_ttm")] = pe_numeric.loc[main_metric.eq("pe_ttm")]
    return result


def _apply_rule_value_with_status(
    panel: pd.DataFrame,
    raw_column: str,
    rule_column: str,
    status_column: str,
    uncomputable_statuses: set[str],
) -> pd.DataFrame:
    panel[rule_column] = pd.to_numeric(panel.get(raw_column), errors="coerce")
    if status_column not in panel.columns:
        panel[status_column] = "ok"
    panel.loc[
        panel[rule_column].isna() & panel[status_column].astype(str).isin(uncomputable_statuses),
        rule_column,
    ] = RULE_UNCOMPUTABLE_SENTINEL
    return panel


def _apply_metric_rule_values(panel: pd.DataFrame) -> pd.DataFrame:
    ttm_profit = pd.to_numeric(panel.get("net_profit_ttm_effective"), errors="coerce")
    net_profit_ttm_status = panel.get("net_profit_ttm_rule_status", pd.Series("ok", index=panel.index, dtype="object")).astype(str)
    ttm_positive = ttm_profit > 0
    panel["ttm_profit_positive"] = ttm_positive.fillna(False)
    panel["pe_ttm_rule_status"] = "ok"
    panel.loc[panel["pe_ttm"].isna(), "pe_ttm_rule_status"] = "source_missing"
    panel.loc[panel["pe_ttm"].isna() & net_profit_ttm_status.eq("insufficient_history"), "pe_ttm_rule_status"] = "insufficient_history"
    panel.loc[panel["pe_ttm"].isna() & ttm_profit.notna() & ttm_profit.le(0), "pe_ttm_rule_status"] = "ttm_non_positive"
    panel = _apply_rule_value_with_status(panel, "pe_ttm", "pe_ttm_rule_value", "pe_ttm_rule_status", {"ttm_non_positive", "insufficient_history"})

    panel["pb_rule_status"] = "ok"
    equity = pd.to_numeric(panel.get("equity_effective"), errors="coerce")
    panel.loc[pd.to_numeric(panel.get("pb"), errors="coerce").isna(), "pb_rule_status"] = "source_missing"
    panel.loc[pd.to_numeric(panel.get("pb"), errors="coerce").isna() & equity.notna() & equity.le(0), "pb_rule_status"] = "equity_non_positive"
    panel = _apply_rule_value_with_status(panel, "pb", "pb_rule_value", "pb_rule_status", {"equity_non_positive"})

    if "roe_rule_status" not in panel.columns:
        panel["roe_rule_status"] = "ok"
        panel.loc[pd.to_numeric(panel.get("roe"), errors="coerce").isna(), "roe_rule_status"] = "source_missing"
    panel = _apply_rule_value_with_status(panel, "roe", "roe_rule_value", "roe_rule_status", {"equity_non_positive"})

    if "cfo_ttm_rule_status" not in panel.columns:
        panel["cfo_ttm_rule_status"] = "ok"
        panel.loc[pd.to_numeric(panel.get("cfo_ttm"), errors="coerce").isna(), "cfo_ttm_rule_status"] = "source_missing"
    panel = _apply_rule_value_with_status(panel, "cfo_ttm", "cfo_ttm_rule_value", "cfo_ttm_rule_status", {"insufficient_history"})
    panel = _apply_rule_value_with_status(
        panel,
        "net_profit_ttm_effective",
        "net_profit_ttm_rule_value",
        "net_profit_ttm_rule_status",
        {"insufficient_history"},
    )

    for raw_column, status_column in (
        ("stock_pe_ttm_q_5y", "pe_ttm_rule_status"),
        ("stock_pe_ttm_q_10y", "pe_ttm_rule_status"),
        ("stock_pe_ttm_q_blended", "pe_ttm_rule_status"),
        ("stock_pe_ttm_history_observations", "pe_ttm_rule_status"),
    ):
        panel = _apply_rule_value_with_status(
            panel,
            raw_column,
            f"{raw_column}_rule_value",
            status_column,
            {"ttm_non_positive", "insufficient_history"},
        )
    for raw_column, status_column in (
        ("stock_pb_q_5y", "pb_rule_status"),
        ("stock_pb_q_10y", "pb_rule_status"),
        ("stock_pb_q_blended", "pb_rule_status"),
        ("stock_pb_history_observations", "pb_rule_status"),
    ):
        panel = _apply_rule_value_with_status(
            panel,
            raw_column,
            f"{raw_column}_rule_value",
            status_column,
            {"equity_non_positive"},
        )
    return panel


def _metric_available_for_core_fields(panel: pd.DataFrame, raw_column: str, rule_column: str) -> pd.Series:
    raw_source = panel[raw_column] if raw_column in panel.columns else pd.Series(np.nan, index=panel.index)
    rule_source = panel[rule_column] if rule_column in panel.columns else pd.Series(np.nan, index=panel.index)
    raw_values = pd.to_numeric(raw_source, errors="coerce")
    rule_values = pd.to_numeric(rule_source, errors="coerce")
    return raw_values.notna() | rule_values.notna()


def _compute_core_fields_complete(panel: pd.DataFrame) -> pd.Series:
    complete = panel[
        [
            "industry",
            "market_cap_billion",
            "avg_amount_60d_million",
            "latest_net_profit",
            "debt_to_assets",
            "industry_pb_q_blended",
            "industry_pe_ttm_q_blended",
        ]
    ].notna().all(axis=1)
    for raw_column, rule_column in (
        ("roe", "roe_rule_value"),
        ("cfo_ttm", "cfo_ttm_rule_value"),
        ("stock_pb_q_blended", "stock_pb_q_blended_rule_value"),
        ("stock_pe_ttm_q_blended", "stock_pe_ttm_q_blended_rule_value"),
    ):
        complete &= _metric_available_for_core_fields(panel, raw_column, rule_column)
    return complete


def _industry_level_rank(level: object) -> int | None:
    if level is None or pd.isna(level):
        return None
    value = str(level).strip().lower()
    mapping = {
        "first": 1,
        "一级行业": 1,
        "一级": 1,
        "second": 2,
        "二级行业": 2,
        "二级": 2,
        "third": 3,
        "三级行业": 3,
        "三级": 3,
    }
    return mapping.get(value)


def _normalize_industry_members(industry_members: pd.DataFrame) -> pd.DataFrame:
    if industry_members.empty:
        return pd.DataFrame(
            columns=[
                "symbol",
                "name",
                "industry_l1_code",
                "industry_l1",
                "industry_l2_code",
                "industry_l2",
                "industry_l3_code",
                "industry_l3",
                "industry_code",
                "industry",
            ]
        )
    members = industry_members.rename(columns={"code": "symbol", "industry_name": "industry"}).copy()
    members["symbol"] = members["symbol"].astype(str)
    members["industry_code"] = members["industry_code"].astype(str).str.replace(".SI", "", regex=False)
    if "name" not in members.columns:
        members["name"] = members["symbol"]
    members["_row_order"] = range(len(members))
    if "industry_level" in members.columns:
        members["_level_rank"] = members["industry_level"].map(_industry_level_rank)
    else:
        members["_level_rank"] = pd.NA

    rows: list[dict] = []
    for symbol, group in members.groupby("symbol", sort=False):
        ordered = group.drop_duplicates(subset=["industry_code", "industry"]).copy()
        ordered["_level_rank"] = ordered["_level_rank"].fillna(pd.Series(range(1, len(ordered) + 1), index=ordered.index))
        ordered = ordered.sort_values(["_level_rank", "_row_order"], ascending=[True, True]).reset_index(drop=True)
        entry = {
            "symbol": symbol,
            "name": str(ordered["name"].dropna().iloc[0]) if ordered["name"].notna().any() else symbol,
        }
        for idx, suffix in enumerate(("l1", "l2", "l3"), start=1):
            row = ordered[ordered["_level_rank"] == idx].head(1)
            if row.empty and len(ordered) >= idx:
                row = ordered.iloc[[idx - 1]]
            if row.empty:
                continue
            entry[f"industry_{suffix}_code"] = str(row.iloc[0]["industry_code"])
            entry[f"industry_{suffix}"] = row.iloc[0]["industry"]
        entry["industry_code"] = entry.get("industry_l1_code") or entry.get("industry_l2_code") or entry.get("industry_l3_code")
        entry["industry"] = entry.get("industry_l1") or entry.get("industry_l2") or entry.get("industry_l3")
        rows.append(entry)
    return pd.DataFrame(rows)


def build_daily_feature_panel(
    price_features: pd.DataFrame,
    financials_effective: pd.DataFrame,
    stock_quantile_panel: pd.DataFrame,
    industry_quantile_panel: pd.DataFrame,
    industry_members: pd.DataFrame,
    st_flags: pd.DataFrame,
    market_caps: pd.DataFrame,
    dividend_daily: pd.DataFrame | None,
    strategy_cfg: dict,
    metric_map_cfg: dict,
) -> pd.DataFrame:
    panel = price_features.rename(columns={"code": "symbol"}).copy()
    if "date" in industry_members.columns:
        members = industry_members.copy()
        if "code" in members.columns and "symbol" not in members.columns:
            members = members.rename(columns={"code": "symbol"})
        if "industry_name" in members.columns and "industry" not in members.columns:
            members = members.rename(columns={"industry_name": "industry"})
        members["symbol"] = members["symbol"].astype(str)
        members["date"] = pd.to_datetime(members["date"], errors="coerce").dt.strftime("%Y-%m-%d")
        panel["date"] = pd.to_datetime(panel["date"], errors="coerce").dt.strftime("%Y-%m-%d")
        keep_columns = [
            column
            for column in (
                "symbol",
                "date",
                "name",
                "industry_l1_code",
                "industry_l1",
                "industry_l2_code",
                "industry_l2",
                "industry_l3_code",
                "industry_l3",
                "industry_code",
                "industry",
            )
            if column in members.columns
        ]
        panel = panel.merge(members[keep_columns].drop_duplicates(subset=["symbol", "date"]), how="left", on=["symbol", "date"])
    else:
        members = _normalize_industry_members(industry_members)
        panel = panel.merge(members, how="left", on="symbol")

    financial_pti = financials_effective.rename(columns={"code": "symbol"})[
        [
            "symbol",
            "date",
            "report_date",
            "announcement_date",
            "effective_date",
            "roe",
            "latest_net_profit",
            "equity_effective",
            "net_profit_ttm_effective",
            "net_profit_ttm_rule_status",
            "cfo_ttm",
            "cfo_ttm_rule_status",
            "debt_to_assets",
            "is_st",
            "dv_ttm",
            "roe_rule_status",
            "profit_positive_years_3y",
            "profit_positive_stability_score",
            "roe_pct_in_last_12_quarters",
        ]
    ]
    panel = _merge_asof_by_key(panel, financial_pti, by="symbol")

    stock_panel = stock_quantile_panel.rename(columns={"code": "symbol"})
    panel = _merge_asof_by_key(panel, stock_panel, by="symbol")

    industry_panel = industry_quantile_panel.drop(columns=["industry_name"], errors="ignore")
    panel = _merge_asof_by_key(panel, industry_panel, by="industry_code")

    panel = _merge_asof_by_key(panel, st_flags.rename(columns={"code": "symbol"})[["symbol", "date", "is_st"]], by="symbol")
    panel = _merge_asof_by_key(
        panel,
        market_caps.rename(columns={"code": "symbol"})[["symbol", "date", "market_cap_billion"]],
        by="symbol",
    )
    if dividend_daily is not None and not dividend_daily.empty:
        dividend_panel = dividend_daily.rename(columns={"code": "symbol"}).copy()
        keep_columns = [
            column
            for column in ("symbol", "date", "dividend_per_share_ttm", "dividend_event_count_ttm", "dv_ttm")
            if column in dividend_panel.columns
        ]
        if {"symbol", "date"} <= set(keep_columns):
            dividend_panel = dividend_panel[keep_columns]
            dividend_panel = _merge_asof_by_key(panel[["symbol", "date"]], dividend_panel, by="symbol")
            if "dividend_per_share_ttm" in dividend_panel.columns:
                panel["dividend_per_share_ttm"] = pd.to_numeric(dividend_panel["dividend_per_share_ttm"], errors="coerce")
            if "dividend_event_count_ttm" in dividend_panel.columns:
                panel["dividend_event_count_ttm"] = pd.to_numeric(dividend_panel["dividend_event_count_ttm"], errors="coerce")
            if "dv_ttm" in dividend_panel.columns:
                dividend_yield = pd.to_numeric(dividend_panel["dv_ttm"], errors="coerce")
                existing_dividend_yield = (
                    pd.to_numeric(panel["dv_ttm"], errors="coerce")
                    if "dv_ttm" in panel.columns
                    else pd.Series(pd.NA, index=panel.index, dtype="Float64")
                )
                panel["dv_ttm"] = dividend_yield.combine_first(existing_dividend_yield)

    panel["name"] = panel["name"].fillna(panel["symbol"])
    if "is_st_x" in panel.columns or "is_st_y" in panel.columns:
        left_st = panel["is_st_x"] if "is_st_x" in panel.columns else pd.Series(False, index=panel.index)
        right_st = panel["is_st_y"] if "is_st_y" in panel.columns else pd.Series(False, index=panel.index)
        panel["is_st"] = left_st.fillna(False) | right_st.fillna(False)
        panel = panel.drop(columns=[column for column in ("is_st_x", "is_st_y") if column in panel.columns])
    elif "is_st" not in panel.columns:
        panel["is_st"] = False
    panel["not_st"] = ~panel["is_st"].fillna(False)
    panel["is_a_share"] = panel["symbol"].astype(str).str.endswith((".sh", ".sz"))
    panel["pb"] = pd.to_numeric(panel.get("stock_pb"), errors="coerce")
    panel["pe_ttm"] = pd.to_numeric(panel.get("stock_pe_ttm"), errors="coerce")
    panel["stock_pb_q_5y"], panel["stock_pb_q_10y"], panel["stock_pb_q_blended"], panel["stock_pb_history_observations"] = _coalesce_metric_quantiles(panel, "pb")
    panel["stock_pe_ttm_q_5y"], panel["stock_pe_ttm_q_10y"], panel["stock_pe_ttm_q_blended"], panel["stock_pe_ttm_history_observations"] = _coalesce_metric_quantiles(panel, "pe_ttm")
    panel = _apply_metric_rule_values(panel)
    panel["industry_pb_q_5y"] = pd.to_numeric(panel.get("industry_pb_q_5y"), errors="coerce")
    panel["industry_pb_q_10y"] = pd.to_numeric(panel.get("industry_pb_q_10y"), errors="coerce")
    panel["industry_pb_q_blended"] = pd.to_numeric(panel.get("industry_pb_q_blended"), errors="coerce")
    panel["industry_pe_ttm_q_5y"] = pd.to_numeric(panel.get("industry_pe_ttm_q_5y"), errors="coerce")
    panel["industry_pe_ttm_q_10y"] = pd.to_numeric(panel.get("industry_pe_ttm_q_10y"), errors="coerce")
    panel["industry_pe_ttm_q_blended"] = pd.to_numeric(panel.get("industry_pe_ttm_q_blended"), errors="coerce")
    panel["primary_metric"] = panel["industry"].map(lambda industry: metric_for_industry_optional(industry, metric_map_cfg))
    panel["main_metric"] = panel["primary_metric"]
    main_metric = panel["main_metric"].astype("string")
    panel["stock_q_5y"] = _select_main_metric_series(main_metric, panel.get("stock_pb_q_5y"), panel.get("stock_pe_ttm_q_5y"))
    panel["stock_q_10y"] = _select_main_metric_series(main_metric, panel.get("stock_pb_q_10y"), panel.get("stock_pe_ttm_q_10y"))
    panel["stock_q_blended"] = _select_main_metric_series(main_metric, panel.get("stock_pb_q_blended"), panel.get("stock_pe_ttm_q_blended"))
    panel["industry_q_5y"] = _select_main_metric_series(main_metric, panel.get("industry_pb_q_5y"), panel.get("industry_pe_ttm_q_5y"))
    panel["industry_q_10y"] = _select_main_metric_series(main_metric, panel.get("industry_pb_q_10y"), panel.get("industry_pe_ttm_q_10y"))
    panel["industry_q_blended"] = _select_main_metric_series(main_metric, panel.get("industry_pb_q_blended"), panel.get("industry_pe_ttm_q_blended"))
    panel["main_metric_history_observations"] = _select_main_metric_series(
        main_metric,
        panel.get("stock_pb_history_observations"),
        panel.get("stock_pe_ttm_history_observations"),
    )
    panel["bucket"] = panel["industry"].map(lambda industry: bucket_for_industry_optional(industry, metric_map_cfg))

    panel["market_cap_percentile"] = _cross_sectional_percentiles_by_date(panel, "market_cap_billion", higher_is_better=True)
    panel["avg_amount_60d_percentile"] = _cross_sectional_percentiles_by_date(panel, "avg_amount_60d_million", higher_is_better=True)
    panel["roe_percentile"] = _cross_sectional_percentiles_by_date(panel, "roe", higher_is_better=True)
    panel["debt_to_assets_percentile"] = _cross_sectional_percentiles_by_date(panel, "debt_to_assets", higher_is_better=True)
    panel["dv_ttm_percentile"] = _cross_sectional_percentiles_by_date(panel, "dv_ttm", higher_is_better=True)
    panel["cfo_score"] = panel["cfo_ttm"].map(lambda value: 100.0 if pd.notna(value) and float(value) > 0 else 0.0)
    panel["industry_market_cap_rank"] = (
        panel.groupby(["date", "industry"])["market_cap_billion"].rank(method="first", ascending=False)
    )
    panel["industry_market_cap_percentile"] = (
        panel.groupby(["date", "industry"])["market_cap_billion"].rank(method="average", pct=True, ascending=False)
    )
    panel["financial_fresh_until"] = pd.to_datetime(panel["report_date"], errors="coerce").map(_financial_fresh_until_date)
    panel["core_data_stale_days"] = _compute_core_data_stale_days(panel["date"], panel["report_date"], panel["effective_date"])
    panel["core_fields_complete"] = _compute_core_fields_complete(panel)
    quality_results = panel.apply(
        lambda row: evaluate_quality(row, strategy_cfg["buckets"][row["bucket"]]["filters"]) if pd.notna(row["bucket"]) else (False, ["bucket"]),
        axis=1,
    )
    panel["quality_pass"] = quality_results.map(lambda item: item[0])
    panel["quality_fail_reasons"] = quality_results.map(lambda item: item[1])
    cyclical_industries = set(strategy_cfg["buckets"]["cyclical_rotation"]["allowed_industries"])
    cyclical_cfg = strategy_cfg["buckets"]["cyclical_rotation"]["cycle_trap_filter"]
    panel["pe_q_blended"] = panel["stock_pe_ttm_q_blended"]
    cyclical_mask = panel["industry"].isin(cyclical_industries)
    pe_q_blended = pd.to_numeric(panel["pe_q_blended"], errors="coerce")
    roe_pct = pd.to_numeric(panel["roe_pct_in_last_12_quarters"], errors="coerce")
    primary_trigger = (
        pe_q_blended.le(float(cyclical_cfg["pe_q_blended_max_primary"]))
        & roe_pct.ge(float(cyclical_cfg["roe_pct_in_last_12_quarters_min_primary"]))
    )
    secondary_trigger = (
        pe_q_blended.le(float(cyclical_cfg["pe_q_blended_max_secondary"]))
        & roe_pct.ge(float(cyclical_cfg["roe_pct_in_last_12_quarters_min_secondary"]))
    )
    panel["cycle_peak_trap"] = (cyclical_mask & (primary_trigger | secondary_trigger)).fillna(False)
    panel["thesis_still_valid"] = panel["quality_pass"] & ~panel["cycle_peak_trap"]
    return panel.sort_values(["date", "symbol"]).reset_index(drop=True)


def build_feature_snapshot(
    price_features: pd.DataFrame,
    latest_financials: pd.DataFrame,
    st_flags: pd.DataFrame,
    market_caps: pd.DataFrame,
    industry_members: pd.DataFrame,
    industry_quantiles: pd.DataFrame,
    stock_quantiles: pd.DataFrame,
    dividend_daily: pd.DataFrame | None,
    strategy_cfg: dict,
    metric_map_cfg: dict,
) -> pd.DataFrame:
    latest_prices = price_features.sort_values(["code", "date"]).groupby("code", as_index=False).tail(1).copy()
    latest_financials = latest_financials.sort_values(["code", "date"]).groupby("code", as_index=False).tail(1).copy()
    st_flags = st_flags.sort_values(["code", "date"]).groupby("code", as_index=False).tail(1).copy()
    market_caps = market_caps.sort_values(["code", "date"]).groupby("code", as_index=False).tail(1).copy()
    stock_quantiles = stock_quantiles.sort_values(["code", "date"]).groupby("code", as_index=False).tail(1).copy()
    industry_quantiles = industry_quantiles.sort_values(["industry_code", "date"]).groupby("industry_code", as_index=False).tail(1).copy()
    return build_daily_feature_panel(
        price_features=latest_prices,
        financials_effective=latest_financials,
        stock_quantile_panel=stock_quantiles,
        industry_quantile_panel=industry_quantiles,
        industry_members=industry_members,
        st_flags=st_flags,
        market_caps=market_caps,
        dividend_daily=dividend_daily,
        strategy_cfg=strategy_cfg,
        metric_map_cfg=metric_map_cfg,
    )
