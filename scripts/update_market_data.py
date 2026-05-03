#!/usr/bin/env python3
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import sys
from threading import Lock
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.adapters.adata_adapter import ADataAdapter
from src.adapters.akshare_adapter import AkshareAdapter
from src.adapters.baostock_adapter import BaoStockAdapter
from src.adapters.factory import create_default_adapter
from src.pipeline.strict_data import (
    build_trade_calendar,
    fetch_akshare_tx_prices,
    fetch_financials_safe,
    clean_benchmark_frame,
    clean_price_frame,
    fetch_benchmark_daily,
    fetch_pytdx_stock_list,
    fetch_tdx_local_prices,
    first_existing_tdx_dir,
    strict_run_dates,
)
from src.utils.config import load_project_configs, resolve_path
from src.utils.exceptions import DataSourceError
from src.utils.ops import write_data_quality_report, write_provider_health_report
from src.utils.storage import clear_directories, configured_cache_directories, write_json_report


RAW_FILES = {
    "stock_list": "data/raw/stock_list.parquet",
    "price_daily": "data/raw/price_daily.parquet",
    "benchmark_daily": "data/raw/benchmark_daily.parquet",
    "stock_valuation": "data/raw/stock_valuation.parquet",
    "industry_daily": "data/raw/industry_daily.parquet",
    "industry_members": "data/raw/industry_members.parquet",
    "financials": "data/raw/financials.parquet",
    "dividend_events": "data/raw/dividend_events.parquet",
    "st_flags": "data/raw/st_flags.parquet",
    "market_caps": "data/raw/market_caps.parquet",
}


