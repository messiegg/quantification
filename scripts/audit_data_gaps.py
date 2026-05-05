#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.utils.cli import write_json
from src.utils.config import load_project_configs, resolve_path
from src.utils.data_gaps import (
    TableStatus,
    financial_ready_symbols,
    hs_a_share_symbols,
    latest_ready_symbols,
    missing_symbols,
    price_ready_symbols,
    valuation_ready_symbols,
)


RAW_FILES = {
    "stock_list": "data/raw/stock_list.parquet",
    "price_daily": "data/raw/price_daily.parquet",
    "benchmark_daily": "data/raw/benchmark_daily.parquet",
    "stock_valuation": "data/raw/stock_valuation.parquet",
    "industry_daily": "data/raw/industry_daily.parquet",
    "industry_members": "data/raw/industry_members.parquet",
    "financials": "data/raw/financials.parquet",
    "st_flags": "data/raw/st_flags.parquet",
    "market_caps": "data/raw/market_caps.parquet",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit local data readiness and emit missing-data checklists.")
    parser.add_argument("--current-date", default="", help="Current calendar date in YYYY-MM-DD; defaults to today.")
    parser.add_argument("--trading-date", default="", help="Target trading date; defaults to max available price date.")
    parser.add_argument("--output-json", default="reports/data_gaps/latest.json", help="JSON summary output path.")
    parser.add_argument("--output-md", default="reports/data_gaps/latest.md", help="Markdown summary output path.")
    parser.add_argument("--missing-dir", default="data/curated/missing_data", help="Directory for missing symbol lists.")
    return parser.parse_args()


def read_dataset(path_like: str) -> pd.DataFrame:
    path = resolve_path(path_like)
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


def write_symbol_list(path_like: str | Path, symbols: list[str]) -> str:
    path = resolve_path(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(symbols) + ("\n" if symbols else ""), encoding="utf-8")
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def clean_benchmark(benchmark: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    if benchmark.empty:
        return benchmark.copy(), 0
    selected = benchmark.copy()
    invalid_rows = int(selected["code"].isna().sum()) if "code" in selected.columns else 0
    if "code" in selected.columns:
        selected = selected[selected["code"].notna()].copy()
    return selected, invalid_rows


def latest_trading_date(price_daily: pd.DataFrame, benchmark: pd.DataFrame) -> str:
    dates: list[pd.Timestamp] = []
    if not price_daily.empty and "date" in price_daily.columns:
        dates.append(pd.to_datetime(price_daily["date"], errors="coerce").max())
    if not benchmark.empty and "date" in benchmark.columns:
        dates.append(pd.to_datetime(benchmark["date"], errors="coerce").max())
    valid_dates = [date for date in dates if pd.notna(date)]
    if not valid_dates:
        return pd.Timestamp.today().strftime("%Y-%m-%d")
    return max(valid_dates).strftime("%Y-%m-%d")


def main() -> int:
    args = parse_args()
    configs = load_project_configs()
    strategy_cfg = configs["strategy"]
    trading_days_per_year = int(strategy_cfg["valuation"]["trading_days_per_year"])
    valuation_history_min_rows = 5 * trading_days_per_year

    stock_list = read_dataset(RAW_FILES["stock_list"])
    price_daily = read_dataset(RAW_FILES["price_daily"])
    benchmark_raw = read_dataset(RAW_FILES["benchmark_daily"])
    benchmark_daily, benchmark_invalid_rows = clean_benchmark(benchmark_raw)
    stock_valuation = read_dataset(RAW_FILES["stock_valuation"])
    industry_daily = read_dataset(RAW_FILES["industry_daily"])
    industry_members = read_dataset(RAW_FILES["industry_members"])
    financials = read_dataset(RAW_FILES["financials"])
    st_flags = read_dataset(RAW_FILES["st_flags"])
    market_caps = read_dataset(RAW_FILES["market_caps"])

    current_date = args.current_date or pd.Timestamp.today().strftime("%Y-%m-%d")
    target_trading_date = args.trading_date or latest_trading_date(price_daily, benchmark_daily)
    hs_symbols = hs_a_share_symbols(stock_list)

    price_ready = price_ready_symbols(price_daily, hs_symbols, target_trading_date, min_rows=250)
    st_ready = latest_ready_symbols(st_flags, hs_symbols, "date", current_date)
    market_cap_ready = latest_ready_symbols(market_caps, hs_symbols, "date", current_date)
    valuation_pb_ready = valuation_ready_symbols(stock_valuation, hs_symbols, "pb", target_trading_date, valuation_history_min_rows)
    valuation_pe_ready = valuation_ready_symbols(stock_valuation, hs_symbols, "pe_ttm", target_trading_date, valuation_history_min_rows)
    financial_ready = financial_ready_symbols(financials, hs_symbols, "2025-12-31")
    industry_member_ready = latest_ready_symbols(industry_members, hs_symbols, "as_of_date", current_date)

    missing_dir = resolve_path(args.missing_dir)
    missing_dir.mkdir(parents=True, exist_ok=True)
    missing_lists = {
        "price": missing_symbols(hs_symbols, price_ready),
        "st_flags": missing_symbols(hs_symbols, st_ready),
        "market_caps": missing_symbols(hs_symbols, market_cap_ready),
        "valuation_pb": missing_symbols(hs_symbols, valuation_pb_ready),
        "valuation_pe_ttm": missing_symbols(hs_symbols, valuation_pe_ready),
        "financials": missing_symbols(hs_symbols, financial_ready),
        "industry_members": missing_symbols(hs_symbols, industry_member_ready),
    }
    missing_counts = {name: len(symbols) for name, symbols in missing_lists.items()}
    core_symbol_missing = sorted(set().union(*[set(symbols) for symbols in missing_lists.values()]))
    missing_files = {
        name: write_symbol_list(missing_dir / f"{name}_missing.txt", symbols)
        for name, symbols in missing_lists.items()
    }
    missing_files["core_symbol_data"] = write_symbol_list(missing_dir / "core_symbol_data_missing.txt", core_symbol_missing)

    industry_members_latest = str(industry_members["as_of_date"].max()) if not industry_members.empty and "as_of_date" in industry_members.columns else ""
    industry_daily_latest = str(pd.to_datetime(industry_daily["date"], errors="coerce").max().date()) if not industry_daily.empty and "date" in industry_daily.columns else ""
    benchmark_latest = str(pd.to_datetime(benchmark_daily["date"], errors="coerce").max().date()) if not benchmark_daily.empty else ""
    benchmark_ready = bool(benchmark_latest and benchmark_latest >= target_trading_date and benchmark_invalid_rows == 0)
    industry_members_ready = len(industry_member_ready) == len(hs_symbols)
    industry_daily_ready = bool(industry_daily_latest and industry_daily_latest >= target_trading_date)

    table_statuses = [
        TableStatus("stock_list", str(stock_list["as_of_date"].max()) if not stock_list.empty and "as_of_date" in stock_list.columns else "", True, len(stock_list), len(hs_symbols), "master symbol table"),
        TableStatus("price_daily", target_trading_date, len(price_ready) == len(hs_symbols), len(price_daily), len(price_ready), "requires >=250 rows and latest trade date"),
        TableStatus("st_flags", str(st_flags["date"].max()) if not st_flags.empty and "date" in st_flags.columns else "", len(st_ready) == len(hs_symbols), len(st_flags), len(st_ready)),
        TableStatus("market_caps", str(market_caps["date"].max()) if not market_caps.empty and "date" in market_caps.columns else "", len(market_cap_ready) == len(hs_symbols), len(market_caps), len(market_cap_ready)),
        TableStatus("valuation_pb", target_trading_date, len(valuation_pb_ready) == len(hs_symbols), len(stock_valuation[stock_valuation.get("metric").astype(str) == "pb"]) if not stock_valuation.empty and "metric" in stock_valuation.columns else 0, len(valuation_pb_ready), "requires latest date and >=5y history"),
        TableStatus("valuation_pe_ttm", target_trading_date, len(valuation_pe_ready) == len(hs_symbols), len(stock_valuation[stock_valuation.get("metric").astype(str) == "pe_ttm"]) if not stock_valuation.empty and "metric" in stock_valuation.columns else 0, len(valuation_pe_ready), "requires latest date and >=5y history"),
        TableStatus("financials", "2025-12-31", len(financial_ready) == len(hs_symbols), len(financials), len(financial_ready), "latest report with roe/net_profit/cfo/debt_to_assets"),
        TableStatus("benchmark_daily", benchmark_latest, benchmark_ready, len(benchmark_daily), benchmark_daily["code"].nunique() if not benchmark_daily.empty and "code" in benchmark_daily.columns else 0, f"invalid_rows={benchmark_invalid_rows}"),
        TableStatus("industry_daily", industry_daily_latest, industry_daily_ready, len(industry_daily), industry_daily["industry_code"].nunique() if not industry_daily.empty and "industry_code" in industry_daily.columns else 0, "required for industry quantiles"),
        TableStatus("industry_members", industry_members_latest, industry_members_ready, len(industry_members), len(industry_member_ready), "required for latest industry mapping"),
    ]

    blockers: list[dict[str, str]] = []
    if not benchmark_ready:
        blockers.append({"dataset": "benchmark_daily", "reason": f"latest_valid={benchmark_latest or 'missing'}, invalid_rows={benchmark_invalid_rows}"})
    if not industry_daily_ready:
        blockers.append({"dataset": "industry_daily", "reason": f"latest={industry_daily_latest or 'missing'} < target_trading_date={target_trading_date}"})
    if not industry_members_ready:
        blockers.append(
            {
                "dataset": "industry_members",
                "reason": f"latest={industry_members_latest or 'missing'}, current_ready_symbols={len(industry_member_ready)}/{len(hs_symbols)}",
            }
        )

    payload = {
        "current_date": current_date,
        "target_trading_date": target_trading_date,
        "hs_a_share_symbol_count": len(hs_symbols),
        "table_status": [status.__dict__ for status in table_statuses],
        "missing_counts": {**missing_counts, "core_symbol_data": len(core_symbol_missing)},
        "missing_files": missing_files,
        "blockers": blockers,
    }
    write_json(args.output_json, payload)

    lines = [
        f"# Data Gaps ({current_date})",
        "",
        f"- Target trading date: {target_trading_date}",
        f"- HS A-share symbols in master list: {len(hs_symbols)}",
        "- Scope: full-market strict data gap audit; this is not the observation gate decision.",
        "- Paths are repo-relative so the report is safe to publish.",
        "",
        "## Table Status",
        "",
    ]
    for status in table_statuses:
        ready_text = "ready" if status.ready else "missing"
        lines.append(
            f"- {status.dataset}: {ready_text} | latest={status.latest_value or 'n/a'} | rows={status.row_count} | ready_unique={status.unique_count} | {status.note}".rstrip()
        )
    lines.extend(["", "## Missing Symbol Files", ""])
    for name, path in missing_files.items():
        lines.append(f"- {name}: {path} ({payload['missing_counts'][name]})")
    lines.extend(["", "## Blocking Tables", ""])
    if blockers:
        for blocker in blockers:
            lines.append(f"- {blocker['dataset']}: {blocker['reason']}")
    else:
        lines.append("- none")
    output_md = resolve_path(args.output_md)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
