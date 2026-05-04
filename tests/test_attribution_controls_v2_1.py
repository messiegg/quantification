from __future__ import annotations

import copy

import pandas as pd

from scripts.audit_backtest_integrity import _audit_status, _close
from scripts.run_backtest_attribution import (
    build_daily_regime_attribution,
    build_monthly_returns,
    build_position_attribution,
    build_signal_attribution,
)
from scripts.run_backtest_controls import _random_selections, _run_v2_variant
from src.strategy.backtest_engine import BacktestResult
from src.utils.config import load_yaml


def test_monthly_returns_chain_matches_final_nav() -> None:
    nav = pd.DataFrame(
        [
            {"date": "2024-01-31", "nav": 110.0, "exposure": 0.5, "holdings_count": 2},
            {"date": "2024-02-29", "nav": 121.0, "exposure": 0.4, "holdings_count": 2},
        ]
    )
    _, check = build_monthly_returns(nav, initial_capital=100.0)
    assert abs(float(check["cumulative_return_from_monthly_chain"].iloc[-1]) - 0.21) < 1e-12
    assert abs(float(check["diff"].iloc[-1])) < 1e-12


def test_open_position_holding_days_count_to_backtest_end() -> None:
    trades = pd.DataFrame(
        [
            {
                "date": "2026-04-01",
                "ts_code": "600000.sh",
                "side": "BUY",
                "shares": 100.0,
                "position_before": 0.0,
                "position_after": 100.0,
                "realized_pnl": 0.0,
                "weight_after": 0.1,
                "bucket": "defensive_dividend",
                "industry": "银行",
                "name": "测试",
                "price": 10.0,
            }
        ]
    )
    final_positions = pd.DataFrame(
        [{"symbol": "600000.sh", "bucket": "defensive_dividend", "industry": "银行", "avg_cost": 10.0, "unrealized_pnl": 50.0}]
    )
    features = pd.DataFrame(
        [
            {"date": "2026-04-01", "symbol": "600000.sh", "close": 10.0},
            {"date": "2026-04-02", "symbol": "600000.sh", "close": 10.2},
            {"date": "2026-04-03", "symbol": "600000.sh", "close": 10.5},
        ]
    )
    attr = build_position_attribution(trades, final_positions, features, ["2026-04-01", "2026-04-02", "2026-04-03"])
    row = attr.iloc[0]
    assert bool(row["is_open_position"])
    assert int(row["holding_days_total"]) == 3
    assert int(row["open_position_days"]) == 3


def test_signal_attribution_assigns_buy_levels_to_pnl() -> None:
    trades = pd.DataFrame(
        [
            {"date": "2024-01-02", "ts_code": "600000.sh", "side": "BUY", "action": "BUY_1", "signal_level": "BUY_1", "shares": 100.0, "price": 10.0, "realized_pnl": 0.0, "bucket": "defensive_dividend", "industry": "银行"},
            {"date": "2024-01-03", "ts_code": "600000.sh", "side": "BUY", "action": "BUY_2", "signal_level": "BUY_2", "shares": 100.0, "price": 9.0, "realized_pnl": 0.0, "bucket": "defensive_dividend", "industry": "银行"},
            {"date": "2024-01-05", "ts_code": "600000.sh", "side": "SELL", "action": "SELL_ALL", "signal_level": "SELL_ALL", "shares": 200.0, "price": 12.0, "realized_pnl": 500.0, "exit_reason": "valuation_reversion_exit", "bucket": "defensive_dividend", "industry": "银行"},
        ]
    )
    attr = build_signal_attribution(trades, pd.DataFrame(), ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"])
    entry = attr[attr["attribution_type"] == "entry_signal"].set_index("entry_signal_level")
    assert float(entry.loc["BUY_1", "total_pnl"]) > 0
    assert float(entry.loc["BUY_2", "total_pnl"]) > 0


def test_daily_mtm_regime_pnl_sums_to_nav_change(configs: dict) -> None:
    result = BacktestResult(
        metrics={},
        nav=pd.DataFrame(
            [
                {"date": "2024-01-02", "nav": 101.0, "cash": 101.0, "exposure": 0.0, "holdings_count": 0},
                {"date": "2024-01-03", "nav": 103.0, "cash": 103.0, "exposure": 0.0, "holdings_count": 0},
            ]
        ),
        trade_list=pd.DataFrame(),
        stock_attribution=pd.DataFrame(),
        industry_attribution=pd.DataFrame(),
        trades_detailed=pd.DataFrame(),
        final_cash=103.0,
        final_positions=pd.DataFrame(),
    )
    features = pd.DataFrame([{"date": "2024-01-02", "symbol": "600000.sh", "close": 10.0}, {"date": "2024-01-03", "symbol": "600000.sh", "close": 10.0}])
    benchmark = pd.DataFrame([{"date": "2024-01-02", "close": 100.0}, {"date": "2024-01-03", "close": 101.0}])
    daily, _ = build_daily_regime_attribution(result, features, benchmark, configs["strategy"], initial_capital=100.0)
    assert abs(float(daily["daily_pnl"].sum()) - 3.0) < 1e-12


def test_control_variant_does_not_mutate_strategy_config(monkeypatch) -> None:
    class FakeEngine:
        def __init__(self, strategy, **kwargs):
            strategy.setdefault("control_overrides", {})["mutated_by_fake"] = True

        def run(self, features, benchmark, bucket):
            return BacktestResult({}, pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame())

    monkeypatch.setattr("scripts.run_backtest_controls.BacktestEngine", FakeEngine)
    configs = {"v2_strategy": {"profile": "combined_v2"}, "v2_universe": {}, "account": {}}
    before = copy.deepcopy(configs["v2_strategy"])
    _run_v2_variant(configs, pd.DataFrame(), pd.DataFrame(), "v2_no_grid", {"disable_grid": True})
    assert configs["v2_strategy"] == before


def test_random_placebo_selection_is_seed_reproducible() -> None:
    candidates = {"2024-01-02": [{"symbol": str(index)} for index in range(10)]}
    counts = {"2024-01-02": 4}
    assert _random_selections(candidates, 7, counts) == _random_selections(candidates, 7, counts)
    assert _random_selections(candidates, 7, counts) != _random_selections(candidates, 8, counts)


def test_v2_1_risk_guard_keeps_combined_v2_config_separate() -> None:
    v2 = load_yaml("config/strategy_v2.yml")
    guard = load_yaml("config/strategy_v2_1_risk_guard.yml")
    assert v2["profile"] == "combined_v2"
    assert guard["profile"] == "combined_v2_1_risk_guard"
    assert guard["control_overrides"]["risk_guard"] is True
    assert "control_overrides" not in v2


def test_legacy_result_no_longer_drives_current_integrity_status() -> None:
    assert _audit_status([{"check_id": "INT-012-LEGACY", "status": "WARN"}]) == "PASS"


def test_current_pit_strict_expected_values_are_recognized() -> None:
    assert _close(0.071352, 0.0714, 0.003)
    assert _close(-0.093645, -0.0936, 0.005)


def test_attribution_helpers_do_not_mutate_inputs() -> None:
    nav = pd.DataFrame([{"date": "2024-01-31", "nav": 101.0, "exposure": 0.0, "holdings_count": 0}])
    before = nav.copy(deep=True)
    build_monthly_returns(nav, 100.0)
    pd.testing.assert_frame_equal(nav, before)
