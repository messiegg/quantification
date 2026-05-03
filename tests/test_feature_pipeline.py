from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd

from scripts.build_features import read_if_covers_date_range
from src.pipeline.features import (
    _apply_metric_rule_values,
    _compute_core_fields_complete,
    _compute_core_data_stale_days,
    _merge_asof_by_key,
    _normalize_industry_members,
    compute_stock_quantiles,
    compute_price_features,
    prepare_financial_effective_frame,
)
from src.pipeline.strict_data import build_dividend_daily, build_stock_valuation_daily, build_trade_calendar, clean_price_frame


ROOT = Path(__file__).resolve().parents[1]


def test_prepare_financial_effective_frame_computes_roe_percentile_without_index_error(configs: dict) -> None:
    financials = pd.DataFrame(
        {
            "code": ["600000.sh", "600000.sh", "600000.sh"],
            "report_date": ["2024-03-31", "2024-06-30", "2024-09-30"],
            "announcement_date": ["2024-04-20", "2024-07-20", "2024-10-20"],
            "roe": [8.0, 10.0, 12.0],
            "net_profit": [10.0, 12.0, 15.0],
            "cfo": [5.0, 6.0, 7.0],
            "debt_to_assets": [50.0, 49.0, 48.0],
            "is_st": [False, False, False],
        }
    )
    result = prepare_financial_effective_frame(financials, configs["strategy"])
    assert "roe_pct_in_last_12_quarters" in result.columns
    assert float(result["roe_pct_in_last_12_quarters"].iloc[-1]) > 0


def test_prepare_financial_effective_frame_backfills_missing_roe_from_profit_over_equity(configs: dict) -> None:
    financials = pd.DataFrame(
        {
            "code": ["600000.sh"],
            "report_date": ["2024-12-31"],
            "announcement_date": ["2025-04-20"],
            "roe": [pd.NA],
            "net_profit": [120.0],
            "cfo": [80.0],
            "debt_to_assets": [50.0],
            "is_st": [False],
            "equity": [2000.0],
        }
    )

    result = prepare_financial_effective_frame(financials, configs["strategy"])

    assert result.loc[0, "roe"] == 6.0


def test_prepare_financial_effective_frame_marks_ttm_statuses(configs: dict) -> None:
    financials = pd.DataFrame(
        {
            "code": ["600000.sh"] * 4,
            "report_date": ["2024-03-31", "2024-06-30", "2024-09-30", "2024-12-31"],
            "announcement_date": ["2024-04-20", "2024-07-20", "2024-10-20", "2025-04-20"],
            "roe": [1.0, 2.0, 3.0, 4.0],
            "net_profit": [10.0, 30.0, 60.0, 100.0],
            "cfo": [5.0, pd.NA, 20.0, 35.0],
            "debt_to_assets": [50.0] * 4,
            "is_st": [False] * 4,
            "equity": [100.0] * 4,
        }
    )

    result = prepare_financial_effective_frame(financials, configs["strategy"])

    assert result["net_profit_ttm_rule_status"].tolist() == ["insufficient_history", "insufficient_history", "insufficient_history", "ok"]
    assert result["cfo_ttm_rule_status"].tolist() == ["insufficient_history", "insufficient_history", "insufficient_history", "source_missing"]


def test_merge_asof_by_key_handles_multiple_symbols_sorted_by_date_then_key() -> None:
    left = pd.DataFrame(
        {
            "symbol": ["b", "a", "b", "a"],
            "date": ["2024-01-02", "2024-01-01", "2024-01-03", "2024-01-03"],
            "value": [2, 1, 3, 4],
        }
    )
    right = pd.DataFrame(
        {
            "symbol": ["a", "b"],
            "date": ["2024-01-01", "2024-01-02"],
            "flag": [10, 20],
        }
    )
    merged = _merge_asof_by_key(left, right, by="symbol")
    assert list(merged["flag"]) == [10, 20, 10, 20]


def test_normalize_industry_members_prefers_level_hierarchy_and_l1_industry() -> None:
    members = pd.DataFrame(
        [
            {"code": "600000.sh", "name": "浦发银行", "industry_code": "801780.SI", "industry_name": "银行", "industry_level": "first"},
            {"code": "600000.sh", "name": "浦发银行", "industry_code": "801783.SI", "industry_name": "股份制银行Ⅱ", "industry_level": "second"},
            {"code": "600000.sh", "name": "浦发银行", "industry_code": "857831.SI", "industry_name": "股份制银行Ⅲ", "industry_level": "third"},
        ]
    )
    normalized = _normalize_industry_members(members)
    row = normalized.iloc[0].to_dict()
    assert row["industry"] == "银行"
    assert row["industry_code"] == "801780"
    assert row["industry_l1"] == "银行"
    assert row["industry_l2"] == "股份制银行Ⅱ"
    assert row["industry_l3"] == "股份制银行Ⅲ"