STRICT_BAOSTOCK_LOCK = Lock()
NON_BLOCKING_FINANCIAL_ISSUES = {"roe_missing_on_latest"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download and cache A-share research data locally.")
    parser.add_argument("--as-of-date", default="", help="Strict run date in YYYY-MM-DD format.")
    parser.add_argument("--start-date", default="", help="Start date in YYYY-MM-DD format.")
    parser.add_argument("--end-date", default="", help="End date in YYYY-MM-DD format.")
    parser.add_argument("--price-start-date", default="", help="Optional override for price history fetch start date.")
    parser.add_argument("--benchmark-start-date", default="", help="Optional override for benchmark fetch start date.")
    parser.add_argument("--industry-start-date", default="", help="Optional override for industry history fetch start date.")
    parser.add_argument(
        "--financial-start-date",
        default="",
        help="Optional override for financial statement fetch start date. Defaults to --start-date.",
    )
    parser.add_argument("--symbols-file", default="", help="Optional file containing one symbol per line.")
    parser.add_argument("--skip-stock-list", action="store_true", help="Skip stock list refresh.")
    parser.add_argument("--skip-prices", action="store_true", help="Skip price history refresh.")
    parser.add_argument("--skip-financials", action="store_true", help="Skip financial statement refresh.")
    parser.add_argument("--skip-dividends", action="store_true", help="Skip dividend event refresh.")
    parser.add_argument("--skip-industry", action="store_true", help="Skip SW industry member and daily refresh.")
    parser.add_argument("--skip-industry-members", action="store_true", help="Skip industry member refresh.")
    parser.add_argument("--skip-industry-daily", action="store_true", help="Skip industry daily refresh.")
    parser.add_argument(
        "--prefer-symbol-industry-fallback",
        action="store_true",
        help="Skip catalog-based industry member fetch and use AData symbol-industry mapping directly.",
    )
    parser.add_argument("--skip-st-flags", action="store_true", help="Skip ST flag refresh.")
    parser.add_argument("--skip-market-caps", action="store_true", help="Skip market cap refresh.")
    parser.add_argument("--skip-valuations", action="store_true", help="Skip stock valuation history refresh.")
    parser.add_argument("--skip-benchmark", action="store_true", help="Skip benchmark refresh.")
    parser.add_argument("--symbols", default="", help="Comma-separated stock symbols.")
    parser.add_argument("--adjust", default="qfq", help="Price adjustment: none/qfq/hfq.")
    parser.add_argument("--benchmark", default="000300", help="Benchmark index symbol.")
    parser.add_argument("--all-stocks", action="store_true", help="Fetch all stocks from the active source.")
    parser.add_argument("--symbol-offset", type=int, default=0, help="Starting offset for batched symbol refresh.")
    parser.add_argument("--max-symbols", type=int, default=0, help="Optional cap for requested symbols.")
    parser.add_argument("--workers", type=int, default=8, help="Parallel worker count for symbol and industry fetches.")
    return parser.parse_args()


def resolve_run_dates(args: argparse.Namespace, data_cfg: dict) -> None:
    if args.as_of_date:
        strict_dates = strict_run_dates(args.as_of_date, data_cfg)
        if not args.start_date:
            args.start_date = strict_dates["start_date"]
        if not args.end_date:
            args.end_date = strict_dates["as_of_date"]
        if not args.price_start_date:
            args.price_start_date = strict_dates["start_date"]
        if not args.benchmark_start_date:
            args.benchmark_start_date = strict_dates["start_date"]
        if not args.financial_start_date:
            args.financial_start_date = strict_dates["financial_start_date"]
        args.skip_market_caps = True
        args.skip_valuations = True
        args.skip_industry = True
        args.skip_industry_daily = True
        args.skip_industry_members = True
    if not args.start_date or not args.end_date:
        raise DataSourceError("Either --as-of-date or both --start-date/--end-date must be provided.")


def append_dataset(path_like: str, frame: pd.DataFrame, subset: list[str]) -> Path:
    path = resolve_path(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        current = pd.read_parquet(path)
        frame = pd.concat([current, frame], ignore_index=True)
    frame = frame.dropna(subset=[column for column in subset if column in frame.columns]).copy()
    freshness_columns = [column for column in ("date", "report_date", "announcement_date", "as_of_date", "listed_date") if column in frame.columns]
    sort_columns = [*subset, *freshness_columns]
    ascending = [True] * len(subset) + [True] * len(freshness_columns)
    if sort_columns:
        frame = frame.sort_values(sort_columns, ascending=ascending, na_position="first")
    frame = frame.drop_duplicates(subset=subset, keep="last").sort_values(subset).reset_index(drop=True)
    frame.to_parquet(path, index=False)
    return path


def read_dataset(path_like: str) -> pd.DataFrame:
    path = resolve_path(path_like)
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


def load_symbols(args: argparse.Namespace, stock_list: pd.DataFrame) -> list[str]:
    if args.symbols:
        symbols = [item.strip() for item in args.symbols.split(",") if item.strip()]
    elif args.symbols_file:
        symbols = [line.strip() for line in resolve_path(args.symbols_file).read_text(encoding="utf-8").splitlines() if line.strip()]
    else:
        symbols = stock_list["code"].astype(str).tolist() if not stock_list.empty and "code" in stock_list.columns else []
    if args.symbol_offset > 0:
        symbols = symbols[args.symbol_offset :]
    if args.max_symbols > 0:
        symbols = symbols[: args.max_symbols]
    return list(dict.fromkeys(symbols))


def history_window_complete(frame: pd.DataFrame, start_date: str, end_date: str) -> bool:
    if frame.empty or "date" not in frame.columns:
        return False
    dates = pd.to_datetime(frame["date"], errors="coerce").dropna()
    if dates.empty:
        return False
    return dates.min() <= pd.Timestamp(start_date) and dates.max() >= pd.Timestamp(end_date)


def strict_expected_start_date(frame: pd.DataFrame, start_date: str) -> str:
    if frame.empty or "date" not in frame.columns:
        return str(start_date)
    dates = pd.to_datetime(frame["date"], errors="coerce").dropna()
    dates = dates[dates >= pd.Timestamp(start_date)]
    dates = dates[dates.dt.weekday < 5]
    if dates.empty:
        return str(start_date)
    return str(dates.min().strftime("%Y-%m-%d"))


def strict_price_expected_start(frame: pd.DataFrame, start_date: str) -> str:
    normalized = clean_price_frame(frame)
    return strict_expected_start_date(normalized, start_date)


def dataset_min_timestamp(frame: pd.DataFrame, date_column: str) -> pd.Timestamp | None:
    if frame.empty or date_column not in frame.columns:
        return None
    dates = pd.to_datetime(frame[date_column], errors="coerce").dropna()
    if dates.empty:
        return None
    return pd.Timestamp(dates.min())


def needs_history_backfill(frame: pd.DataFrame, requested_start_date: str, date_column: str) -> bool:
    if not requested_start_date:
        return False
    earliest = dataset_min_timestamp(frame, date_column)
    if earliest is None:
        return True
    return pd.Timestamp(requested_start_date) < earliest


def strict_price_history_gaps(
    frame: pd.DataFrame,
    symbols: list[str],
    start_date: str,
    end_date: str,
    stock_list: pd.DataFrame | None = None,
    expected_start_date: str | None = None,
) -> dict[str, object]:
    normalized = clean_price_frame(frame)
    expected_start = strict_price_expected_start(normalized, start_date) if expected_start_date is None else str(pd.Timestamp(expected_start_date).strftime("%Y-%m-%d"))
    stats = (
        normalized.groupby("code")["date"].agg(["min", "max", "count"]).reset_index()
        if not normalized.empty
        else pd.DataFrame(columns=["code", "min", "max", "count"])
    )
    stats_map = {str(row["code"]): row for row in stats.to_dict(orient="records")}
    listed_map: dict[str, pd.Timestamp | None] = {}
    if stock_list is not None and not stock_list.empty and "listed_date" in stock_list.columns:
        listed = stock_list[["code", "listed_date"]].drop_duplicates(subset=["code"]).copy()
        listed["code"] = listed["code"].astype(str)
        listed["listed_date"] = pd.to_datetime(listed["listed_date"], errors="coerce")
        listed_map = listed.set_index("code")["listed_date"].to_dict()

    expected_start_ts = pd.Timestamp(expected_start)
    end_ts = pd.Timestamp(end_date)
    missing: list[dict[str, object]] = []
    for symbol in list(dict.fromkeys(symbols)):
        row = stats_map.get(str(symbol))
        listed_date = listed_map.get(str(symbol))
        issues: list[str] = []
        min_date = ""
        max_date = ""
        count = 0
        requires_full_window = listed_date is pd.NaT or listed_date is None or pd.isna(listed_date) or listed_date <= expected_start_ts
        if row is None:
            issues.append("missing_symbol_history")
        else:
            min_date = str(row["min"])
            max_date = str(row["max"])
            count = int(row["count"])
            if requires_full_window and pd.Timestamp(min_date) > expected_start_ts:
                issues.append("history_starts_after_expected")
            if pd.Timestamp(max_date) < end_ts:
                issues.append("missing_as_of_date")
        if not issues:
            continue
        missing.append(
            {
                "symbol": str(symbol),
                "listed_date": listed_date.strftime("%Y-%m-%d") if isinstance(listed_date, pd.Timestamp) and not pd.isna(listed_date) else None,
                "min_date": min_date or None,
                "max_date": max_date or None,
                "row_count": count,
                "issues": issues,
            }
        )
    return {
        "requested_start_date": str(start_date),
        "expected_start_date": expected_start,
        "requested_end_date": str(end_date),
        "missing_symbols": [item["symbol"] for item in missing],
        "missing_count": len(missing),
        "details": missing,
    }


def strict_price_history_complete(
    frame: pd.DataFrame,
    symbols: list[str],
    start_date: str,
    end_date: str,
    stock_list: pd.DataFrame | None = None,
) -> bool:
    report = strict_price_history_gaps(frame, symbols, start_date, end_date, stock_list=stock_list)
    return int(report["missing_count"]) == 0


def strict_price_symbol_complete(
    frame: pd.DataFrame,
    symbol: str,
    start_date: str,
    end_date: str,
    stock_list: pd.DataFrame | None = None,
    expected_start_date: str | None = None,
) -> bool:
    symbol_stock_list = pd.DataFrame()
    if stock_list is not None and not stock_list.empty and "code" in stock_list.columns:
        symbol_stock_list = stock_list.loc[stock_list["code"].astype(str) == str(symbol)].copy()
    report = strict_price_history_gaps(
        frame,
        [symbol],
        start_date,
        end_date,
        stock_list=symbol_stock_list,
        expected_start_date=expected_start_date,
    )
    return int(report["missing_count"]) == 0


def summarize_price_gap_report(report: dict[str, object]) -> dict[str, object]:
    details = list(report.get("details", []))
    category_counts: dict[str, int] = {}
    start_distribution: dict[str, int] = {}
    for item in details:
        for issue in item.get("issues", []):
            category_counts[issue] = category_counts.get(issue, 0) + 1
        min_date = item.get("min_date")
        if min_date:
            start_distribution[str(min_date)] = start_distribution.get(str(min_date), 0) + 1
    ordered_distribution = dict(sorted(start_distribution.items(), key=lambda entry: (-entry[1], entry[0]))[:20])
    return {
        "requested_start_date": report.get("requested_start_date"),
        "expected_start_date": report.get("expected_start_date"),
        "requested_end_date": report.get("requested_end_date"),
        "missing_count": int(report.get("missing_count", 0)),
        "missing_symbols": list(report.get("missing_symbols", [])),
        "category_counts": category_counts,
        "start_date_distribution_top": ordered_distribution,
        "sample_details": details[:200],
    }


def write_strict_price_gap_report(as_of_date: str, before: dict[str, object], after: dict[str, object], output_dir: str | Path) -> None:
    output_root = resolve_path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    payload = {
        "name": "price_history_gaps",
        "as_of_date": as_of_date,
        "before": summarize_price_gap_report(before),
        "after": summarize_price_gap_report(after),
    }
    json_path = output_root / f"price_history_gaps_{as_of_date}.json"
    write_json_report(json_path, payload)

    before_summary = payload["before"]
    after_summary = payload["after"]
    lines = [
        f"# Price History Gaps ({as_of_date})",
        "",
        "## Before Backfill",
        "",
        f"- requested_start_date: `{before_summary['requested_start_date']}`",
        f"- expected_start_date: `{before_summary['expected_start_date']}`",
        f"- requested_end_date: `{before_summary['requested_end_date']}`",
        f"- missing_count: `{before_summary['missing_count']}`",
        f"- category_counts: `{json.dumps(before_summary['category_counts'], ensure_ascii=False, sort_keys=True)}`",
        f"- start_date_distribution_top: `{json.dumps(before_summary['start_date_distribution_top'], ensure_ascii=False, sort_keys=True)}`",
        "",
        "## After Backfill",
        "",
        f"- requested_start_date: `{after_summary['requested_start_date']}`",
        f"- expected_start_date: `{after_summary['expected_start_date']}`",
        f"- requested_end_date: `{after_summary['requested_end_date']}`",
        f"- missing_count: `{after_summary['missing_count']}`",
        f"- category_counts: `{json.dumps(after_summary['category_counts'], ensure_ascii=False, sort_keys=True)}`",
        f"- start_date_distribution_top: `{json.dumps(after_summary['start_date_distribution_top'], ensure_ascii=False, sort_keys=True)}`",
        "",
    ]
    if after_summary["missing_symbols"]:
        lines.extend(["## Remaining Symbols", ""])
        for symbol in after_summary["missing_symbols"][:200]:
            lines.append(f"- {symbol}")
        lines.append("")
    md_path = output_root / f"price_history_gaps_{as_of_date}.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")


def price_frame_has_as_of(frame: pd.DataFrame, symbol: str, end_date: str) -> bool:
    normalized = clean_price_frame(frame)
    if normalized.empty:
        return False
    return not normalized.loc[
        (normalized["code"].astype(str) == str(symbol)) & (normalized["date"].astype(str) == str(end_date))
    ].empty


def strict_financial_history_complete(frame: pd.DataFrame, symbols: list[str], start_date: str, end_date: str) -> bool:
    report = strict_financial_history_gaps(frame, symbols, start_date, end_date, end_date)
    return blocking_financial_gap_count(report) == 0


def required_financial_report_date(as_of_date: str) -> str:
    current = pd.Timestamp(as_of_date)
    if current.month <= 4:
        return f"{current.year - 1}-09-30"
    if current.month <= 8:
        return f"{current.year - 1}-12-31"
    if current.month <= 10:
        return f"{current.year}-06-30"
    return f"{current.year}-09-30"


def dividend_report_dates(start_date: str, end_date: str) -> list[str]:
    start_ts = pd.Timestamp(start_date)
    end_ts = pd.Timestamp(end_date)
    report_dates: list[str] = []
    for year in range(start_ts.year - 2, end_ts.year + 1):
        for month, day in ((6, 30), (12, 31)):
            report_ts = pd.Timestamp(year=year, month=month, day=day)
            if report_ts <= end_ts:
                report_dates.append(report_ts.strftime("%Y-%m-%d"))
    return sorted(report_dates)


def strict_financial_history_gaps(
    frame: pd.DataFrame,
    symbols: list[str],
    start_date: str,
    end_date: str,
    as_of_date: str,
) -> dict[str, object]:
    if frame.empty or "code" not in frame.columns or "report_date" not in frame.columns:
        return {
            "requested_start_date": str(start_date),
            "requested_end_date": str(end_date),
            "as_of_date": str(as_of_date),
            "required_report_date": required_financial_report_date(as_of_date),
            "missing_symbols": list(dict.fromkeys(symbols)),
            "missing_count": len(list(dict.fromkeys(symbols))),
            "details": [{"symbol": str(symbol), "issues": ["missing_financial_history"]} for symbol in list(dict.fromkeys(symbols))],
        }

    financials = frame.copy()
    financials["code"] = financials["code"].astype(str)
    financials["report_date"] = pd.to_datetime(financials["report_date"], errors="coerce")
    if "announcement_date" in financials.columns:
        financials["announcement_date"] = pd.to_datetime(financials["announcement_date"], errors="coerce")
    else:
        financials["announcement_date"] = pd.NaT
    financials = financials.dropna(subset=["code", "report_date"])
    financials = financials[
        (financials["report_date"] >= pd.Timestamp(start_date)) & (financials["report_date"] <= pd.Timestamp(end_date))
    ].copy()
    required_report = pd.Timestamp(required_financial_report_date(as_of_date))
    required_fields = ("roe", "net_profit", "cfo", "debt_to_assets", "equity")

    missing: list[dict[str, object]] = []
    for symbol in list(dict.fromkeys(symbols)):
        subset = financials.loc[financials["code"] == str(symbol)].sort_values(["report_date", "announcement_date"])
        issues: list[str] = []
        latest_report_date = None
        latest_announcement_date = None
        if subset.empty:
            issues.append("missing_financial_history")
        else:
            latest = subset.iloc[-1]
            latest_report_ts = pd.to_datetime(latest["report_date"], errors="coerce")
            latest_report_date = latest_report_ts.strftime("%Y-%m-%d") if pd.notna(latest_report_ts) else None
            latest_announce_ts = pd.to_datetime(latest.get("announcement_date"), errors="coerce")
            latest_announcement_date = latest_announce_ts.strftime("%Y-%m-%d") if pd.notna(latest_announce_ts) else None
            if pd.isna(latest_report_ts) or latest_report_ts < required_report:
                issues.append("latest_report_before_required")
            for field in required_fields:
                if field not in subset.columns or pd.isna(latest.get(field)):
                    issues.append(f"{field}_missing_on_latest")
        if issues:
            missing.append(
                {
                    "symbol": str(symbol),
                    "latest_report_date": latest_report_date,
                    "latest_announcement_date": latest_announcement_date,
                    "issues": issues,
                }
            )
    return {
        "requested_start_date": str(start_date),
        "requested_end_date": str(end_date),
        "as_of_date": str(as_of_date),
        "required_report_date": required_report.strftime("%Y-%m-%d"),
        "missing_symbols": [item["symbol"] for item in missing],
        "missing_count": len(missing),
        "details": missing,
    }


def summarize_financial_gap_report(report: dict[str, object]) -> dict[str, object]:
    details = list(report.get("details", []))
    category_counts: dict[str, int] = {}
    latest_report_distribution: dict[str, int] = {}
    for item in details:
        for issue in item.get("issues", []):
            category_counts[issue] = category_counts.get(issue, 0) + 1
        latest_report_date = item.get("latest_report_date")
        if latest_report_date:
            latest_report_distribution[str(latest_report_date)] = latest_report_distribution.get(str(latest_report_date), 0) + 1
    ordered_distribution = dict(sorted(latest_report_distribution.items(), key=lambda entry: (-entry[1], entry[0]))[:20])
    return {
        "requested_start_date": report.get("requested_start_date"),
        "requested_end_date": report.get("requested_end_date"),
        "as_of_date": report.get("as_of_date"),
        "required_report_date": report.get("required_report_date"),
        "missing_count": int(report.get("missing_count", 0)),
        "missing_symbols": list(report.get("missing_symbols", [])),
        "blocking_count": blocking_financial_gap_count(report),
        "blocking_symbols": blocking_financial_gap_symbols(report),
        "category_counts": category_counts,
        "latest_report_distribution_top": ordered_distribution,
        "sample_details": details[:200],
    }


def blocking_financial_gap_symbols(report: dict[str, object]) -> list[str]:
    symbols: list[str] = []
    for item in list(report.get("details", [])):
        issues = set(item.get("issues", []))
        if not issues:
            continue
        if issues - NON_BLOCKING_FINANCIAL_ISSUES:
            symbols.append(str(item["symbol"]))
    return symbols


def blocking_financial_gap_count(report: dict[str, object]) -> int:
    return len(blocking_financial_gap_symbols(report))


def write_strict_financial_gap_report(as_of_date: str, before: dict[str, object], after: dict[str, object], output_dir: str | Path) -> None:
    output_root = resolve_path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    payload = {
        "name": "financial_history_gaps",
        "as_of_date": as_of_date,
        "before": summarize_financial_gap_report(before),
        "after": summarize_financial_gap_report(after),
    }
    json_path = output_root / f"financial_history_gaps_{as_of_date}.json"
    write_json_report(json_path, payload)

    before_summary = payload["before"]
    after_summary = payload["after"]
    lines = [
        f"# Financial History Gaps ({as_of_date})",
        "",
        "## Before Refresh",
        "",
        f"- required_report_date: `{before_summary['required_report_date']}`",
        f"- missing_count: `{before_summary['missing_count']}`",
        f"- blocking_count: `{before_summary['blocking_count']}`",
        f"- category_counts: `{json.dumps(before_summary['category_counts'], ensure_ascii=False, sort_keys=True)}`",
        f"- latest_report_distribution_top: `{json.dumps(before_summary['latest_report_distribution_top'], ensure_ascii=False, sort_keys=True)}`",
        "",
        "## After Refresh",
        "",
        f"- required_report_date: `{after_summary['required_report_date']}`",
        f"- missing_count: `{after_summary['missing_count']}`",
        f"- blocking_count: `{after_summary['blocking_count']}`",
        f"- category_counts: `{json.dumps(after_summary['category_counts'], ensure_ascii=False, sort_keys=True)}`",
        f"- latest_report_distribution_top: `{json.dumps(after_summary['latest_report_distribution_top'], ensure_ascii=False, sort_keys=True)}`",
        "",
    ]
    if after_summary["blocking_symbols"]:
        lines.extend(["## Remaining Blocking Symbols", ""])
        for symbol in after_summary["blocking_symbols"][:200]:
            lines.append(f"- {symbol}")
        lines.append("")
    md_path = output_root / f"financial_history_gaps_{as_of_date}.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")


