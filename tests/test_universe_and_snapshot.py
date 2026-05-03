from __future__ import annotations

import copy

import pandas as pd

from src.pipeline.snapshot import prepare_daily_snapshot
from src.strategy.universe import (
    _base_filter_reasons,
    _bucket_filter_reasons,
    build_effective_universe,
    effective_to_date,
    is_rebalance_day,
)


def _feature_row(symbol: str, bucket: str, industry: str, score: float = 80.0) -> dict:
    return {
        "symbol": symbol,
        "name": f"标的{symbol}",
        "industry": industry,
        "bucket": bucket,
        "main_metric": "pe_ttm" if bucket == "defensive_dividend" else "pb",
        "close": 10.0,
        "ma20": 9.8,
        "ma60": 9.5,
        "ma120": 11.0,
        "ma200": 8.8,
        "ma250": 9.2,
        "atr20": 0.4,
        "ma20_slope_10d": 0.02,
        "ma60_slope_20d": 0.01,
        "ma120_slope_20d": 0.01,
        "stock_q_blended": 12.0,
        "industry_q_blended": 12.0,
        "stock_q_5y": 10.0,
        "stock_q_10y": 14.0,
        "industry_q_5y": 11.0,
        "industry_q_10y": 13.0,
        "quality_pass": True,
        "cycle_peak_trap": False,
        "core_fields_complete": True,
        "core_data_stale_days": 0,
        "final_score": score,
        "universe_final_score": score,
        "data_stale": False,
    }


def _financial_history(symbol: str, is_st: bool = False) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "code": [symbol],
            "date": ["2025-12-31"],
            "latest_net_profit": [10.0],
            "roe": [12.0],
            "cfo_ttm": [10.0],
            "is_st": [is_st],
        }
    )


def test_universe_monthly_rebuild_and_hysteresis(configs: dict) -> None:
    feature_panel = pd.DataFrame({"date": ["2026-01-30", "2026-01-31"]})
    assert is_rebalance_day(feature_panel, "2026-01-31", "monthly") is True

    candidate_pool = pd.DataFrame(
        [
            {
                "symbol": "600001.sh",
                "name": "旧成分",
                "industry": "银行",
                "industry_rank": 4,
                "final_score": 82.0,
                "size_score": 70.0,
                "liquidity_score": 70.0,
                "industry_size_median": 60.0,
                "industry_liquidity_median": 60.0,
            },
            {
                "symbol": "600002.sh",
                "name": "新龙头",
                "industry": "银行",
                "industry_rank": 1,
                "final_score": 90.0,
                "size_score": 80.0,
                "liquidity_score": 80.0,
                "industry_size_median": 60.0,
                "industry_liquidity_median": 60.0,
            },
            {
                "symbol": "600003.sh",
                "name": "新第三名",
                "industry": "银行",
                "industry_rank": 3,
                "final_score": 89.0,
                "size_score": 90.0,
                "liquidity_score": 90.0,
                "industry_size_median": 60.0,
                "industry_liquidity_median": 60.0,
            },
        ]
    )
    previous_universe = {"stocks": [{"symbol": "600001.sh", "name": "旧成分", "industry_l1": "银行", "final_score": 82.0}]}
    selected, _ = build_effective_universe(candidate_pool, previous_universe, pd.DataFrame(columns=["symbol"]), configs["universe_rules"])
    assert set(selected["symbol"]) == {"600001.sh", "600002.sh"}
    assert "600003.sh" not in set(selected["symbol"])


def test_effective_to_date_advances_to_next_period_end_from_last_trading_day() -> None:
    assert effective_to_date("2025-01-27", "monthly") == "2025-02-28"
    assert effective_to_date("2025-03-28", "quarterly") == "2025-06-30"


