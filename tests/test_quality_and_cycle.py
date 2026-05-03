from __future__ import annotations

import pandas as pd

from src.strategy.quality import evaluate_quality, is_cycle_peak_trap


def test_cycle_peak_trap_triggers_with_strict_quantile_and_roe_percentile(configs: dict) -> None:
    cycle_cfg = configs["strategy"]["buckets"]["cyclical_rotation"]["cycle_trap_filter"]
    latest = {"stock_pe_ttm_q_blended": 10, "roe": 18, "roe_pct_in_last_12_quarters": 90}
    history = pd.DataFrame(
        {
            "date": ["2023-03-31", "2023-06-30", "2023-09-30", "2023-12-31"],
            "roe": [10, 20, 17, 18],
        }
    )
    assert is_cycle_peak_trap(latest, history, cycle_cfg, trading_days=252)


def test_evaluate_quality_uses_extended_thresholds(configs: dict) -> None:
    filters_cfg = configs["strategy"]["buckets"]["defensive_dividend"]["filters"]
    passed, reasons = evaluate_quality(
        {
            "listed_days": 2000,
            "not_st": True,
            "market_cap_billion": 80,
            "avg_amount_60d_million": 150,
            "roe": 10,
            "latest_net_profit": 1,
            "cfo_ttm": 1,
            "debt_to_assets": 60,
            "dv_ttm": 0.04,
            "main_metric": "pe_ttm",
            "pe_ttm": 12,
            "stock_pb_q_blended": 20,
            "pb": 1.2,
        },
        filters_cfg,
    )
    assert passed is True
    assert reasons == []


def test_evaluate_quality_uses_rule_statuses_for_uncomputable_values(configs: dict) -> None:
    filters_cfg = configs["strategy"]["buckets"]["defensive_dividend"]["filters"]
    passed, reasons = evaluate_quality(
        {
            "listed_days": 2000,
            "not_st": True,
            "market_cap_billion": 80,
            "avg_amount_60d_million": 150,
            "roe": pd.NA,
            "roe_rule_value": -999999999.0,
            "roe_rule_status": "equity_non_positive",
            "latest_net_profit": 1,
            "cfo_ttm": pd.NA,
            "cfo_ttm_rule_value": -999999999.0,
            "cfo_ttm_rule_status": "insufficient_history",
            "debt_to_assets": 60,
            "dv_ttm": 0.04,
            "main_metric": "pe_ttm",
            "pe_ttm": pd.NA,
            "pe_ttm_rule_value": -999999999.0,
            "pe_ttm_rule_status": "ttm_non_positive",
            "stock_pb_q_blended": 20,
            "pb": 1.2,
        },
        filters_cfg,
    )

    assert passed is False
    assert reasons == [
        "roe_equity_non_positive",
        "cfo_ttm_insufficient_history",
        "pe_ttm_ttm_non_positive",
    ]
