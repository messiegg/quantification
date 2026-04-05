from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


def hs_a_share_symbols(stock_list: pd.DataFrame) -> list[str]:
    if stock_list.empty or "code" not in stock_list.columns:
        return []
    symbols = stock_list["code"].astype(str)
    filtered = symbols[symbols.str.endswith((".sh", ".sz"))]
    return filtered.drop_duplicates().sort_values().tolist()


def latest_ready_symbols(frame: pd.DataFrame, all_symbols: list[str], date_col: str, target_date: str) -> set[str]:
    if frame.empty or "code" not in frame.columns or date_col not in frame.columns:
        return set()
    selected = frame.copy()
    selected[date_col] = pd.to_datetime(selected[date_col], errors="coerce")
    latest = selected.groupby("code", as_index=False)[date_col].max()
    threshold = pd.Timestamp(target_date)
    ready = latest[latest[date_col] >= threshold]["code"].astype(str)
    return set(ready[ready.isin(all_symbols)])


def price_ready_symbols(frame: pd.DataFrame, all_symbols: list[str], target_date: str, min_rows: int = 250) -> set[str]:
    if frame.empty or "code" not in frame.columns or "date" not in frame.columns:
        return set()
    selected = frame.copy()
    selected["date"] = pd.to_datetime(selected["date"], errors="coerce")
    grouped = selected.groupby("code", as_index=False).agg(last_date=("date", "max"), row_count=("date", "size"))
    threshold = pd.Timestamp(target_date)
    ready = grouped[(grouped["last_date"] >= threshold) & (grouped["row_count"] >= int(min_rows))]["code"].astype(str)
    return set(ready[ready.isin(all_symbols)])


def valuation_ready_symbols(
    frame: pd.DataFrame,
    all_symbols: list[str],
    metric: str,
    target_date: str,
    min_history_rows: int,
) -> set[str]:
    if frame.empty or {"code", "date", "metric"} - set(frame.columns):
        return set()
    selected = frame[frame["metric"].astype(str) == metric].copy()
    if selected.empty:
        return set()
    selected["date"] = pd.to_datetime(selected["date"], errors="coerce")
    grouped = selected.groupby("code", as_index=False).agg(last_date=("date", "max"), row_count=("date", "size"))
    threshold = pd.Timestamp(target_date)
    ready = grouped[(grouped["last_date"] >= threshold) & (grouped["row_count"] >= int(min_history_rows))]["code"].astype(str)
    return set(ready[ready.isin(all_symbols)])


def financial_ready_symbols(frame: pd.DataFrame, all_symbols: list[str], min_report_date: str) -> set[str]:
    required_fields = {"roe", "net_profit", "cfo", "debt_to_assets"}
    if frame.empty or {"code", "report_date"} - set(frame.columns):
        return set()
    selected = frame.copy()
    selected["report_date"] = pd.to_datetime(selected["report_date"], errors="coerce")
    latest = selected.sort_values(["code", "report_date"]).groupby("code", as_index=False).tail(1).copy()
    threshold = pd.Timestamp(min_report_date)
    ready_mask = latest["report_date"] >= threshold
    for field in required_fields:
        if field not in latest.columns:
            ready_mask &= False
        else:
            ready_mask &= pd.to_numeric(latest[field], errors="coerce").notna()
    ready = latest.loc[ready_mask, "code"].astype(str)
    return set(ready[ready.isin(all_symbols)])


def missing_symbols(all_symbols: list[str], ready_symbols: set[str]) -> list[str]:
    return sorted(set(all_symbols) - set(ready_symbols))


@dataclass
class TableStatus:
    dataset: str
    latest_value: str
    ready: bool
    row_count: int
    unique_count: int
    note: str = ""
