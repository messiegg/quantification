from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

from scripts.audit_backtest_lookahead import build_valuation_field_resolution
from scripts.build_combined_v2_release_candidate import build_release_manifest, build_report_consistency_check
from src.strategy.valuation_resolution import resolve_industry_valuation_quantile, resolve_stock_valuation_quantile
from src.utils.config import load_yaml, resolve_path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_valuation_resolver_matches_v2_actual_fields() -> None:
    metric_map = load_yaml("config/metric_map.yml")
    defensive_pe = {
        "date": "2026-04-03",
        "industry": "通信",
        "bucket": "defensive_dividend",
        "pe_ttm": 18.0,
        "stock_pe_ttm_q_blended": 22.0,
        "industry_pe_ttm_q_blended": 33.0,
        "stock_pb_q_blended": 44.0,
        "industry_pb_q_blended": 55.0,
    }
    stock = resolve_stock_valuation_quantile(defensive_pe, "defensive_dividend", metric_map)
    industry = resolve_industry_valuation_quantile(defensive_pe, "defensive_dividend", metric_map)
    assert stock.value == 22.0
    assert stock.source_field == "stock_pe_ttm_q_blended"
    assert stock.metric == "pe_ttm"
    assert industry.value == 33.0
    assert industry.source_field == "industry_pe_ttm_q_blended"

    defensive_pb_fallback = dict(defensive_pe, pe_ttm=pd.NA)
    stock = resolve_stock_valuation_quantile(defensive_pb_fallback, "defensive_dividend", metric_map)
    assert stock.value == 44.0
    assert stock.source_field == "stock_pb_q_blended"
    assert stock.metric == "pb"
    assert stock.fallback_used is True

    cyclical = dict(defensive_pe, industry="有色金属", bucket="cyclical_rotation")
    stock = resolve_stock_valuation_quantile(cyclical, "cyclical_rotation", metric_map)
    industry = resolve_industry_valuation_quantile(cyclical, "cyclical_rotation", metric_map)
    assert stock.value == 44.0
    assert stock.metric == "pb"
    assert industry.value == 55.0
    assert industry.metric == "pb"


def test_lookahead_field_resolution_checks_resolver_source_fields() -> None:
    scores = pd.DataFrame(
        [
            {
                "date": "2024-01-03",
                "ts_code": "600000.sh",
                "industry": "银行",
                "bucket": "defensive_dividend",
                "stock_valuation_quantile": 20.0,
                "stock_valuation_quantile_source_field": "stock_pb_q_blended",
                "stock_valuation_metric": "pb",
                "industry_valuation_quantile": 30.0,
                "industry_valuation_quantile_source_field": "industry_pb_q_blended",
                "industry_valuation_metric": "pb",
            }
        ]
    )
    stock_daily = pd.DataFrame([{"date": "2024-01-02", "symbol": "600000.sh", "pb": 1.0}])
    industry_daily = pd.DataFrame([{"date": "2024-01-02", "industry_name": "银行", "pb": 1.1}])
    resolution = build_valuation_field_resolution(scores, stock_daily, industry_daily)
    row = resolution.iloc[0]
    assert row["pass_or_fail"] == "PASS"
    assert row["stock_valuation_quantile_source_field"] == "stock_pb_q_blended"
    assert row["max_source_date_used"] == "2024-01-02"


def test_report_consistency_and_manifest_do_not_mutate_trades_detailed() -> None:
    trades_path = resolve_path("reports/backtest/combined_v2_trades_detailed.csv")
    before = _sha256(trades_path)
    build_report_consistency_check()
    build_release_manifest()
    after = _sha256(trades_path)
    assert after == before


def test_current_combined_v2_next_bar_strict_metrics_match_rc() -> None:
    execution = pd.read_csv(resolve_path("reports/backtest/audit/execution_mode_compare.csv"))
    row = execution[(execution["profile"] == "combined_v2") & (execution["execution_mode"] == "next_bar")].iloc[0]
    assert abs(float(row["annual_return"]) - 0.0714) < 0.003
    assert abs(float(row["cumulative_return"]) - 0.2196) < 0.003
    assert abs(float(row["max_drawdown"]) - (-0.0936)) < 0.005
    assert int(row["total_trades"]) == 76


def test_release_manifest_matches_current_trade_and_nav_artifacts() -> None:
    manifest = build_release_manifest()
    execution = pd.read_csv(resolve_path("reports/backtest/audit/execution_mode_compare.csv"))
    row = execution[(execution["profile"] == "combined_v2") & (execution["execution_mode"] == "next_bar")].iloc[0]
    expected_final_nav = 200000.0 * (1.0 + float(row["cumulative_return"]))
    assert abs(float(manifest["final_nav"]) - expected_final_nav) < 1e-6
    assert int(manifest["total_trades"]) == 76
    trade_hash = next(item for item in manifest["key_output_file_hashes"] if item["path"] == "reports/backtest/combined_v2_trades_detailed.csv")
    assert trade_hash["exists"]
    assert trade_hash["sha256"] == _sha256(resolve_path("reports/backtest/combined_v2_trades_detailed.csv"))


def test_report_diagnostics_keep_nav_and_monthly_consistency() -> None:
    consistency = build_report_consistency_check()
    failed = consistency[consistency["status"] == "FAIL"]
    assert failed.empty
    monthly = pd.read_csv(resolve_path("reports/backtest/attribution/combined_v2_monthly_returns.csv"))
    assert abs(float(monthly["diff"].iloc[-1])) < 1e-8
    daily = pd.read_csv(resolve_path("reports/backtest/attribution/combined_v2_daily_regime_attribution.csv"))
    execution = pd.read_csv(resolve_path("reports/backtest/audit/execution_mode_compare.csv"))
    row = execution[(execution["profile"] == "combined_v2") & (execution["execution_mode"] == "next_bar")].iloc[0]
    expected_pnl = 200000.0 * float(row["cumulative_return"])
    assert abs(float(daily["daily_pnl"].sum()) - expected_pnl) < 1e-6