def parallel_frames(
    items: list[object],
    worker_count: int,
    fetcher,
    warning_prefix: str,
) -> tuple[list[pd.DataFrame], list[dict[str, object]]]:
    frames: list[pd.DataFrame] = []
    provider_entries: list[dict[str, object]] = []
    if not items:
        return frames, provider_entries
    with ThreadPoolExecutor(max_workers=max(1, worker_count)) as executor:
        future_map = {executor.submit(fetcher, item): item for item in items}
        for future in as_completed(future_map):
            item = future_map[future]
            try:
                frame, entry = future.result()
            except Exception as exc:  # pragma: no cover - exercised in live runs
                print(f"[warn] {warning_prefix} failed for {item}: {exc}", file=sys.stderr)
                provider_entries.append(
                    {"method": warning_prefix, "adapter": "parallel", "success": False, "error": str(exc), "attempt_index": 1}
                )
                continue
            provider_entries.append(entry)
            if frame is not None and not frame.empty:
                frames.append(frame)
    return frames, provider_entries


def discover_industries(data_cfg: dict) -> pd.DataFrame:
    ak = AkshareAdapter(data_cfg)
    frames: list[pd.DataFrame] = []
    for fn_name, level in (
        ("sw_index_first_info", "first"),
        ("sw_index_second_info", "second"),
        ("sw_index_third_info", "third"),
    ):
        try:
            frame = ak._invoke(fn_name)  # noqa: SLF001 - internal helper is acceptable in this repo script
        except Exception:
            continue
        if frame.empty:
            continue
        frame = frame.rename(columns={"行业代码": "industry_code", "行业名称": "industry_name", "指数代码": "industry_code", "指数名称": "industry_name"})
        if {"industry_code", "industry_name"} <= set(frame.columns):
            frame["level"] = level
            frames.append(frame[["industry_code", "industry_name", "level"]].drop_duplicates())
    if not frames:
        raise DataSourceError("Unable to discover SW industry catalog from AkShare.")
    return pd.concat(frames, ignore_index=True).drop_duplicates(subset=["industry_code"])


