from __future__ import annotations

import pandas as pd

from src.strategy.deployment_repair import evaluate_cash_sleeve_research


def test_cash_sleeve_without_etf_data_outputs_feasibility_only() -> None:
    result = evaluate_cash_sleeve_research(
        {"market_regime": "risk_on", "cash_ratio": 0.40, "no_executable_stock_buy": True, "no_quality_defensive_fill": True, "no_winner_add": True},
        {},
        {},
    )

    assert result["cash_sleeve_data_available"] is False
    assert result["cash_sleeve_trades"] == []
    assert result["cash_sleeve_trades_count"] == 0


def test_cash_sleeve_with_data_is_research_only_and_separately_attributed() -> None:
    result = evaluate_cash_sleeve_research(
        {"market_regime": "risk_on", "cash_ratio": 0.40, "no_executable_stock_buy": True, "no_quality_defensive_fill": True, "no_winner_add": True},
        {"510300": pd.DataFrame([{"date": "2025-01-02", "close": 4.0}])},
        {"max_weight_risk_on": 0.15, "cash": 20_000, "nav": 50_000, "round_lot": 100},
    )

    assert result["cash_sleeve_data_available"] is True
    assert result["cash_sleeve_trades"][0]["action_label"] == "BUY_CASH_SLEEVE_RESEARCH"
    assert result["cash_sleeve_trades"][0]["diagnostic_label"] == "CASH_SLEEVE_RESEARCH_ONLY"
    assert result["live_approval"] is False
