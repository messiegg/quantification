#!/usr/bin/env python3
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.adapters.akshare_adapter import AkshareAdapter
from src.pipeline.strict_data import build_industry_members_effective, strict_run_dates
from src.utils.config import load_project_configs, resolve_path
from src.utils.exceptions import DataSourceError
from src.utils.storage import write_blocker_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill strict SW industry history and daily effective membership.")
    parser.add_argument("--as-of-date", required=True, help="Strict as-of date in YYYY-MM-DD format.")
    parser.add_argument("--start-date", default="1990-01-01", help="Fallback CNInfo history start date.")
    parser.add_argument("--workers", type=int, default=12, help="Parallel worker count.")
    return parser.parse_args()


def _target_symbols(as_of_date: str) -> list[str]:
    prices = pd.read_parquet(resolve_path("data/raw/price_daily.parquet"))
    as_of_symbols = prices.loc[prices["date"] == as_of_date, "code"].astype(str).tolist()
    if as_of_symbols:
        return list(dict.fromkeys(as_of_symbols))
    stock_list = pd.read_parquet(resolve_path("data/raw/stock_list.parquet"))
    return list(dict.fromkeys(stock_list["code"].astype(str).tolist()))


def main() -> int:
    args = parse_args()
    configs = load_project_configs()
    data_cfg = configs["data_sources"]
    ak = AkshareAdapter(data_cfg)
    strict_dates = strict_run_dates(args.as_of_date, data_cfg)
    prices = pd.read_parquet(resolve_path("data/raw/price_daily.parquet"))
    stock_list = pd.read_parquet(resolve_path("data/raw/stock_list.parquet"))
    target_symbols = _target_symbols(args.as_of_date)

    sw_hist = ak.get_sw_industry_hist()
    sw_category = ak.get_sw_industry_category_cninfo()
    hist_target = sw_hist[sw_hist["symbol"].isin(target_symbols)].copy()
    covered = set(hist_target["symbol"].astype(str))
    missing_symbols = sorted(set(target_symbols) - covered)
    fallback_frames: list[pd.DataFrame] = []
    fallback_failures: list[str] = []

    if missing_symbols:
        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
            futures = {
                executor.submit(ak.get_industry_change_cninfo, symbol, args.start_date, strict_dates["as_of_date"]): symbol for symbol in missing_symbols
            }
            for future in as_completed(futures):
                symbol = futures[future]
                try:
                    frame = future.result()
                except Exception:
                    fallback_failures.append(symbol)
                    continue
                frame = frame[frame["standard_name"].astype(str).str.contains("申银万国行业分类标准", na=False)].copy()
                if frame.empty:
                    fallback_failures.append(symbol)
                    continue
                converted = frame.rename(columns={"change_date": "start_date"})[["symbol", "start_date", "industry_code", "source"]].copy()
                converted["update_time"] = pd.NA
                fallback_frames.append(converted)

    combined_hist = pd.concat([hist_target, *fallback_frames], ignore_index=True) if fallback_frames else hist_target.copy()
    combined_hist["symbol"] = combined_hist["symbol"].astype(str)
    combined_hist["start_date"] = pd.to_datetime(combined_hist["start_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    combined_hist["industry_code"] = combined_hist["industry_code"].astype(str).str.removeprefix("S")
    combined_hist = combined_hist.drop_duplicates(subset=["symbol", "start_date", "industry_code"], keep="last").sort_values(["symbol", "start_date"])

    raw_output = resolve_path("data/raw/industry_hist_sw.parquet")
    raw_output.parent.mkdir(parents=True, exist_ok=True)
    combined_hist.to_parquet(raw_output, index=False)

    effective = build_industry_members_effective(
        price_daily=prices[prices["code"].astype(str).isin(target_symbols)].copy(),
        industry_history=combined_hist,
        sw_category=sw_category,
        stock_list=stock_list,
    )
    curated_output = resolve_path("data/curated/industry_members_effective.parquet")
    curated_output.parent.mkdir(parents=True, exist_ok=True)
    effective.to_parquet(curated_output, index=False)

    current_effective = effective[effective["date"] == args.as_of_date].copy()
    missing_current = sorted(set(target_symbols) - set(current_effective["symbol"].astype(str)))
    missing_mapping = current_effective[current_effective["industry_code"].isna() | current_effective["industry"].isna()]["symbol"].astype(str).tolist()
    categories: list[dict] = []
    if fallback_failures:
        categories.append({"category": "industry_history_fallback_failed", "count": len(fallback_failures), "symbols": fallback_failures[:200]})
    if missing_current:
        categories.append({"category": "industry_effective_missing_symbol", "count": len(missing_current), "symbols": missing_current[:200]})
    if missing_mapping:
        categories.append({"category": "industry_effective_missing_mapping", "count": len(missing_mapping), "symbols": missing_mapping[:200]})
    if categories:
        write_blocker_report(
            name="industry_history",
            as_of_date=args.as_of_date,
            stage="backfill_industry_history",
            categories=categories,
            output_dir=strict_dates["blocker_dir"],
        )
        raise DataSourceError(f"Strict industry history backfill has blockers: {categories}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
