from __future__ import annotations

from scripts.run_50k_core_experiments import CoreParams
from scripts.generate_50k_core_traces import _exit_row
from src.strategy.backtest_engine import Position
from tests.test_50k_core_trace_generation import make_trace_bundle


def test_exit_rule_trace_has_bool_fields_and_disabled_trend_stop_would_have_triggered() -> None:
    exit_trace = make_trace_bundle().exit_rule_trace

    required_bool = [
        "valuation_reversion_exit_triggered",
        "soft_trim_triggered",
        "trend_stop_triggered",
        "partial_derisk_triggered",
        "cycle_peak_trap_trend_break_triggered",
        "replacement_sell_triggered",
        "force_exit_triggered",
    ]
    for col in required_bool:
        assert col in exit_trace.columns
    assert exit_trace["would_have_triggered_trend_stop"].any()
    assert exit_trace["trend_stop_disabled_by_profile"].any()


def test_partial_derisk_single_lot_exit_row_does_not_create_half_lot() -> None:
    params = CoreParams(
        max_positions=5,
        max_tranches=1,
        target_universe_size=8,
        cash_reserve_ratio=0.1,
        max_single_stock_weight=0.18,
        max_new_positions_per_day=1,
        max_adds_per_day=0,
        industry_max_positions=2,
        defensive_core_min_positions=3,
        cyclical_max_positions=0,
        lot_notional_max_ratio_to_target_budget=1.0,
        score_gap_threshold=8,
        max_replacements_per_month=1,
        risk_on_target_exposure=0.85,
        neutral_target_exposure=0.6,
        risk_off_target_exposure=0.25,
        partial_derisk_enabled=True,
    )
    row = _exit_row(
        date="2025-01-01",
        params=params,
        symbol="600000.sh",
        position=Position(symbol="600000.sh", industry="银行", bucket="defensive_dividend", shares=100, avg_cost=120, entry_index=0),
        decision={"close": 100, "ma120": 110, "ma20_slope_10d": -0.01, "relative_strength": -0.1, "action_enum": "HOLD"},
        regime_name="risk_on",
        nav=50000,
        current_index=10,
    )

    assert row["reduce_or_sell_shares"] in {0, 100}
    assert row["reduce_or_sell_shares"] % 100 == 0