def test_build_trade_calendar_uses_price_daily_dates_only() -> None:
    prices = pd.DataFrame(
        {
            "code": ["600000.sh", "600000.sh", "000001.sz", "000001.sz"],
            "date": ["2026-04-03", "2026-04-03", "2026-04-04", "2026-04-02"],
            "close": [10.2, 10.2, 11.0, 10.8],
        }
    )

    calendar = build_trade_calendar(prices)

    assert calendar.to_dict(orient="records") == [
        {"date": "2026-04-02", "source": "price_daily"},
        {"date": "2026-04-03", "source": "price_daily"},
    ]


def test_clean_price_frame_normalizes_akshare_tx_amount_to_cny_once() -> None:
    prices = pd.DataFrame(
        {
            "code": ["000333.sz", "600000.sh"],
            "date": ["2026-04-03", "2026-04-03"],
            "close": [76.35, 10.12],
            "volume": [pd.NA, 411518.0],
            "amount": [172773.0, 417211984.0],
        }
    )

    cleaned = clean_price_frame(prices)

    assert float(cleaned.loc[cleaned["code"] == "000333.sz", "amount"].iloc[0]) == 172773.0 * 10000.0
    assert float(cleaned.loc[cleaned["code"] == "600000.sh", "amount"].iloc[0]) == 417211984.0


def test_compute_price_features_uses_trade_calendar_for_listed_days() -> None:
    prices = pd.DataFrame(
        {
            "code": ["600000.sh", "600000.sh"],
            "date": ["2026-04-02", "2026-04-03"],
            "open": [10.0, 10.1],
            "high": [10.2, 10.3],
            "low": [9.9, 10.0],
            "close": [10.1, 10.2],
            "volume": [1000, 1100],
            "amount": [1_000_000, 1_100_000],
        }
    )
    stock_list = pd.DataFrame([{"code": "600000.sh", "listed_date": "2026-04-02"}])
    trade_calendar = pd.DataFrame(
        {
            "date": ["2026-04-01", "2026-04-02", "2026-04-03"],
            "source": ["price_daily", "price_daily", "price_daily"],
        }
    )

    features = compute_price_features(prices, stock_list=stock_list, trade_calendar=trade_calendar)

    assert list(features["listed_days"].astype(int)) == [1, 2]
    assert list(features["listed_days_source"]) == ["listed_date_trade_calendar", "listed_date_trade_calendar"]


def test_compute_price_features_trade_calendar_not_short_benchmark_caps_mature_symbol() -> None:
    prices = pd.DataFrame(
        {
            "code": ["600000.sh", "600000.sh"],
            "date": ["2026-04-02", "2026-04-03"],
            "open": [10.0, 10.1],
            "high": [10.2, 10.3],
            "low": [9.9, 10.0],
            "close": [10.1, 10.2],
            "volume": [1000, 1100],
            "amount": [1_000_000, 1_100_000],
        }
    )
    stock_list = pd.DataFrame([{"code": "600000.sh", "listed_date": "1999-11-10"}])
    trade_calendar = pd.DataFrame(
        {
            "date": ["2026-03-31", "2026-04-01", "2026-04-02", "2026-04-03"],
            "source": ["price_daily"] * 4,
        }
    )
    benchmark = pd.DataFrame(
        {
            "code": ["000300.sh", "000300.sh"],
            "date": ["2026-04-02", "2026-04-03"],
            "close": [1.0, 1.0],
        }
    )

    features = compute_price_features(
        prices,
        stock_list=stock_list,
        trade_calendar=trade_calendar,
        benchmark_daily=benchmark,
    )

    assert list(features["listed_days"].astype(int)) == [3, 4]
    assert list(features["listed_days_source"]) == ["listed_date_trade_calendar", "listed_date_trade_calendar"]