def normalize_industry_level(value: object) -> str:
    mapping = {
        "first": "first",
        "一级行业": "first",
        "一级": "first",
        "申万一级": "first",
        "second": "second",
        "二级行业": "second",
        "二级": "second",
        "申万二级": "second",
        "third": "third",
        "三级行业": "third",
        "三级": "third",
        "申万三级": "third",
    }
    return mapping.get(str(value).strip(), str(value).strip())


def build_industry_code_reference(existing_members: pd.DataFrame, existing_daily: pd.DataFrame) -> dict[tuple[str, str], str]:
    mapping: dict[tuple[str, str], str] = {}
    frames: list[pd.DataFrame] = []
    if not existing_members.empty and {"industry_name", "industry_code"} <= set(existing_members.columns):
        members = existing_members[["industry_name", "industry_code"]].copy()
        members["industry_level"] = existing_members.get("industry_level", "")
        frames.append(members)
    if not existing_daily.empty and {"industry_name", "industry_code"} <= set(existing_daily.columns):
        daily = existing_daily[["industry_name", "industry_code"]].copy()
        daily["industry_level"] = existing_daily.get("industry_level", "")
        frames.append(daily)
    if not frames:
        return mapping
    combined = pd.concat(frames, ignore_index=True)
    combined["industry_name"] = combined["industry_name"].astype(str).str.strip()
    combined["industry_code"] = combined["industry_code"].astype(str).str.replace(".SI", "", regex=False)
    combined["industry_level"] = combined["industry_level"].map(normalize_industry_level)
    combined = combined.dropna(subset=["industry_name", "industry_code"])
    for row in combined.itertuples(index=False):
        mapping[(str(row.industry_name), str(row.industry_level))] = str(row.industry_code)
        mapping.setdefault((str(row.industry_name), ""), str(row.industry_code))
    return mapping


