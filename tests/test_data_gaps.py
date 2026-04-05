from __future__ import annotations

import pandas as pd

from src.utils.data_gaps import (
    financial_ready_symbols,
    hs_a_share_symbols,
    latest_ready_symbols,
    price_ready_symbols,
    valuation_ready_symbols,
)


def test_hs_a_share_symbols_filters_out_bj_codes() -> None:
    stock_list = pd.DataFrame({"code": ["600000.sh", "000001.sz", "830799.bj"]})
    assert hs_a_share_symbols(stock_list) == ["000001.sz", "600000.sh"]


def test_latest_ready_symbols_requires_target_date() -> None:
    frame = pd.DataFrame({"code": ["600000.sh", "000001.sz"], "date": ["2026-04-03", "2026-04-02"]})
    ready = latest_ready_symbols(frame, ["600000.sh", "000001.sz"], "date", "2026-04-03")
    assert ready == {"600000.sh"}


def test_price_ready_symbols_requires_latest_date_and_min_rows() -> None:
    frame = pd.DataFrame(
        {
            "code": ["600000.sh"] * 250 + ["000001.sz"] * 249,
            "date": ["2026-04-03"] * 250 + ["2026-04-03"] * 249,
        }
    )
    ready = price_ready_symbols(frame, ["600000.sh", "000001.sz"], "2026-04-03", min_rows=250)
    assert ready == {"600000.sh"}


def test_valuation_ready_symbols_filters_by_metric_history_and_latest_date() -> None:
    frame = pd.DataFrame(
        {
            "code": ["600000.sh"] * 3 + ["000001.sz"] * 3,
            "metric": ["pb", "pb", "pb", "pb", "pb", "pe_ttm"],
            "date": ["2026-04-01", "2026-04-02", "2026-04-03", "2026-04-01", "2026-04-02", "2026-04-03"],
        }
    )
    ready = valuation_ready_symbols(frame, ["600000.sh", "000001.sz"], "pb", "2026-04-03", min_history_rows=3)
    assert ready == {"600000.sh"}


def test_financial_ready_symbols_requires_recent_report_and_core_fields() -> None:
    frame = pd.DataFrame(
        {
            "code": ["600000.sh", "000001.sz"],
            "report_date": ["2025-12-31", "2025-09-30"],
            "roe": [8.0, 7.0],
            "net_profit": [10.0, 9.0],
            "cfo": [5.0, None],
            "debt_to_assets": [40.0, 50.0],
        }
    )
    ready = financial_ready_symbols(frame, ["600000.sh", "000001.sz"], "2025-12-31")
    assert ready == {"600000.sh"}