def test_compute_price_features_falls_back_to_first_trade_when_listed_date_missing() -> None:
    prices = pd.DataFrame(
        {
            "code": ["600000.sh", "600000.sh"],
            "date": ["2026-04-02", "2026-04-03"],
            "open": [10.0, 10.1],
            "high": [10.2, 10.3],
            "low": [9.9, 10.0],
            "close": [10.1, 10.2],
            "volume": [1000, 1100],
            "amount": [1_000_000, 1_100_000],
        }
    )
    stock_list = pd.DataFrame([{"code": "600000.sh", "listed_date": pd.NA}])
    trade_calendar = pd.DataFrame(
        {
            "date": ["2026-04-01", "2026-04-02", "2026-04-03"],
            "source": ["price_daily"] * 3,
        }
    )

    features = compute_price_features(prices, stock_list=stock_list, trade_calendar=trade_calendar)

    assert list(features["listed_days"].astype(int)) == [1, 2]
    assert list(features["listed_days_source"]) == ["first_price_trade_calendar", "first_price_trade_calendar"]


def test_build_dividend_daily_computes_trailing_cash_dividend_yield() -> None:
    prices = pd.DataFrame(
        {
            "code": ["600000.sh", "600000.sh", "600000.sh"],
            "date": ["2025-04-30", "2025-05-01", "2026-05-01"],
            "open": [10.0, 10.0, 10.0],
            "high": [10.0, 10.0, 10.0],
            "low": [10.0, 10.0, 10.0],
            "close": [10.0, 10.0, 10.0],
            "volume": [100, 100, 100],
            "amount": [1000, 1000, 1000],
        }
    )
    dividend_events = pd.DataFrame(
        {
            "code": ["600000.sh", "600000.sh"],
            "announcement_date": ["2024-04-20", "2025-04-20"],
            "record_date": ["2024-04-30", "2025-04-30"],
            "ex_dividend_date": ["2024-05-01", "2025-05-01"],
            "cash_dividend_per_share": [1.0, 2.0],
            "progress": ["实施分配", "实施分配"],
        }
    )

    result = build_dividend_daily(prices, dividend_events)

    assert result["dividend_per_share_ttm"].tolist() == [1.0, 3.0, 2.0]
    assert result["dividend_event_count_ttm"].tolist() == [1, 2, 1]
    assert result["dv_ttm"].round(4).tolist() == [0.1, 0.3, 0.2]


def test_build_stock_valuation_daily_adds_pe_rule_value_for_non_positive_ttm() -> None:
    market_caps = pd.DataFrame(
        {
            "symbol": ["600000.sh", "600001.sh"],
            "date": ["2026-04-03", "2026-04-03"],
            "total_mv": [1000.0, 800.0],
            "float_mv": [900.0, 700.0],
            "market_cap_billion": [1.0, 0.8],
        }
    )
    financials = pd.DataFrame(
        {
            "code": ["600000.sh", "600001.sh"],
            "date": ["2026-04-03", "2026-04-03"],
            "equity_effective": [500.0, 400.0],
            "net_profit_ttm_effective": [100.0, -20.0],
            "net_profit_ttm_rule_status": ["ok", "ok"],
            "report_date": ["2025-12-31", "2025-12-31"],
            "announcement_date": ["2026-03-30", "2026-03-30"],
            "effective_date": ["2026-03-30", "2026-03-30"],
        }
    )

    result = build_stock_valuation_daily(market_caps, financials).sort_values("symbol").reset_index(drop=True)

    assert result.loc[0, "pe_ttm"] == 10.0
    assert bool(result.loc[0, "ttm_profit_positive"]) is True
    assert result.loc[0, "pe_ttm_rule_value"] == 10.0
    assert result.loc[0, "pe_ttm_rule_status"] == "ok"
    assert result.loc[0, "pb_rule_value"] == 2.0
    assert result.loc[0, "pb_rule_status"] == "ok"
    assert pd.isna(result.loc[1, "pe_ttm"])
    assert bool(result.loc[1, "ttm_profit_positive"]) is False
    assert result.loc[1, "pe_ttm_rule_value"] == -999999999.0
    assert result.loc[1, "pe_ttm_rule_status"] == "ttm_non_positive"
    assert result.loc[1, "pb_rule_status"] == "ok"


