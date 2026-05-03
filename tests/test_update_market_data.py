from __future__ import annotations

import json

import pandas as pd

from scripts.update_market_data import (
    append_dataset,
    dataset_min_timestamp,
    dividend_report_dates,
    needs_history_backfill,
    required_financial_report_date,
    strict_financial_history_gaps,
    strict_price_history_gaps,
    strict_price_symbol_complete,
    write_strict_price_gap_report,
)
from src.pipeline.strict_data import clean_benchmark_frame


def test_strict_price_history_gaps_flags_old_symbol_but_not_recent_listing() -> None:
    prices = pd.DataFrame(
        {
            "code": ["600000.sh", "600000.sh", "301000.sz", "301000.sz"],
            "date": ["2025-01-02", "2026-04-03", "2025-01-02", "2026-04-03"],
            "close": [10.0, 11.0, 20.0, 21.0],
        }
    )
    stock_list = pd.DataFrame(
        {
            "code": ["600000.sh", "301000.sz"],
            "listed_date": ["1999-11-10", "2024-12-20"],
        }
    )

    report = strict_price_history_gaps(
        prices,
        ["600000.sh", "301000.sz", "000001.sz"],
        start_date="2021-01-01",
        end_date="2026-04-03",
        stock_list=stock_list,
        expected_start_date="2021-01-04",
    )

    details = {item["symbol"]: item for item in report["details"]}

    assert report["expected_start_date"] == "2021-01-04"
    assert report["missing_count"] == 2
    assert details["600000.sh"]["issues"] == ["history_starts_after_expected"]
    assert details["000001.sz"]["issues"] == ["missing_symbol_history"]
    assert "301000.sz" not in details


def test_dataset_min_timestamp_and_needs_history_backfill_detect_earlier_request() -> None:
    prices = pd.DataFrame(
        {
            "code": ["600000.sh", "600000.sh"],
            "date": ["2018-01-02", "2026-04-03"],
            "close": [10.0, 11.0],
        }
    )

    assert dataset_min_timestamp(prices, "date") == pd.Timestamp("2018-01-02")
    assert needs_history_backfill(prices, "2016-01-01", "date") is True
    assert needs_history_backfill(prices, "2018-01-02", "date") is False
    assert needs_history_backfill(pd.DataFrame(), "2016-01-01", "date") is True


def test_strict_price_history_gaps_respects_forced_expected_start_for_backfill_mode() -> None:
    prices = pd.DataFrame(
        {
            "code": ["600000.sh", "600000.sh"],
            "date": ["2016-01-04", "2026-04-03"],
            "close": [10.0, 11.0],
        }
    )
    stock_list = pd.DataFrame({"code": ["600000.sh"], "listed_date": ["1999-11-10"]})

    report = strict_price_history_gaps(
        prices,
        ["600000.sh"],
        start_date="2015-01-01",
        end_date="2026-04-03",
        stock_list=stock_list,
        expected_start_date="2015-01-05",
    )

    assert report["missing_count"] == 1
    assert report["details"][0]["issues"] == ["history_starts_after_expected"]


def test_write_strict_price_gap_report_writes_json_and_markdown(tmp_path) -> None:
    before = {
        "requested_start_date": "2021-01-01",
        "expected_start_date": "2021-01-04",
        "requested_end_date": "2026-04-03",
        "missing_count": 2,
        "missing_symbols": ["000001.sz", "000002.sz"],
        "details": [
            {
                "symbol": "000001.sz",
                "listed_date": "1991-04-03",
                "min_date": "2025-01-02",
                "max_date": "2026-04-03",
                "row_count": 302,
                "issues": ["history_starts_after_expected"],
            }
        ],
    }
    after = {
        "requested_start_date": "2021-01-01",
        "expected_start_date": "2021-01-04",
        "requested_end_date": "2026-04-03",
        "missing_count": 1,
        "missing_symbols": ["000002.sz"],
        "details": [
            {
                "symbol": "000002.sz",
                "listed_date": "1991-01-29",
                "min_date": "2025-01-02",
                "max_date": "2026-04-03",
                "row_count": 302,
                "issues": ["history_starts_after_expected"],
            }
        ],
    }

    write_strict_price_gap_report("2026-04-03", before, after, tmp_path)

    json_payload = json.loads((tmp_path / "price_history_gaps_2026-04-03.json").read_text(encoding="utf-8"))
    markdown = (tmp_path / "price_history_gaps_2026-04-03.md").read_text(encoding="utf-8")

    assert json_payload["before"]["missing_count"] == 2
    assert json_payload["after"]["missing_count"] == 1
    assert "000002.sz" in markdown
    assert "history_starts_after_expected" in markdown


