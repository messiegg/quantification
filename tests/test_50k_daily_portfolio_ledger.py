from __future__ import annotations

import pandas as pd

from tests.test_50k_core_trace_generation import make_trace_bundle


def test_daily_portfolio_ledger_reconciles_nav_cash_and_trade_counts() -> None:
    bundle = make_trace_bundle()
    daily = bundle.daily_portfolio_ledger
    trades = bundle.trade_ledger

    calc_return = daily["nav"] / daily["previous_nav"] - 1.0
    assert (calc_return - daily["daily_return"]).abs().max() < 1e-12
    assert (daily["cash"] / daily["nav"] - daily["cash_ratio"]).abs().max() < 1e-12
    assert (daily["gross_exposure"] - (1.0 - daily["cash_ratio"])).abs().max() < 1e-12

    by_signal_date = trades.groupby("signal_date")["side"].apply(lambda values: values.astype(str).str.contains("BUY").sum())
    merged = daily.set_index("date")
    for date, count in by_signal_date.items():
        assert int(merged.loc[date, "buy_count_today"]) == int(count)


def test_daily_portfolio_ledger_has_no_non_positive_nav() -> None:
    daily = make_trace_bundle().daily_portfolio_ledger

    assert (pd.to_numeric(daily["nav"], errors="coerce") > 0).all()
    assert {"trace_quality_flag", "risk_on_cash_drag_reason"} <= set(daily.columns)
