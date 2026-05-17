from __future__ import annotations

from src.strategy.deployment_repair import compute_winner_add_candidate


def _holding(**overrides):
    base = {
        "symbol": "600036.sh",
        "industry": "银行",
        "bucket": "defensive_dividend",
        "shares": 100,
        "current_weight": 0.12,
        "unrealized_pnl_pct": 0.05,
        "close": 12.0,
        "ma60": 11.5,
        "ma120": 11.0,
        "ma20_slope_10d": 0.002,
        "thesis_still_valid": True,
        "fundamental_break": False,
        "structural_lot_block": False,
    }
    base.update(overrides)
    return base


def _state(**overrides):
    base = {
        "market_regime": "risk_on",
        "cash_ratio": 0.38,
        "positions_count": 4,
        "winner_adds_this_month": 0,
        "group_cap_result": {"allowed": True},
    }
    base.update(overrides)
    return base


def _cfg(max_weight: float = 0.16):
    return {"enabled": True, "max_single_stock_weight": max_weight, "max_extra_lots_per_symbol": 1, "max_adds_per_month": 1}


def test_winner_add_only_adds_profitable_existing_risk_on_holding() -> None:
    assert compute_winner_add_candidate(_holding(), _state(), _cfg())["eligible"] is True
    assert compute_winner_add_candidate(_holding(unrealized_pnl_pct=-0.01), _state(), _cfg())["eligible"] is False
    assert compute_winner_add_candidate(_holding(shares=0), _state(), _cfg())["eligible"] is False
    assert compute_winner_add_candidate(_holding(), _state(market_regime="neutral"), _cfg())["eligible"] is False


def test_winner_add_blocks_average_down_weight_and_group_cap() -> None:
    assert "MAX_SINGLE_STOCK_WEIGHT" in compute_winner_add_candidate(_holding(current_weight=0.17), _state(), _cfg())["fail_reasons"]
    assert "GROUP_CAP" in compute_winner_add_candidate(_holding(), _state(group_cap_result={"allowed": False}), _cfg())["fail_reasons"]
    assert "TREND_NOT_CONFIRMED" in compute_winner_add_candidate(_holding(close=10.0), _state(), _cfg())["fail_reasons"]