def test_strict_price_symbol_complete_requires_full_window_for_mature_symbol() -> None:
    prices = pd.DataFrame(
        {
            "code": ["600000.sh", "600000.sh"],
            "date": ["2025-01-02", "2026-04-03"],
            "close": [10.0, 11.0],
        }
    )
    stock_list = pd.DataFrame(
        {
            "code": ["600000.sh"],
            "listed_date": ["1999-11-10"],
        }
    )

    assert not strict_price_symbol_complete(
        prices,
        "600000.sh",
        start_date="2021-01-01",
        end_date="2026-04-03",
        stock_list=stock_list,
        expected_start_date="2021-01-04",
    )


def test_required_financial_report_date_respects_a_share_disclosure_windows() -> None:
    assert required_financial_report_date("2026-04-03") == "2025-09-30"
    assert required_financial_report_date("2026-05-06") == "2025-12-31"
    assert required_financial_report_date("2026-09-15") == "2026-06-30"
    assert required_financial_report_date("2026-11-03") == "2026-09-30"


def test_dividend_report_dates_include_prior_year_for_initial_ttm_window() -> None:
    assert dividend_report_dates("2021-01-04", "2021-12-31") == [
        "2019-06-30",
        "2019-12-31",
        "2020-06-30",
        "2020-12-31",
        "2021-06-30",
        "2021-12-31",
    ]


def test_strict_financial_history_gaps_accepts_latest_required_q3_but_flags_missing_equity() -> None:
    financials = pd.DataFrame(
        {
            "code": ["002601.sz", "600036.sh"],
            "report_date": ["2025-09-30", "2025-12-31"],
            "announcement_date": ["2025-10-28", pd.NA],
            "roe": [7.02, 13.44],
            "net_profit": [1.6, 150.0],
            "cfo": [1.0, 2.0],
            "debt_to_assets": [50.0, 90.0],
            "equity": [23.5, pd.NA],
        }
    )

    report = strict_financial_history_gaps(
        financials,
        ["002601.sz", "600036.sh"],
        start_date="2020-01-01",
        end_date="2026-04-03",
        as_of_date="2026-04-03",
    )

    assert report["required_report_date"] == "2025-09-30"
    assert report["missing_symbols"] == ["600036.sh"]
    assert report["details"][0]["issues"] == ["equity_missing_on_latest"]


def test_append_dataset_prefers_non_null_announcement_date_for_same_report(tmp_path) -> None:
    path = tmp_path / "financials.parquet"
    existing = pd.DataFrame(
        {
            "code": ["000001.sz"],
            "report_date": ["2025-12-31"],
            "announcement_date": [pd.NA],
            "equity": [pd.NA],
        }
    )
    existing.to_parquet(path, index=False)
    incoming = pd.DataFrame(
        {
            "code": ["000001.sz"],
            "report_date": ["2025-12-31"],
            "announcement_date": ["2026-03-21"],
            "equity": [451187600000.0],
        }
    )

    append_dataset(path, incoming, ["code", "report_date"])

    merged = pd.read_parquet(path)
    assert merged.loc[0, "announcement_date"] == "2026-03-21"
    assert float(merged.loc[0, "equity"]) == 451187600000.0


def test_clean_benchmark_frame_drops_invalid_duplicate_rows_and_prefers_complete_record() -> None:
    benchmark = pd.DataFrame(
        {
            "code": ["000300.sh", "000300.sz", "nan"],
            "date": ["2026-04-03", "2026-04-03", "2026-04-03"],
            "close": [4440.7889, 4440.79, 103.0],
            "open": [4492.8461, 4492.84, pd.NA],
            "high": [4494.4571, 4494.45, pd.NA],
            "low": [4437.5952, 4437.59, pd.NA],
            "volume": [1.683217e10, 1.683217e8, pd.NA],
            "amount": [3.732349e11, 3.732349e11, pd.NA],
            "turn": [0.509606, pd.NA, pd.NA],
        }
    )

    cleaned = clean_benchmark_frame(benchmark)

    assert len(cleaned) == 1
    assert cleaned.loc[0, "code"] == "000300.sh"
    assert float(cleaned.loc[0, "close"]) == 4440.7889
