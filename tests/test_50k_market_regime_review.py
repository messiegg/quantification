from __future__ import annotations

from src.strategy.deployment_repair import evaluate_market_regime_review_fill


def _decision(**overrides):
    base = {
        "market_regime": "neutral",
        "bucket": "defensive_dividend",
        "is_quality_defensive_fill": True,
        "cash_ratio": 0.40,
        "final_score": 70,
        "stock_q_blended": 35,
        "close": 11.0,
        "ma60": 10.5,
        "fundamental_break": False,
        "lot_fit_status": "OK",
    }
    base.update(overrides)
    return base


def test_market_regime_review_never_allows_risk_off_or_cyclical() -> None:
    assert evaluate_market_regime_review_fill(_decision(market_regime="risk_off"), {})["allowed"] is False
    assert evaluate_market_regime_review_fill(_decision(bucket="cyclical_rotation"), {})["allowed"] is False


def test_market_regime_review_allows_only_strict_neutral_defensive_fill() -> None:
    allowed = evaluate_market_regime_review_fill(_decision(), {})
    blocked = evaluate_market_regime_review_fill(_decision(final_score=67), {})

    assert allowed["allowed"] is True
    assert allowed["action_label"] == "BUY_REGIME_REVIEW_FILL"
    assert blocked["allowed"] is False
