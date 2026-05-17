from __future__ import annotations

from src.strategy.deployment_repair import compute_quality_defensive_fill_candidate


def _decision(**overrides):
    base = {
        "symbol": "600036.sh",
        "bucket": "defensive_dividend",
        "industry": "银行",
        "market_regime": "risk_on",
        "cash_ratio": 0.42,
        "has_executable_stock_buy": False,
        "in_effective_universe": True,
        "quality_pass": True,
        "fundamental_break": False,
        "data_stale": False,
        "core_fields_complete": True,
        "lot_fit_status": "OK",
        "structural_lot_block": False,
        "final_score": 70,
        "expected_edge_score": 78,
        "stock_q_blended": 35,
        "industry_q_blended": 52,
        "dv_ttm": 0.025,
        "close": 10.5,
        "ma60": 10.0,
        "ma120": 10.2,
        "ma20_slope_10d": 0.001,
    }
    base.update(overrides)
    return base


def _cfg(profile: str = "strict"):
    return {
        "enabled": True,
        "threshold_profile": profile,
        "thresholds": {
            "strict": {
                "final_score_min": 65,
                "stock_q_blended_max": 45,
                "industry_q_blended_max": 60,
                "dv_ttm_min": 0.020,
                "close_to_ma120_max": 1.08,
                "ma20_slope_10d_min": -0.005,
            },
            "balanced": {
                "final_score_min": 60,
                "stock_q_blended_max": 55,
                "industry_q_blended_max": 70,
                "dv_ttm_min": 0.015,
                "close_to_ma120_max": 1.12,
                "ma20_slope_10d_min": -0.010,
            },
        },
    }


def test_quality_defensive_fill_requires_risk_on_high_cash_and_no_stock_buy() -> None:
    assert compute_quality_defensive_fill_candidate(_decision(), {}, _cfg())["eligible"] is True
    assert compute_quality_defensive_fill_candidate(_decision(market_regime="neutral"), {}, _cfg())["eligible"] is False
    assert compute_quality_defensive_fill_candidate(_decision(cash_ratio=0.30), {}, _cfg())["eligible"] is False
    assert compute_quality_defensive_fill_candidate(_decision(has_executable_stock_buy=True), {}, _cfg())["eligible"] is False


def test_quality_defensive_fill_blocks_cyclical_fundamental_and_lot_failures() -> None:
    for patch in [
        {"bucket": "cyclical_rotation"},
        {"fundamental_break": True},
        {"structural_lot_block": True},
        {"quality_pass": False},
        {"data_stale": True},
    ]:
        result = compute_quality_defensive_fill_candidate(_decision(**patch), {}, _cfg())
        assert result["eligible"] is False
        assert result["action_label"] == "WATCH_ONLY_DEFENSIVE_FILL_BLOCKED"


def test_quality_defensive_fill_strict_and_balanced_thresholds_are_configurable() -> None:
    borderline = _decision(final_score=62, stock_q_blended=50, industry_q_blended=65, dv_ttm=0.018, ma20_slope_10d=-0.008)

    strict = compute_quality_defensive_fill_candidate(borderline, {}, _cfg("strict"))
    balanced = compute_quality_defensive_fill_candidate(borderline, {}, _cfg("balanced"))

    assert strict["eligible"] is False
    assert balanced["eligible"] is True
