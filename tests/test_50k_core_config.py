from __future__ import annotations

from src.utils.config import load_yaml


def test_50k_core_config_is_research_only_and_safe() -> None:
    cfg = load_yaml("config/strategy_v2_50k_core.yml")

    assert cfg["profile_name"] == "combined_v2_50k_core"
    assert cfg["research_only"] is True
    assert cfg["base_strategy_config"] == "config/strategy_v2.yml"
    assert cfg["base_account_profile"] == "retail_50k_lot_aware"
    assert cfg["release_profile_replacement"] is False

    safety = cfg["safety"]
    assert safety["long_only"] is True
    assert safety["manual_execution_only"] is True
    assert safety["auto_trading_approved"] is False
    assert safety["broker_integration_enabled"] is False
    assert safety["llm_decision_allowed"] is False
    assert safety["writes_real_trades"] is False


def test_50k_core_config_contains_required_grids_and_cash_sleeve_disabled() -> None:
    cfg = load_yaml("config/strategy_v2_50k_core.yml")

    assert cfg["account"] == {"capital": 50_000, "round_lot": 100, "min_trade_value": 1_500}
    assert cfg["portfolio"]["max_positions_grid"] == [5, 6]
    assert cfg["portfolio"]["max_tranches_grid"] == [1]
    assert cfg["portfolio"]["max_adds_per_day_grid"] == [0]
    assert cfg["portfolio"]["target_universe_size_grid"] == [8, 10, 12]
    assert cfg["lot_fit"]["enabled"] is True
    assert cfg["replacement"]["backtest_switch_plan_enabled"] is True
    assert cfg["cash_sleeve"]["enabled"] is False
    assert cfg["cash_sleeve"]["research_only"] is True
    assert cfg["cash_sleeve"]["allowed_instruments"] == []
