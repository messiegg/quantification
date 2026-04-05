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
from src.pipeline.strict_data import strict_run_dates
from src.utils.config import load_project_configs, resolve_path
from src.utils.exceptions import DataSourceError
from src.utils.storage import write_blocker_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill strict share-change history from CNInfo.")
    parser.add_argument("--as-of-date", required=True, help="Strict as-of date in YYYY-MM-DD format.")
    parser.add_argument("--start-date", default="1990-01-01", help="Share-change history start date.")
    parser.add_argument("--workers", type=int, default=12, help="Parallel worker count.")
    return parser.parse_args()


def _target_symbols(as_of_date: str) -> list[str]:
    stock_list = pd.read_parquet(resolve_path("data/raw/stock_list.parquet"))
    prices_path = resolve_path("data/raw/price_daily.parquet")
    if prices_path.exists():
        prices = pd.read_parquet(prices_path)
        as_of_symbols = prices.loc[prices["date"] == as_of_date, "code"].astype(str).tolist()
        if as_of_symbols:
            return list(dict.fromkeys(as_of_symbols))
    return list(dict.fromkeys(stock_list["code"].astype(str).tolist()))


def main() -> int:
    args = parse_args()
    configs = load_project_configs()
    data_cfg = configs["data_sources"]
    ak = AkshareAdapter(data_cfg)
    strict_dates = strict_run_dates(args.as_of_date, data_cfg)
    symbols = _target_symbols(args.as_of_date)
    frames: list[pd.DataFrame] = []
    failed: list[str] = []
    empty: list[str] = []

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = {
            executor.submit(ak.get_share_change_cninfo, symbol, args.start_date, strict_dates["as_of_date"]): symbol for symbol in symbols
        }
        for future in as_completed(futures):
            symbol = futures[future]
            try:
                frame = future.result()
            except Exception:
                failed.append(symbol)
                continue
            if frame.empty:
                empty.append(symbol)
                continue
            frames.append(frame)

    if not frames:
        write_blocker_report(
            name="share_change",
            as_of_date=args.as_of_date,
            stage="backfill_share_change",
            categories=[{"category": "share_change_all_failed", "count": len(symbols), "symbols": symbols[:200]}],
            output_dir=strict_dates["blocker_dir"],
        )
        raise DataSourceError("Strict share_change backfill failed for every symbol.")

    combined = pd.concat(frames, ignore_index=True)
    combined["symbol"] = combined["symbol"].astype(str)
    combined["announce_date"] = pd.to_datetime(combined["announce_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    combined["change_date"] = pd.to_datetime(combined["change_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    combined = combined.drop_duplicates(subset=["symbol", "change_date", "announce_date", "reason"], keep="last").sort_values(["symbol", "change_date", "announce_date"])
    output_path = resolve_path("data/raw/share_change.parquet")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    combined.to_parquet(output_path, index=False)

    categories: list[dict] = []
    if failed:
        categories.append({"category": "share_change_fetch_failed", "count": len(failed), "symbols": failed[:200]})
    if empty:
        categories.append({"category": "share_change_empty", "count": len(empty), "symbols": empty[:200]})
    if categories:
        write_blocker_report(
            name="share_change",
            as_of_date=args.as_of_date,
            stage="backfill_share_change",
            categories=categories,
            output_dir=strict_dates["blocker_dir"],
        )
        raise DataSourceError(f"Strict share_change backfill has blockers: {categories}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