def test_apply_metric_rule_values_separates_uncomputable_from_source_missing() -> None:
    panel = pd.DataFrame(
        {
            "net_profit_ttm_effective": [10.0, -5.0, pd.NA, pd.NA],
            "net_profit_ttm_rule_status": ["ok", "ok", "insufficient_history", "source_missing"],
            "pe_ttm": [12.0, pd.NA, pd.NA, pd.NA],
            "pb": [1.2, pd.NA, pd.NA, pd.NA],
            "equity_effective": [100.0, -20.0, 10.0, pd.NA],
            "roe": [8.0, pd.NA, pd.NA, pd.NA],
            "roe_rule_status": ["ok", "equity_non_positive", "source_missing", "source_missing"],
            "cfo_ttm": [5.0, pd.NA, pd.NA, pd.NA],
            "cfo_ttm_rule_status": ["ok", "source_missing", "insufficient_history", "source_missing"],
            "stock_pe_ttm_q_5y": [35.0, pd.NA, pd.NA, pd.NA],
            "stock_pe_ttm_q_10y": [45.0, pd.NA, pd.NA, pd.NA],
            "stock_pe_ttm_q_blended": [39.0, pd.NA, pd.NA, pd.NA],
            "stock_pe_ttm_history_observations": [1500.0, pd.NA, pd.NA, pd.NA],
            "stock_pb_q_5y": [25.0, pd.NA, pd.NA, pd.NA],
            "stock_pb_q_10y": [30.0, pd.NA, pd.NA, pd.NA],
            "stock_pb_q_blended": [27.0, pd.NA, pd.NA, pd.NA],
            "stock_pb_history_observations": [1500.0, pd.NA, pd.NA, pd.NA],
        }
    )

    result = _apply_metric_rule_values(panel)

    assert result.loc[0, "pe_ttm"] == 12.0
    assert pd.isna(result.loc[1, "pe_ttm"])
    assert result["ttm_profit_positive"].tolist() == [True, False, False, False]
    assert result["pe_ttm_rule_status"].tolist() == ["ok", "ttm_non_positive", "insufficient_history", "source_missing"]
    assert result.loc[0, "pe_ttm_rule_value"] == 12.0
    assert result.loc[1, "pe_ttm_rule_value"] == -999999999.0
    assert result.loc[2, "pe_ttm_rule_value"] == -999999999.0
    assert pd.isna(result.loc[3, "pe_ttm_rule_value"])
    assert result["pb_rule_status"].tolist() == ["ok", "equity_non_positive", "source_missing", "source_missing"]
    assert result.loc[0, "pb_rule_value"] == 1.2
    assert result.loc[1, "pb_rule_value"] == -999999999.0
    assert pd.isna(result.loc[2, "pb_rule_value"])
    assert pd.isna(result.loc[3, "pb_rule_value"])
    assert result.loc[0, "roe_rule_value"] == 8.0
    assert result.loc[1, "roe_rule_value"] == -999999999.0
    assert pd.isna(result.loc[2, "roe_rule_value"])
    assert pd.isna(result.loc[3, "roe_rule_value"])
    assert result.loc[0, "cfo_ttm_rule_value"] == 5.0
    assert pd.isna(result.loc[1, "cfo_ttm_rule_value"])
    assert result.loc[2, "cfo_ttm_rule_value"] == -999999999.0
    assert pd.isna(result.loc[3, "cfo_ttm_rule_value"])
    assert result.loc[0, "stock_pe_ttm_q_5y_rule_value"] == 35.0
    assert result.loc[1, "stock_pe_ttm_q_5y_rule_value"] == -999999999.0
    assert result.loc[2, "stock_pe_ttm_q_5y_rule_value"] == -999999999.0
    assert pd.isna(result.loc[3, "stock_pe_ttm_q_5y_rule_value"])
    assert result.loc[0, "stock_pe_ttm_q_10y_rule_value"] == 45.0
    assert result.loc[1, "stock_pe_ttm_q_10y_rule_value"] == -999999999.0
    assert result.loc[2, "stock_pe_ttm_q_10y_rule_value"] == -999999999.0
    assert pd.isna(result.loc[3, "stock_pe_ttm_q_10y_rule_value"])
    assert result.loc[0, "stock_pe_ttm_q_blended_rule_value"] == 39.0
    assert result.loc[1, "stock_pe_ttm_q_blended_rule_value"] == -999999999.0
    assert result.loc[2, "stock_pe_ttm_q_blended_rule_value"] == -999999999.0
    assert pd.isna(result.loc[3, "stock_pe_ttm_q_blended_rule_value"])
    assert result.loc[0, "stock_pe_ttm_history_observations_rule_value"] == 1500.0
    assert result.loc[1, "stock_pe_ttm_history_observations_rule_value"] == -999999999.0
    assert result.loc[2, "stock_pe_ttm_history_observations_rule_value"] == -999999999.0
    assert pd.isna(result.loc[3, "stock_pe_ttm_history_observations_rule_value"])
    assert result.loc[0, "stock_pb_q_blended_rule_value"] == 27.0
    assert result.loc[1, "stock_pb_q_blended_rule_value"] == -999999999.0
    assert pd.isna(result.loc[2, "stock_pb_q_blended_rule_value"])
    assert pd.isna(result.loc[3, "stock_pb_q_blended_rule_value"])


