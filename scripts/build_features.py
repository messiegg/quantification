#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.pipeline.features import (
    build_daily_feature_panel,
    compute_industry_quantiles,
    compute_industry_quantile_panel,
    compute_price_features,
    compute_stock_quantiles,
    compute_stock_quantile_panel,
    prepare_financial_effective_frame,
)
from src.pipeline.strict_data import build_trade_calendar
from src.utils.config import load_project_configs, resolve_path
from src.utils.exceptions import DataSourceError
from src.utils.storage import write_feature_dataset


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build point-in-time daily features from cached raw data.")
    parser.add_argument("--as-of-date", default="", help="Optional as-of date for strict coverage validation.")
    parser.add_argument("--output-file", default="data/features/daily_features", help="Daily feature parquet file or yearly-partitioned directory output path.")
    parser.add_argument("--latest-output-file", default="data/features/latest_feature_snapshot.parquet", help="Latest feature snapshot output path.")
    return parser.parse_args()


def read_required(path_like: str) -> pd.DataFrame:
    path = resolve_path(path_like)
    if not path.exists():
        raise DataSourceError(f"Required raw dataset missing: {path}")
    return pd.read_parquet(path)


def read_if_covers_as_of(path_like: str, as_of_date: str) -> pd.DataFrame:
    path = resolve_path(path_like)
    if not path.exists():
        return pd.DataFrame()
    frame = pd.read_parquet(path)
    if frame.empty or "date" not in frame.columns:
        return pd.DataFrame()
    if as_of_date and str(as_of_date) not in set(frame["date"].astype(str)):
        return pd.DataFrame()
    return frame


def read_if_covers_date_range(path_like: str, source_frame: pd.DataFrame) -> pd.DataFrame:
    path = resolve_path(path_like)
    if not path.exists() or source_frame.empty or "date" not in source_frame.columns:
        return pd.DataFrame()
    frame = pd.read_parquet(path)
    if frame.empty or "date" not in frame.columns:
        return pd.DataFrame()
    source_dates = pd.to_datetime(source_frame["date"], errors="coerce").dropna()
    cached_dates = pd.to_datetime(frame["date"], errors="coerce").dropna()
    if source_dates.empty or cached_dates.empty:
        return pd.DataFrame()
    if cached_dates.min() > source_dates.min() or cached_dates.max() < source_dates.max():
        return pd.DataFrame()
    return frame


def write_feature_output(frame: pd.DataFrame, output_path_like: str, as_of_date: str) -> None:
    if not as_of_date:
        write_feature_dataset(frame, output_path_like)
        return
    output_path = resolve_path(output_path_like)
    target = output_path
    if output_path.suffix != ".parquet":
        target = output_path / f"{pd.Timestamp(as_of_date).year}.parquet"
    existing = pd.read_parquet(target) if target.exists() else pd.DataFrame()
    if not existing.empty and "date" in existing.columns:
        existing = existing[existing["date"].astype(str) != str(as_of_date)].copy()
    combined = pd.concat([existing, frame], ignore_index=True, sort=False) if not existing.empty else frame.copy()
    sort_columns = [column for column in ("date", "symbol") if column in combined.columns]
    if sort_columns:
        combined = combined.sort_values(sort_columns).reset_index(drop=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    combined.to_parquet(target, index=False)


def main() -> int:
    args = parse_args()
    configs = load_project_configs()
    strategy_cfg = configs["strategy"]
    metric_map_cfg = configs["metric_map"]

    prices = read_required("data/raw/price_daily.parquet")
    benchmark_daily = read_required("data/raw/benchmark_daily.parquet")
    stock_list = read_required("data/raw/stock_list.parquet")
    trade_calendar_path = resolve_path("data/curated/trade_calendar.parquet")
    if trade_calendar_path.exists():
        trade_calendar = pd.read_parquet(trade_calendar_path)
    else:
        trade_calendar = build_trade_calendar(prices)
        if trade_calendar.empty:
            raise DataSourceError("Unable to build formal trade calendar from price_daily.")
        trade_calendar_path.parent.mkdir(parents=True, exist_ok=True)
        trade_calendar.to_parquet(trade_calendar_path, index=False)
    stock_valuation = read_required("data/curated/stock_valuation_daily.parquet")
    industry_daily = read_required("data/curated/industry_daily.parquet")
    industry_members = read_required("data/curated/industry_members_effective.parquet")
    financials = read_required("data/raw/financials.parquet")
    st_flags = read_required("data/raw/st_flags.parquet")
    market_caps = read_required("data/curated/market_cap_daily.parquet")
    dividend_daily_path = resolve_path("data/curated/dividend_daily.parquet")
    dividend_daily = pd.read_parquet(dividend_daily_path) if dividend_daily_path.exists() else pd.DataFrame()

    price_features = compute_price_features(
        prices,
        stock_list=stock_list,
        trade_calendar=trade_calendar,
        benchmark_daily=benchmark_daily,
    )
    panel_prices = price_features
    if args.as_of_date:
        panel_prices = price_features[price_features["date"].astype(str) == str(args.as_of_date)].copy()
        if panel_prices.empty:
            raise DataSourceError(f"Price feature panel does not cover strict as-of date {args.as_of_date}.")
    # Always rebuild the derived financial frame so logic changes do not silently reuse stale caches.
    financials_effective = prepare_financial_effective_frame(financials, strategy_cfg)
    stock_quantile_panel = pd.DataFrame()
    if not args.as_of_date:
        stock_quantile_panel = read_if_covers_date_range("data/curated/stock_quantiles.parquet", stock_valuation)
    if stock_quantile_panel.empty:
        stock_quantile_panel = (
            compute_stock_quantiles(stock_valuation, strategy_cfg)
            if args.as_of_date
            else compute_stock_quantile_panel(stock_valuation, strategy_cfg)
        )
    industry_quantile_panel = pd.DataFrame()
    if not args.as_of_date:
        industry_quantile_panel = read_if_covers_date_range("data/curated/industry_quantiles.parquet", industry_daily)
    if industry_quantile_panel.empty:
        industry_quantile_panel = (
            compute_industry_quantiles(industry_daily, strategy_cfg, metric="pb")
            if args.as_of_date
            else compute_industry_quantile_panel(industry_daily, strategy_cfg, metric_map_cfg)
        )
    daily_features = build_daily_feature_panel(
        panel_prices,
        financials_effective,
        stock_quantile_panel,
        industry_quantile_panel,
        industry_members,
        st_flags,
        market_caps,
        dividend_daily,
        strategy_cfg,
        metric_map_cfg,
    )
    if args.as_of_date and str(args.as_of_date) not in set(daily_features["date"].astype(str)):
        raise DataSourceError(f"Feature panel does not cover strict as-of date {args.as_of_date}.")
    write_feature_output(daily_features, args.output_file, args.as_of_date)

    latest = daily_features.sort_values(["symbol", "date"]).groupby("symbol", as_index=False).tail(1).copy()
    latest_output = resolve_path(args.latest_output_file)
    latest_output.parent.mkdir(parents=True, exist_ok=True)
    latest.to_parquet(latest_output, index=False)

    resolve_path("data/curated/financials_effective.parquet").parent.mkdir(parents=True, exist_ok=True)
    financials_effective.to_parquet(resolve_path("data/curated/financials_effective.parquet"), index=False)
    stock_quantile_panel.to_parquet(resolve_path("data/curated/stock_quantiles.parquet"), index=False)
    industry_quantile_panel.to_parquet(resolve_path("data/curated/industry_quantiles.parquet"), index=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
