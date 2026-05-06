from __future__ import annotations

import copy

import pandas as pd

from src.strategy.grid import compute_grid_step
from src.strategy.signals import SignalEngine
from src.strategy.universe import build_candidate_pool
from src.utils.config import load_yaml


def _v2_configs(configs: dict) -> tuple[dict, dict, dict]:
    strategy_cfg = load_yaml("config/strategy_v2.yml")
    universe_rules_cfg = load_yaml("config/universe_rules_v2.yml")
    account_cfg = copy.deepcopy(configs["account"])
    account_cfg["account"]["current_cash"] = 200000
    account_cfg["account"]["latest_total_equity"] = 200000
    account_cfg["execution"]["round_lot"] = 1
    account_cfg["position_sizing"]["min_trade_value"] = 0
    strategy_cfg["execution"]["lot_aware_sizing"] = False
    strategy_cfg["execution"]["pending_add_state"] = False
    strategy_cfg["execution"]["duplicate_blocked_signal_suppression"] = False
    return strategy_cfg, universe_rules_cfg, account_cfg


def _row(bucket: str = "defensive_dividend") -> dict:
    cyc = bucket == "cyclical_rotation"
    return {
        "symbol": "600000.sh" if not cyc else "600111.sh",
        "name": "测试股",
        "industry": "银行" if not cyc else "有色金属",
        "bucket": bucket,
        "close": 10.0,
        "ma20": 9.8,
        "ma60": 9.5,
        "ma120": 10.5,
        "ma200": 9.0,
        "ma250": 9.5,
        "atr20": 0.5,
        "ma20_slope_10d": 0.02,
        "ma60_slope_20d": 0.01,
        "ma120_slope_20d": 0.01,
        "stock_q_blended": 20.0,
        "industry_q_blended": 25.0,
        "stock_pb_q_blended": 20.0,
        "industry_pb_q_blended": 25.0,
        "dv_ttm": 0.05,
        "latest_net_profit": 10.0,
        "quality_pass": True,
        "thesis_still_valid": True,
        "core_fields_complete": True,
        "cycle_peak_trap": False,
        "fundamental_break": False,
        "data_stale": False,
        "in_effective_universe": True,
        "holding_state": "NONE",
        "current_position_tranches": 0,
        "current_weight": 0.0,
        "current_shares": 0,
        "avg_cost": 10.0,
        "last_fill_price": 11.0,
        "holding_days": 80,
        "days_since_last_buy": 30,
        "unrealized_pnl_pct": 0.0,
        "final_score": 80.0,
        "universe_final_score": 80.0,
    }


def _generate_one(strategy_cfg: dict, universe_rules_cfg: dict, account_cfg: dict, row: dict, max_total: float = 0.95) -> dict:
    engine = SignalEngine(strategy_cfg, universe_rules_cfg, account_cfg)
    decisions = engine.generate(
        pd.DataFrame([row]),
        pd.DataFrame(
            [
                {
                    "symbol": row["symbol"],
                    "current_position_tranches": row.get("current_position_tranches", 0),
                    "current_weight": row.get("current_weight", 0.0),
                    "current_shares": row.get("current_shares", 0),
                    "avg_cost": row.get("avg_cost", 10.0),
                    "extra_tranches": 0,
                    "last_fill_price": row.get("last_fill_price", 10.0),
                    "holding_days": row.get("holding_days", 0),
                    "days_since_last_buy": row.get("days_since_last_buy", 0),
                }
            ]
        )
        if row.get("current_position_tranches", 0)
        else pd.DataFrame(columns=["symbol", "current_position_tranches", "current_weight", "current_shares", "avg_cost", "extra_tranches", "last_fill_price"]),
        {"regime": "risk_on", "max_total_position": max_total},
        account_state={"current_cash": 200000, "reserved_cash": 0, "latest_total_equity": 200000, "current_invested_value": row.get("current_weight", 0.0) * 200000},
    )
    return decisions[0]


def test_v2_frozen_holding_is_not_sold_only_because_removed_from_universe(configs: dict) -> None:
    strategy_cfg, universe_rules_cfg, account_cfg = _v2_configs(configs)
    row = _row()
    row.update({"holding_state": "FROZEN", "in_effective_universe": False, "current_position_tranches": 1, "current_weight": 0.04, "current_shares": 800})
    decision = _generate_one(strategy_cfg, universe_rules_cfg, account_cfg, row)
    assert decision["action_enum"] == "HOLD_FROZEN"


def test_v2_soft_sell_all_respects_min_holding_days(configs: dict) -> None:
    strategy_cfg, universe_rules_cfg, account_cfg = _v2_configs(configs)
    row = _row()
    row.update({"current_position_tranches": 2, "current_weight": 0.08, "current_shares": 1600, "holding_state": "ACTIVE", "holding_days": 20, "stock_q_blended": 95.0, "industry_q_blended": 95.0, "close": 12.0, "ma120": 10.0})
    decision = _generate_one(strategy_cfg, universe_rules_cfg, account_cfg, row)
    assert decision["action_enum"] == "HOLD"


def test_v2_hard_exit_ignores_min_holding_days(configs: dict) -> None:
    strategy_cfg, universe_rules_cfg, account_cfg = _v2_configs(configs)
    row = _row()
    row.update({"current_position_tranches": 1, "current_weight": 0.04, "current_shares": 800, "holding_state": "ACTIVE", "holding_days": 5, "fundamental_break": True})
    decision = _generate_one(strategy_cfg, universe_rules_cfg, account_cfg, row)
    assert decision["action_enum"] == "SELL_ALL"