def test_decision_scope_includes_effective_universe_union_current_holdings_and_frozen(configs: dict) -> None:
    strategy_cfg = copy.deepcopy(configs["strategy"])
    universe_rules_cfg = copy.deepcopy(configs["universe_rules"])
    account_cfg = copy.deepcopy(configs["account"])
    account_cfg["account"]["current_cash"] = 100000
    account_cfg["account"]["latest_total_equity"] = 100000

    feature_snapshot = pd.DataFrame(
        [
            _feature_row("600010.sh", "defensive_dividend", "银行", 85.0),
            _feature_row("600011.sh", "defensive_dividend", "银行", 70.0),
        ]
    )
    positions = pd.DataFrame(
        [
            {
                "symbol": "600011.sh",
                "name": "持有股",
                "current_position_tranches": 1,
                "current_weight": 0.03,
                "current_shares": 300,
                "avg_cost": 10.0,
                "extra_tranches": 0,
                "last_fill_price": 10.0,
            }
        ]
    )
    universe_cfg = {
        "rebalance_day": False,
        "stocks": [{"symbol": "600010.sh", "name": "池内股", "bucket": "defensive_dividend", "industry_l1": "银行", "main_metric": "pe_ttm", "final_score": 85.0}],
        "changes": [],
    }
    financials = pd.concat([_financial_history("600010.sh"), _financial_history("600011.sh")], ignore_index=True)
    report = prepare_daily_snapshot(
        as_of_date="2026-04-03",
        feature_snapshot=feature_snapshot,
        benchmark_frame=pd.DataFrame({"date": ["2026-04-03"], "close": [100]}),
        positions_frame=positions,
        financial_history=financials,
        strategy_cfg=strategy_cfg,
        metric_map_cfg=configs["metric_map"],
        universe_cfg=universe_cfg,
        universe_rules_cfg=universe_rules_cfg,
        account_cfg=account_cfg,
        data_errors=[],
        data_notes=[],
    )
    by_symbol = {item["symbol"]: item for item in report["decisions"]}
    assert set(by_symbol) == {"600010.sh", "600011.sh"}
    assert by_symbol["600011.sh"]["holding_state"] == "FROZEN"
    assert by_symbol["600011.sh"]["action_enum"] == "HOLD_FROZEN"


def test_force_exit_holding_sells_all(configs: dict) -> None:
    strategy_cfg = copy.deepcopy(configs["strategy"])
    universe_rules_cfg = copy.deepcopy(configs["universe_rules"])
    account_cfg = copy.deepcopy(configs["account"])
    account_cfg["account"]["current_cash"] = 100000
    account_cfg["account"]["latest_total_equity"] = 100000
    feature_snapshot = pd.DataFrame([_feature_row("600020.sh", "defensive_dividend", "银行", 88.0)])
    positions = pd.DataFrame(
        [
            {
                "symbol": "600020.sh",
                "name": "强退股",
                "current_position_tranches": 1,
                "current_weight": 0.03,
                "current_shares": 300,
                "avg_cost": 10.0,
                "extra_tranches": 0,
                "last_fill_price": 10.0,
            }
        ]
    )
    feature_snapshot.loc[0, "is_st"] = True
    financials = _financial_history("600020.sh", is_st=True)
    report = prepare_daily_snapshot(
        as_of_date="2026-04-03",
        feature_snapshot=feature_snapshot,
        benchmark_frame=pd.DataFrame({"date": ["2026-04-03"], "close": [100]}),
        positions_frame=positions,
        financial_history=financials,
        strategy_cfg=strategy_cfg,
        metric_map_cfg=configs["metric_map"],
        universe_cfg={"rebalance_day": False, "stocks": [{"symbol": "600020.sh", "bucket": "defensive_dividend", "industry_l1": "银行", "main_metric": "pe_ttm", "final_score": 88.0}]},
        universe_rules_cfg=universe_rules_cfg,
        account_cfg=account_cfg,
        data_errors=[],
        data_notes=[],
    )
    decision = report["decisions"][0]
    assert decision["holding_state"] == "FORCE_EXIT"
    assert decision["action_enum"] == "SELL_ALL"


def test_filter_reasons_use_special_value_status_without_misclassifying_as_missing(configs: dict) -> None:
    row = pd.Series(
        {
            "industry": "银行",
            "is_a_share": True,
            "is_st": False,
            "listed_days": 2000,
            "avg_amount_60d_million": 150.0,
            "market_cap_billion": 120.0,
            "latest_net_profit": 5.0,
            "roe": 10.0,
            "cfo_ttm": 5.0,
            "debt_to_assets": 55.0,
            "dv_ttm": 0.04,
            "pb": 1.2,
            "pb_rule_value": 1.2,
            "pb_rule_status": "ok",
            "pe_ttm": pd.NA,
            "pe_ttm_rule_value": -999999999.0,
            "pe_ttm_rule_status": "ttm_non_positive",
            "stock_pe_ttm_history_observations": pd.NA,
            "stock_pe_ttm_history_observations_rule_value": -999999999.0,
            "core_fields_complete": True,
        }
    )

    base_reasons = _base_filter_reasons(row, configs["universe_rules"], "pe_ttm", trading_days=252)
    bucket_reasons = _bucket_filter_reasons(row, "defensive_dividend", configs["universe_rules"], "pe_ttm")

    assert "core_fields_missing" not in base_reasons
    assert "pe_ttm_ttm_non_positive" in base_reasons
    assert "pe_ttm_ttm_non_positive" in bucket_reasons
