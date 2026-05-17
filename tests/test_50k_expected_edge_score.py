from __future__ import annotations

from src.strategy.score_50k_core import compute_50k_expected_edge_score


def _policy(**overrides) -> dict:
    policy = {
        "account_equity": 50_000,
        "cash_reserve_ratio": 0.10,
        "max_positions": 5,
        "round_lot": 100,
        "max_single_stock_weight": 0.16,
        "lot_notional_max_ratio_to_target_budget": 0.90,
        "industry_max_positions": 1,
        "industry_position_counts": {},
        "market_regime": "risk_on",
    }
    policy.update(overrides)
    return policy


def _decision(**overrides) -> dict:
    row = {
        "symbol": "600000.sh",
        "industry": "银行",
        "bucket": "defensive_dividend",
        "stock_q_blended": 15,
        "final_score": 82,
        "quality_pass": True,
        "roe": 0.13,
        "cfo_ttm": 1.0,
        "latest_net_profit": 1.0,
        "dv_ttm": 0.055,
        "close": 45,
        "ma60": 42,
        "ma120": 40,
        "ma20_slope_10d": 0.01,
        "ma120_slope_20d": 0.01,
    }
    row.update(overrides)
    return row


def test_defensive_low_valuation_high_quality_dividend_scores_higher() -> None:
    strong = compute_50k_expected_edge_score(_decision(), _policy())
    weak = compute_50k_expected_edge_score(
        _decision(stock_q_blended=80, final_score=35, quality_pass=False, dv_ttm=0.005),
        _policy(),
    )

    assert strong["expected_edge_score"] > weak["expected_edge_score"]
    assert strong["score_components"]["valuation_depth"] > weak["score_components"]["valuation_depth"]
    assert strong["lot_fit_status"] == "FIT"


def test_trend_break_reduces_score() -> None:
    good = compute_50k_expected_edge_score(_decision(close=45, ma60=42, ma120=40, ma20_slope_10d=0.02, ma120_slope_20d=0.01), _policy())
    bad = compute_50k_expected_edge_score(_decision(close=35, ma60=42, ma120=40, ma20_slope_10d=-0.02, ma120_slope_20d=-0.01), _policy())

    assert bad["score_components"]["trend_confirmation"] < good["score_components"]["trend_confirmation"]
    assert bad["expected_edge_score"] < good["expected_edge_score"]


def test_missing_relative_strength_is_neutral_not_error() -> None:
    result = compute_50k_expected_edge_score(_decision(), _policy())

    assert result["score_components"]["relative_strength"] == 50.0


def test_lot_fit_marks_structural_block_above_single_name_cap() -> None:
    result = compute_50k_expected_edge_score(_decision(close=90), _policy(max_single_stock_weight=0.16))

    assert result["lot_notional"] == 9_000
    assert result["structural_lot_block"] is True
    assert result["lot_fit_status"] == "STRUCTURAL_BLOCK"


def test_lot_fit_no_penalty_below_budget_and_penalty_above_budget() -> None:
    fit = compute_50k_expected_edge_score(_decision(close=70), _policy(max_positions=5, cash_reserve_ratio=0.10))
    stretched = compute_50k_expected_edge_score(_decision(close=88), _policy(max_positions=5, cash_reserve_ratio=0.10, max_single_stock_weight=0.20))

    assert fit["score_components"]["lot_fit_penalty"] == 0.0
    assert stretched["score_components"]["lot_fit_penalty"] > 0.0
    assert stretched["lot_fit_status"] == "STRETCHED"


def test_cyclical_non_risk_on_is_watch_only() -> None:
    result = compute_50k_expected_edge_score(
        _decision(bucket="cyclical_rotation", close=45, ma60=42, ma20_slope_10d=0.02, cycle_peak_trap=False),
        _policy(market_regime="neutral"),
    )

    assert result["cyclical_executable"] is False
    assert "CYCLICAL_NOT_RISK_ON" in result["watch_only_reasons"]
