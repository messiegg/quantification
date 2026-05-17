from __future__ import annotations

from src.execution.partial_derisk import evaluate_partial_derisk


def _holding(**overrides) -> dict:
    row = {
        "symbol": "600000.sh",
        "shares": 300,
        "round_lot": 100,
        "unrealized_pnl_pct": -0.09,
        "close": 9,
        "ma120": 10,
        "relative_strength": -3,
        "ma20_slope_10d": -0.01,
    }
    row.update(overrides)
    return row


def test_partial_derisk_reduces_only_round_lots() -> None:
    result = evaluate_partial_derisk(_holding(shares=300))

    assert result["action"] == "REDUCE"
    assert result["sell_shares"] % 100 == 0
    assert result["sell_shares"] == 100


def test_partial_derisk_single_lot_has_explicit_action() -> None:
    result = evaluate_partial_derisk(_holding(shares=100))

    assert result["action"] in {"SELL_ALL", "HOLD_WITH_RISK_FLAG"}
    assert result["sell_shares"] in {0, 100}


def test_partial_derisk_does_not_fire_without_trend_or_rs_confirmation() -> None:
    result = evaluate_partial_derisk(_holding(relative_strength=5, ma20_slope_10d=0.02))

    assert result["action"] == "HOLD"
    assert result["sell_shares"] == 0
