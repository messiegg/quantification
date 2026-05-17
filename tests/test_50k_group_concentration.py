from __future__ import annotations

from src.strategy.deployment_repair import evaluate_group_concentration


def _cfg():
    return {
        "enabled": True,
        "financial_max_positions": 1,
        "financial_max_weight": 0.30,
        "utility_max_positions": 1,
        "utility_max_weight": 0.20,
    }


def test_financial_group_combines_bank_and_nonbank() -> None:
    state = {
        "positions": [
            {"symbol": "600036.sh", "industry": "银行", "weight": 0.16},
        ]
    }
    result = evaluate_group_concentration(state, {"symbol": "601318.sh", "industry": "非银金融", "weight_after_buy": 0.16}, _cfg())

    assert result["allowed"] is False
    assert result["blocked_reason"] == "WATCH_ONLY_GROUP_CONCENTRATION"
    assert result["group"] == "financial"
    assert result["group_current_positions"] == 1


def test_utility_group_is_limited_separately_without_forced_sells() -> None:
    state = {"positions": [{"symbol": "600803.sh", "industry": "公用事业", "weight": 0.18}]}
    result = evaluate_group_concentration(state, {"symbol": "600900.sh", "industry": "公用事业", "weight_after_buy": 0.08}, _cfg())

    assert result["allowed"] is False
    assert result["do_not_force_sell_existing"] is True
    assert result["group"] == "defensive_utility"
