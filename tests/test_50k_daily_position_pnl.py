from __future__ import annotations

from tests.test_50k_core_trace_generation import make_trace_bundle


def test_daily_position_pnl_reconciles_to_portfolio_total_pnl() -> None:
    bundle = make_trace_bundle()
    position = bundle.daily_position_pnl
    daily = bundle.daily_portfolio_ledger.set_index("date")

    by_day = position.groupby("date")["total_pnl_today"].sum()
    for date, value in by_day.items():
        assert abs(value - daily.loc[date, "total_pnl_today"]) < 1e-9


def test_position_pnl_has_valid_market_value_and_no_future_return_fields() -> None:
    position = make_trace_bundle().daily_position_pnl

    assert (position["shares"] >= 0).all()
    assert (position["market_value"] - position["shares"] * position["close"]).abs().max() < 1e-9
    assert not any(col.startswith("diagnostic_future_return") for col in position.columns)