def test_compute_core_fields_complete_separates_uncomputable_from_true_missing() -> None:
    panel = pd.DataFrame(
        {
            "industry": ["银行", "银行"],
            "market_cap_billion": [80.0, 80.0],
            "avg_amount_60d_million": [120.0, 120.0],
            "roe": [pd.NA, pd.NA],
            "roe_rule_value": [-999999999.0, pd.NA],
            "latest_net_profit": [10.0, 10.0],
            "cfo_ttm": [pd.NA, pd.NA],
            "cfo_ttm_rule_value": [-999999999.0, pd.NA],
            "debt_to_assets": [50.0, 50.0],
            "stock_pb_q_blended": [pd.NA, pd.NA],
            "stock_pb_q_blended_rule_value": [-999999999.0, pd.NA],
            "industry_pb_q_blended": [30.0, 30.0],
            "stock_pe_ttm_q_blended": [pd.NA, pd.NA],
            "stock_pe_ttm_q_blended_rule_value": [-999999999.0, pd.NA],
            "industry_pe_ttm_q_blended": [35.0, 35.0],
        }
    )

    result = _compute_core_fields_complete(panel)

    assert result.tolist() == [True, False]


def test_core_data_stale_days_respects_financial_reporting_window() -> None:
    stale_days = _compute_core_data_stale_days(
        pd.Series(["2026-04-03", "2026-05-06"]),
        pd.Series(["2025-09-30", "2025-09-30"]),
        pd.Series(["2025-10-28", "2025-10-28"]),
    )

    assert list(stale_days.astype("Int64")) == [0, 6]


def test_compute_stock_quantiles_returns_latest_quantiles_only() -> None:
    valuation = pd.DataFrame(
        {
            "symbol": ["600000.sh"] * 3,
            "date": ["2026-04-01", "2026-04-02", "2026-04-03"],
            "pb": [1.0, 1.2, 1.1],
            "pe_ttm": [10.0, 12.0, 11.0],
        }
    )
    strategy_cfg = {
        "valuation": {
            "windows_years": {"q_5y": 5, "q_10y": 10},
            "blended_weights": {"q_5y": 0.6, "q_10y": 0.4},
            "trading_days_per_year": 252,
        }
    }

    latest = compute_stock_quantiles(valuation, strategy_cfg)

    assert latest["date"].tolist() == ["2026-04-03"]
    assert latest["code"].tolist() == ["600000.sh"]
    assert latest["stock_pb_history_observations"].tolist() == [3]
    assert latest["stock_pe_ttm_history_observations"].tolist() == [3]
    assert pd.notna(latest["stock_pb_q_blended"].iloc[0])


def test_read_if_covers_date_range_rejects_stale_quantile_cache(tmp_path) -> None:
    cached = pd.DataFrame(
        {
            "date": ["2021-04-26", "2026-04-03"],
            "code": ["600000.sh", "600000.sh"],
            "stock_pb_q_blended": [50.0, 40.0],
        }
    )
    source = pd.DataFrame(
        {
            "date": ["2015-01-05", "2026-04-03"],
            "symbol": ["600000.sh", "600000.sh"],
            "pb": [1.0, 1.1],
        }
    )
    path = tmp_path / "stock_quantiles.parquet"
    cached.to_parquet(path, index=False)

    loaded = read_if_covers_date_range(path, source)

    assert loaded.empty


def test_key_scripts_support_help() -> None:
    scripts = [
        "scripts/update_market_data.py",
        "scripts/build_features.py",
        "scripts/refresh_universe.py",
        "scripts/prepare_snapshot.py",
        "scripts/render_report.py",
    ]
    for script in scripts:
        result = subprocess.run(
            [sys.executable, script, "--help"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, script
        assert "usage:" in result.stdout.lower(), script
