from __future__ import annotations

from tests.test_50k_core_trace_generation import make_trace_bundle


def test_drawdown_attribution_identifies_window_and_contribution_sum() -> None:
    bundle = make_trace_bundle()
    drawdown = bundle.drawdown_attribution_trace

    assert drawdown.iloc[0]["start_date"] == "2025-01-01"
    assert drawdown.iloc[0]["trough_date"] == "2025-01-02"
    assert abs(drawdown["pnl_contribution_during_drawdown"].sum() + 500) < 1e-9


def test_drawdown_trace_keeps_missing_quality_flag_when_unavailable() -> None:
    drawdown = make_trace_bundle().drawdown_attribution_trace

    assert "trace_quality_flag" in drawdown.columns
    assert drawdown["symbol"].notna().all()