def test_v2_pb_bucket_keeps_pe_missing_when_pb_is_valid(configs: dict) -> None:
    universe_rules_cfg = load_yaml("config/universe_rules_v2.yml")
    row = pd.DataFrame(
        [
            {
                "symbol": "600111.sh",
                "name": "周期股",
                "industry": "有色金属",
                "is_a_share": True,
                "is_st": False,
                "listed_days": 1600,
                "avg_amount_60d_million": 100,
                "market_cap_billion": 500,
                "latest_net_profit": 10,
                "roe": 5,
                "pb": 1.0,
                "pe_ttm": pd.NA,
                "stock_pb_q_blended": 20,
                "industry_pb_q_blended": 30,
                "market_cap_percentile": 80,
                "avg_amount_60d_percentile": 70,
                "industry_market_cap_rank": 3,
                "industry_market_cap_percentile": 0.1,
                "cycle_peak_trap": False,
                "cfo_ttm": 1,
                "debt_to_assets": 50,
            }
        ]
    )
    pool = build_candidate_pool(row, universe_rules_cfg, configs["metric_map"], "2026-04-03")
    assert "600111.sh" in set(pool["symbol"])


def test_v2_financial_industry_does_not_hard_filter_debt_or_missing_cfo(configs: dict) -> None:
    universe_rules_cfg = load_yaml("config/universe_rules_v2.yml")
    row = pd.DataFrame(
        [
            {
                "symbol": "600000.sh",
                "name": "银行股",
                "industry": "银行",
                "is_a_share": True,
                "is_st": False,
                "listed_days": 2000,
                "avg_amount_60d_million": 100,
                "market_cap_billion": 800,
                "latest_net_profit": 10,
                "roe": 8,
                "dv_ttm": 0.04,
                "pb": 0.8,
                "pe_ttm": pd.NA,
                "stock_pb_q_blended": 35,
                "industry_pb_q_blended": 45,
                "market_cap_percentile": 90,
                "avg_amount_60d_percentile": 80,
                "industry_market_cap_rank": 1,
                "industry_market_cap_percentile": 0.05,
                "cycle_peak_trap": False,
                "cfo_ttm": pd.NA,
                "debt_to_assets": 91,
            }
        ]
    )
    pool = build_candidate_pool(row, universe_rules_cfg, configs["metric_map"], "2026-04-03")
    assert "600000.sh" in set(pool["symbol"])


def test_v2_cycle_peak_trap_blocks_cyclical_open_and_add(configs: dict) -> None:
    strategy_cfg, universe_rules_cfg, account_cfg = _v2_configs(configs)
    row = _row("cyclical_rotation")
    row["cycle_peak_trap"] = True
    decision = _generate_one(strategy_cfg, universe_rules_cfg, account_cfg, row)
    assert decision["action_enum"] == "BLOCKED"
    row.update({"current_position_tranches": 1, "current_weight": 0.03, "current_shares": 600, "holding_state": "ACTIVE"})
    held_decision = _generate_one(strategy_cfg, universe_rules_cfg, account_cfg, row)
    assert held_decision["action_enum"] != "BUY_2"


def test_v2_grid_step_is_clipped(configs: dict) -> None:
    strategy_cfg, _, _ = _v2_configs(configs)
    grid_cfg = strategy_cfg["execution"]["grid_execution"]
    assert compute_grid_step(atr20=0.01, close=10.0, grid_cfg=grid_cfg) == 0.035
    assert compute_grid_step(atr20=1.0, close=10.0, grid_cfg=grid_cfg) == 0.08


def test_v2_buy_levels_map_to_bucket_tranche_weights(configs: dict) -> None:
    strategy_cfg, universe_rules_cfg, account_cfg = _v2_configs(configs)
    buy1 = _generate_one(strategy_cfg, universe_rules_cfg, account_cfg, _row())
    assert buy1["action_enum"] == "BUY_1"
    assert buy1["target_weight"] == 0.04
    row2 = _row()
    row2.update({"current_position_tranches": 1, "current_weight": 0.04, "current_shares": 800, "holding_state": "ACTIVE", "close": 9.0, "stock_q_blended": 20.0, "industry_q_blended": 25.0})
    buy2 = _generate_one(strategy_cfg, universe_rules_cfg, account_cfg, row2)
    assert buy2["action_enum"] == "BUY_2"
    assert buy2["desired_target_weight"] == 0.08
    row3 = _row()
    row3.update({"current_position_tranches": 2, "current_weight": 0.08, "current_shares": 1600, "holding_state": "ACTIVE", "close": 9.0, "stock_q_blended": 15.0, "industry_q_blended": 20.0})
    buy3 = _generate_one(strategy_cfg, universe_rules_cfg, account_cfg, row3)
    assert buy3["action_enum"] == "BUY_3"
    assert buy3["desired_target_weight"] == 0.12


def test_v2_market_regime_exposure_cap_blocks_buy(configs: dict) -> None:
    strategy_cfg, universe_rules_cfg, account_cfg = _v2_configs(configs)
    decision = _generate_one(strategy_cfg, universe_rules_cfg, account_cfg, _row(), max_total=0.02)
    assert decision["action_enum"] == "BLOCKED"
    assert decision["blocked_reason"] == "REGIME_CAP_BLOCK"


def test_v2_lot_size_and_min_trade_amount_block_zero_order(configs: dict) -> None:
    strategy_cfg, universe_rules_cfg, account_cfg = _v2_configs(configs)
    account_cfg["execution"]["round_lot"] = 100
    account_cfg["position_sizing"]["min_trade_value"] = 5000
    row = _row()
    row["close"] = 10000
    row["ma120"] = 11000
    decision = _generate_one(strategy_cfg, universe_rules_cfg, account_cfg, row)
    assert decision["action_enum"] == "BLOCKED"
    assert decision["blocked_reason"] in {"ROUND_LOT_BLOCK", "MIN_TRADE_VALUE"}
