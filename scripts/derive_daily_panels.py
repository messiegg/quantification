#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.pipeline.features import prepare_financial_effective_frame
from src.pipeline.strict_data import (
    build_dividend_daily,
    build_industry_daily,
    build_market_cap_daily,
    build_shares_daily,
    build_stock_valuation_daily,
    strict_run_dates,
)
from src.strategy.metric_map import metric_for_industry_optional
from src.utils.config import load_project_configs, resolve_path
from src.utils.exceptions import DataSourceError
from src.utils.storage import write_blocker_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Derive strict daily panels from raw share, industry, financial, and price data.")
    parser.add_argument("--as-of-date", required=True, help="Strict as-of date in YYYY-MM-DD format.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    configs = load_project_configs()
    data_cfg = configs["data_sources"]
    strategy_cfg = configs["strategy"]
    metric_map_cfg = configs["metric_map"]
    strict_dates = strict_run_dates(args.as_of_date, data_cfg)

    prices = pd.read_parquet(resolve_path("data/raw/price_daily.parquet"))
    share_change = pd.read_parquet(resolve_path("data/raw/share_change.parquet"))
    financials = pd.read_parquet(resolve_path("data/raw/financials.parquet"))
    dividend_events_path = resolve_path("data/raw/dividend_events.parquet")
    dividend_events = pd.read_parquet(dividend_events_path) if dividend_events_path.exists() else pd.DataFrame()
    industry_members_effective = pd.read_parquet(resolve_path("data/curated/industry_members_effective.parquet"))

    financials_effective = prepare_financial_effective_frame(financials, strategy_cfg)
    shares_daily = build_shares_daily(prices, share_change)
    market_cap_daily = build_market_cap_daily(prices, shares_daily)
    dividend_daily = build_dividend_daily(prices, dividend_events)
    stock_valuation_daily = build_stock_valuation_daily(market_cap_daily, financials_effective)
    industry_daily = build_industry_daily(stock_valuation_daily, industry_members_effective)

    resolve_path("data/curated").mkdir(parents=True, exist_ok=True)
    financials_effective.to_parquet(resolve_path("data/curated/financials_effective.parquet"), index=False)
    shares_daily.to_parquet(resolve_path("data/curated/shares_daily.parquet"), index=False)
    market_cap_daily.to_parquet(resolve_path("data/curated/market_cap_daily.parquet"), index=False)
    dividend_daily.to_parquet(resolve_path("data/curated/dividend_daily.parquet"), index=False)
    stock_valuation_daily.to_parquet(resolve_path("data/curated/stock_valuation_daily.parquet"), index=False)
    industry_daily.to_parquet(resolve_path("data/curated/industry_daily.parquet"), index=False)

    current_industry = industry_members_effective[industry_members_effective["date"] == args.as_of_date].copy()
    required_industries = sorted(
        {
            industry
            for industry in current_industry["industry"].dropna().astype(str).tolist()
            if pd.notna(metric_for_industry_optional(industry, metric_map_cfg))
        }
    )
    industry_today = industry_daily[industry_daily["date"] == args.as_of_date].copy()
    categories: list[dict] = []
    missing_market_caps = market_cap_daily[(market_cap_daily["date"] == args.as_of_date) & market_cap_daily["market_cap_billion"].isna()]["symbol"].astype(str).tolist()
    if missing_market_caps:
        categories.append({"category": "market_cap_missing", "count": len(missing_market_caps), "symbols": missing_market_caps[:200]})

    missing_industries: list[str] = []
    for industry in required_industries:
        metric = metric_for_industry_optional(industry, metric_map_cfg)
        subset = industry_today[industry_today["industry_name"] == industry].copy()
        if subset.empty or subset[metric].isna().all():
            missing_industries.append(industry)
    if missing_industries:
        categories.append({"category": "industry_daily_missing_required_metric", "count": len(missing_industries), "industries": missing_industries})

    if categories:
        write_blocker_report(
            name="daily_panels",
            as_of_date=args.as_of_date,
            stage="derive_daily_panels",
            categories=categories,
            output_dir=strict_dates["blocker_dir"],
        )
        raise DataSourceError(f"Strict daily panel derivation has blockers: {categories}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