def main() -> int:
    args = parse_args()
    configs = load_project_configs()
    data_cfg = configs["data_sources"]
    resolve_run_dates(args, data_cfg)
    if data_cfg.get("cache", {}).get("clear_on_run", False):
        clear_directories(configured_cache_directories(data_cfg))
    adapter = create_default_adapter(data_cfg)
    provider_entries: list[dict[str, object]] = []
    strict_mode = bool(args.as_of_date)
    existing_prices = read_dataset(RAW_FILES["price_daily"])
    existing_benchmark = read_dataset(RAW_FILES["benchmark_daily"])
    existing_financials = read_dataset(RAW_FILES["financials"])

    if args.skip_stock_list:
        stock_list = read_dataset(RAW_FILES["stock_list"])
    else:
        if strict_mode:
            try:
                stock_list = fetch_pytdx_stock_list(data_cfg, args.end_date)
                provider_entries.append(
                    {"method": "get_stock_list", "adapter": "pytdx", "success": True, "error": None, "attempt_index": 1, "rows": int(len(stock_list))}
                )
            except Exception as exc:
                provider_entries.append(
                    {"method": "get_stock_list", "adapter": "pytdx", "success": False, "error": str(exc), "attempt_index": 1}
                )
                try:
                    stock_list = adapter.get_stock_list(args.end_date)
                except Exception:
                    stock_list = read_dataset(RAW_FILES["stock_list"])
                    if stock_list.empty:
                        raise
                else:
                    provider_entries.extend(adapter.call_history)
        else:
            stock_list = adapter.get_stock_list(args.end_date)
        if strict_mode:
            stock_list = (
                stock_list.dropna(subset=["code"])
                .drop_duplicates(subset=["code"], keep="last")
                .sort_values(["code"])
                .reset_index(drop=True)
            )
            stock_list_path = resolve_path(RAW_FILES["stock_list"])
            stock_list_path.parent.mkdir(parents=True, exist_ok=True)
            stock_list.to_parquet(stock_list_path, index=False)
        else:
            append_dataset(RAW_FILES["stock_list"], stock_list, ["code"])

    symbols = load_symbols(args, stock_list)
    needs_symbol_scope = not all(
        [
            args.skip_prices,
            args.skip_financials,
            args.skip_st_flags,
            args.skip_market_caps,
            args.skip_valuations,
        ]
    )
    if needs_symbol_scope and not symbols:
        raise DataSourceError("No symbols selected for symbol-bound market data refresh.")
    price_start_date = args.price_start_date or args.start_date
    benchmark_start_date = args.benchmark_start_date or args.start_date
    industry_start_date = args.industry_start_date or args.start_date
    financial_start_date = args.financial_start_date or args.start_date
    price_history_backfill_mode = not strict_mode and needs_history_backfill(existing_prices, price_start_date, "date")
    benchmark_history_backfill_mode = not strict_mode and needs_history_backfill(existing_benchmark, benchmark_start_date, "date")

    if not args.skip_benchmark:
        existing_benchmark_clean = clean_benchmark_frame(existing_benchmark)
        expected_benchmark_start = strict_expected_start_date(existing_benchmark_clean, benchmark_start_date)
        use_direct_benchmark_backfill = strict_mode or benchmark_history_backfill_mode
        if use_direct_benchmark_backfill and not benchmark_history_backfill_mode and history_window_complete(
            existing_benchmark_clean,
            expected_benchmark_start,
            args.end_date,
        ):
            benchmark = existing_benchmark_clean
            resolve_path(RAW_FILES["benchmark_daily"]).parent.mkdir(parents=True, exist_ok=True)
            benchmark.to_parquet(resolve_path(RAW_FILES["benchmark_daily"]), index=False)
            provider_entries.append(
                {"method": "get_index_daily", "adapter": "existing_raw", "success": True, "error": None, "attempt_index": 1, "rows": int(len(benchmark))}
            )
        else:
            try:
                benchmark = (
                    fetch_benchmark_daily(data_cfg, args.benchmark, benchmark_start_date, args.end_date)
                    if use_direct_benchmark_backfill
                    else adapter.get_index_daily(args.benchmark, benchmark_start_date, args.end_date)
                )
            except DataSourceError as exc:
                if use_direct_benchmark_backfill:
                    raise
                print(
                    f"[warn] benchmark download failed for {args.benchmark}: {exc}. "
                    "Continuing with stock data refresh; backtests should provide a local benchmark fallback.",
                    file=sys.stderr,
                )
                provider_entries.append(
                    {
                        "method": "get_index_daily",
                        "adapter": "strict_price" if strict_mode else "composite",
                        "success": False,
                        "error": str(exc),
                        "attempt_index": 0,
                    }
                )
            else:
                benchmark = clean_benchmark_frame(pd.concat([existing_benchmark, benchmark], ignore_index=True))
                benchmark_path = resolve_path(RAW_FILES["benchmark_daily"])
                benchmark_path.parent.mkdir(parents=True, exist_ok=True)
                benchmark.to_parquet(benchmark_path, index=False)

    if not args.skip_prices:
        use_direct_price_backfill = strict_mode or price_history_backfill_mode
        expected_price_start = ""
        if price_history_backfill_mode:
            benchmark_for_expected_start = read_dataset(RAW_FILES["benchmark_daily"])
            expected_price_start = strict_expected_start_date(clean_benchmark_frame(benchmark_for_expected_start), price_start_date)
        price_gaps_before = strict_price_history_gaps(
            existing_prices,
            symbols,
            price_start_date,
            args.end_date,
            stock_list=stock_list,
            expected_start_date=expected_price_start or None,
        )
        has_existing_coverage = int(price_gaps_before["missing_count"]) == 0 and not price_history_backfill_mode
        expected_price_start = str(price_gaps_before["expected_start_date"])
        if not expected_price_start or expected_price_start == str(price_start_date):
            benchmark_for_expected_start = read_dataset(RAW_FILES["benchmark_daily"])
            expected_price_start = strict_expected_start_date(clean_benchmark_frame(benchmark_for_expected_start), price_start_date)
        if use_direct_price_backfill and has_existing_coverage:
            prices = clean_price_frame(existing_prices)
            resolve_path(RAW_FILES["price_daily"]).parent.mkdir(parents=True, exist_ok=True)
            prices.to_parquet(resolve_path(RAW_FILES["price_daily"]), index=False)
            provider_entries.append(
                {"method": "get_price_daily", "adapter": "existing_raw", "success": True, "error": None, "attempt_index": 1, "rows": int(len(prices))}
            )
        else:
            price_symbols = (
                list(price_gaps_before["missing_symbols"])
                if use_direct_price_backfill and not has_existing_coverage and not existing_prices.empty
                else symbols
            )
            tdx_dir = first_existing_tdx_dir(data_cfg) if use_direct_price_backfill else None

            def fetch_price(symbol: str):
                if use_direct_price_backfill:
                    if tdx_dir is not None:
                        frame = fetch_tdx_local_prices(tdx_dir, [symbol], price_start_date, args.end_date)
                        adapter_name = "mootdx"
                        if not strict_price_symbol_complete(
                            frame,
                            symbol,
                            price_start_date,
                            args.end_date,
                            stock_list=stock_list,
                            expected_start_date=expected_price_start,
                        ):
                            raise DataSourceError(
                                f"Local TDX price history incomplete for {symbol}: missing strict window {price_start_date} -> {args.end_date}."
                            )
                    else:
                        try:
                            frame = fetch_akshare_tx_prices([symbol], price_start_date, args.end_date, args.adjust)
                            adapter_name = "akshare_tx"
                            if not price_frame_has_as_of(frame, symbol, args.end_date):
                                raise DataSourceError(
                                    f"AkShare TX price history stale for {symbol}: missing {args.end_date}."
                                )
                            if not strict_price_symbol_complete(
                                frame,
                                symbol,
                                price_start_date,
                                args.end_date,
                                stock_list=stock_list,
                                expected_start_date=expected_price_start,
                            ):
                                raise DataSourceError(
                                    f"AkShare TX price history incomplete for {symbol}: missing strict window {price_start_date} -> {args.end_date}."
                                )
                        except Exception:
                            with STRICT_BAOSTOCK_LOCK:
                                frame = BaoStockAdapter(data_cfg).get_price_daily([symbol], price_start_date, args.end_date, args.adjust)
                            adapter_name = "baostock"
                            if not strict_price_symbol_complete(
                                frame,
                                symbol,
                                price_start_date,
                                args.end_date,
                                stock_list=stock_list,
                                expected_start_date=expected_price_start,
                            ):
                                raise DataSourceError(
                                    f"BaoStock price history incomplete for {symbol}: missing strict window {price_start_date} -> {args.end_date}."
                                )
                else:
                    frame = create_default_adapter(data_cfg).get_price_daily([symbol], price_start_date, args.end_date, args.adjust)
                    adapter_name = "parallel_composite"
                return frame, {
                    "method": "get_price_daily",
                    "adapter": adapter_name,
                    "success": True,
                    "error": None,
                    "attempt_index": 1,
                    "rows": int(len(frame)),
                    "symbol": symbol,
                }

            price_frames, price_entries = parallel_frames(price_symbols, args.workers, fetch_price, "price download")
            provider_entries.extend(price_entries)
            if not price_frames:
                raise DataSourceError("Price download failed for all selected symbols.")
            prices = clean_price_frame(pd.concat(price_frames, ignore_index=True))
            append_dataset(RAW_FILES["price_daily"], prices, ["code", "date"])
            if use_direct_price_backfill:
                updated_prices = read_dataset(RAW_FILES["price_daily"])
                price_gaps_after = strict_price_history_gaps(updated_prices, symbols, price_start_date, args.end_date, stock_list=stock_list)
                write_strict_price_gap_report(
                    args.as_of_date or args.end_date,
                    price_gaps_before,
                    price_gaps_after,
                    data_cfg.get("strict_run", {}).get("blocker_dir", "reports/strict"),
                )
                if int(price_gaps_after["missing_count"]) > 0:
                    missing_symbols = list(price_gaps_after["missing_symbols"])
                    raise DataSourceError(
                        f"Strict price refresh incomplete for {len(missing_symbols)} symbols on {args.end_date}: {missing_symbols[:20]}"
                    )
        if use_direct_price_backfill and has_existing_coverage:
            write_strict_price_gap_report(
                args.as_of_date or args.end_date,
                price_gaps_before,
                price_gaps_before,
                data_cfg.get("strict_run", {}).get("blocker_dir", "reports/strict"),
            )
    calendar_prices = read_dataset(RAW_FILES["price_daily"])
    trade_calendar = build_trade_calendar(calendar_prices)
    if trade_calendar.empty:
        raise DataSourceError("Unable to derive trade calendar from price_daily.")
    trade_calendar_path = resolve_path("data/curated/trade_calendar.parquet")
    trade_calendar_path.parent.mkdir(parents=True, exist_ok=True)
    trade_calendar.to_parquet(trade_calendar_path, index=False)

    if not args.skip_st_flags:
        st_flags = adapter.get_st_flags(symbols, args.end_date)
        append_dataset(RAW_FILES["st_flags"], st_flags, ["code", "date"])

    if not args.skip_market_caps:
        market_caps = adapter.get_market_caps(symbols, args.end_date)
        append_dataset(RAW_FILES["market_caps"], market_caps, ["code", "date"])

    if not args.skip_financials:
        financial_gaps_before = strict_financial_history_gaps(
            existing_financials,
            symbols,
            financial_start_date,
            args.end_date,
            args.end_date,
        )
        has_existing_financial_coverage = blocking_financial_gap_count(financial_gaps_before) == 0
        if strict_mode and has_existing_financial_coverage:
            financials = existing_financials.copy()
            resolve_path(RAW_FILES["financials"]).parent.mkdir(parents=True, exist_ok=True)
            financials.to_parquet(resolve_path(RAW_FILES["financials"]), index=False)
            provider_entries.append(
                {"method": "get_financials", "adapter": "existing_raw", "success": True, "error": None, "attempt_index": 1, "rows": int(len(financials))}
            )
        else:
            financial_symbols = (
                list(financial_gaps_before["missing_symbols"])
                if strict_mode and not has_existing_financial_coverage and not existing_financials.empty
                else symbols
            )

            def fetch_financial(symbol: str):
                if strict_mode:
                    try:
                        frame = create_default_adapter(data_cfg).get_financials(symbol, start_date=financial_start_date, end_date=args.end_date)
                        adapter_name = "strict_composite"
                    except Exception:
                        frame = fetch_financials_safe(data_cfg, symbol, financial_start_date, args.end_date)
                        adapter_name = "strict_financial_subprocess"
                else:
                    frame = create_default_adapter(data_cfg).get_financials(symbol, start_date=financial_start_date, end_date=args.end_date)
                    adapter_name = "parallel_composite"
                frame["code"] = symbol
                return frame, {
                    "method": "get_financials",
                    "adapter": adapter_name,
                    "success": True,
                    "error": None,
                    "attempt_index": 1,
                    "rows": int(len(frame)),
                    "symbol": symbol,
                }

            financial_frames, financial_entries = parallel_frames(financial_symbols, args.workers, fetch_financial, "financial download")
            provider_entries.extend(financial_entries)
            if financial_frames:
                financials = pd.concat(financial_frames, ignore_index=True)
                append_dataset(RAW_FILES["financials"], financials, ["code", "report_date"])
                if strict_mode:
                    updated_financials = read_dataset(RAW_FILES["financials"])
                    financial_gaps_after = strict_financial_history_gaps(
                        updated_financials,
                        symbols,
                        financial_start_date,
                        args.end_date,
                        args.end_date,
                    )
                    write_strict_financial_gap_report(
                        args.as_of_date,
                        financial_gaps_before,
                        financial_gaps_after,
                        data_cfg.get("strict_run", {}).get("blocker_dir", "reports/strict"),
                    )
                    missing_symbols = blocking_financial_gap_symbols(financial_gaps_after)
                    if missing_symbols:
                        raise DataSourceError(
                            f"Strict financial refresh incomplete for {len(missing_symbols)} symbols on {args.end_date}: {missing_symbols[:20]}"
                        )
            else:
                print("[warn] financial download failed for all selected symbols.", file=sys.stderr)
        if strict_mode and has_existing_financial_coverage:
            write_strict_financial_gap_report(
                args.as_of_date,
                financial_gaps_before,
                financial_gaps_before,
                data_cfg.get("strict_run", {}).get("blocker_dir", "reports/strict"),
            )

    if not args.skip_dividends:
        dividend_adapter = AkshareAdapter(data_cfg)
        dividend_frames: list[pd.DataFrame] = []
        for report_date in dividend_report_dates(financial_start_date, args.end_date):
            try:
                frame = dividend_adapter.get_dividend_events(report_date)
            except Exception as exc:
                provider_entries.append(
                    {
                        "method": "get_dividend_events",
                        "adapter": "akshare",
                        "success": False,
                        "error": str(exc),
                        "attempt_index": 1,
                        "report_date": report_date,
                    }
                )
                continue
            dividend_frames.append(frame)
            provider_entries.append(
                {
                    "method": "get_dividend_events",
                    "adapter": "akshare",
                    "success": True,
                    "error": None,
                    "attempt_index": 1,
                    "rows": int(len(frame)),
                    "report_date": report_date,
                }
            )
        if dividend_frames:
            dividend_events = pd.concat(dividend_frames, ignore_index=True)
            append_dataset(RAW_FILES["dividend_events"], dividend_events, ["code", "report_date"])
        else:
            print("[warn] dividend event refresh failed for all requested report dates.", file=sys.stderr)

    if not args.skip_industry and not args.skip_industry_members:
        existing_industry_members = read_dataset(RAW_FILES["industry_members"])
        existing_industry_daily = read_dataset(RAW_FILES["industry_daily"])
        industry_code_reference = build_industry_code_reference(existing_industry_members, existing_industry_daily)
        stock_name_map: dict[str, str] = {}
        if not stock_list.empty and {"code", "name"} <= set(stock_list.columns):
            stock_name_map = (
                stock_list[["code", "name"]]
                .drop_duplicates(subset=["code"])
                .set_index("code")["name"]
                .astype(str)
                .to_dict()
            )
        industry_symbols = symbols or stock_list.get("code", pd.Series(dtype=str)).astype(str).tolist()
        member_frames: list[pd.DataFrame] = []
        if not args.prefer_symbol_industry_fallback:
            try:
                industry_catalog = discover_industries(data_cfg)
                provider_entries.append(
                    {
                        "method": "discover_industries",
                        "adapter": "akshare",
                        "success": True,
                        "error": None,
                        "attempt_index": 1,
                        "rows": int(len(industry_catalog)),
                    }
                )

                industry_meta = industry_catalog.set_index("industry_code")[["industry_name", "level"]].to_dict(orient="index")

                def fetch_members(industry_code: str):
                    local_adapter = create_default_adapter(data_cfg)
                    frame = local_adapter.get_industry_members(industry_code, as_of_date=args.end_date)
                    matched = industry_meta[str(industry_code)]
                    frame["industry_name"] = matched["industry_name"]
                    frame["industry_level"] = matched["level"]
                    return frame, {
                        "method": "get_industry_members",
                        "adapter": "parallel_composite",
                        "success": True,
                        "error": None,
                        "attempt_index": 1,
                        "rows": int(len(frame)),
                        "industry_code": str(industry_code),
                    }

                member_frames, member_entries = parallel_frames(
                    industry_catalog["industry_code"].astype(str).tolist(),
                    args.workers,
                    fetch_members,
                    "industry member download",
                )
                provider_entries.extend(member_entries)
            except DataSourceError as exc:
                provider_entries.append(
                    {"method": "get_industry_members", "adapter": "akshare", "success": False, "error": str(exc), "attempt_index": 1}
                )
                member_frames = []

        if not member_frames and industry_symbols:
            print("[warn] industry member catalog/source unavailable; falling back to AData symbol industry mapping.", file=sys.stderr)

            def fetch_symbol_industry(symbol: str):
                local_adapter = ADataAdapter(data_cfg)
                frame = local_adapter.get_symbol_industries(symbol, as_of_date=args.end_date)
                frame["name"] = stock_name_map.get(symbol, symbol)
                frame["industry_level"] = frame["industry_level"].map(normalize_industry_level)
                frame["industry_code"] = [
                    industry_code_reference.get((str(name), str(level)))
                    or industry_code_reference.get((str(name), ""))
                    or str(code).replace(".SI", "")
                    for name, level, code in zip(frame["industry_name"], frame["industry_level"], frame["industry_code"], strict=False)
                ]
                return frame[["industry_code", "code", "name", "industry_name", "industry_level", "as_of_date"]], {
                    "method": "get_symbol_industries",
                    "adapter": "adata",
                    "success": True,
                    "error": None,
                    "attempt_index": 1,
                    "rows": int(len(frame)),
                    "symbol": symbol,
                }

            member_frames, member_entries = parallel_frames(
                industry_symbols,
                args.workers,
                fetch_symbol_industry,
                "symbol industry mapping",
            )
            provider_entries.extend(member_entries)

        if member_frames:
            industry_members = pd.concat(member_frames, ignore_index=True)
            append_dataset(RAW_FILES["industry_members"], industry_members, ["industry_code", "code"])
        else:
            print("[warn] industry member refresh failed for all selected symbols.", file=sys.stderr)

    if not args.skip_industry and not args.skip_industry_daily:
        try:
            industry_daily_frames: list[pd.DataFrame] = []
            for level_label, level_value in (("first", "一级行业"), ("second", "二级行业"), ("third", "三级行业")):
                frame = adapter.get_industry_daily(industry_start_date, args.end_date, level=level_value)
                frame["industry_level"] = level_label
                industry_daily_frames.append(frame)
            industry_daily = pd.concat(industry_daily_frames, ignore_index=True)
            append_dataset(RAW_FILES["industry_daily"], industry_daily, ["industry_code", "date"])
        except DataSourceError as exc:
            provider_entries.append(
                {"method": "get_industry_daily", "adapter": "composite", "success": False, "error": str(exc), "attempt_index": 1}
            )
            print(f"[warn] industry daily download failed: {exc}", file=sys.stderr)

    if not args.skip_valuations:
        valuation_tasks = [(symbol, metric) for symbol in symbols for metric in ("pb", "pe_ttm")]

        def fetch_valuation(task: tuple[str, str]):
            symbol, metric = task
            local_adapter = create_default_adapter(data_cfg)
            frame = local_adapter.get_stock_valuation_history(symbol, metric=metric, period=args.end_date)
            return frame, {
                "method": "get_stock_valuation_history",
                "adapter": "parallel_composite",
                "success": True,
                "error": None,
                "attempt_index": 1,
                "rows": int(len(frame)),
                "symbol": symbol,
                "metric": metric,
            }

        valuation_frames, valuation_entries = parallel_frames(valuation_tasks, args.workers, fetch_valuation, "valuation download")
        provider_entries.extend(valuation_entries)
        if not valuation_frames:
            raise DataSourceError("Stock valuation download failed for all selected symbols.")
        valuations = pd.concat(valuation_frames, ignore_index=True)
        append_dataset(RAW_FILES["stock_valuation"], valuations, ["code", "date", "metric"])
    provider_entries.extend(adapter.call_history)
    write_provider_health_report(
        "provider_health/latest.json",
        as_of_date=args.end_date,
        entries=provider_entries,
        source="update_market_data",
    )
    write_data_quality_report("data_quality/latest.json", list(RAW_FILES.values()), args.end_date)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
