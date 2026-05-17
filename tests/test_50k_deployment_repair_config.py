from __future__ import annotations

from src.utils.config import load_yaml


def test_deployment_repair_config_is_research_only_and_safe() -> None:
    cfg = load_yaml("config/strategy_v2_50k_core_deployment_repair.yml")

    assert cfg["base_strategy_config"] == "config/strategy_v2.yml"
    assert cfg["base_50k_core_config"] == "config/strategy_v2_50k_core.yml"
    assert cfg["base_account_profile"] == "retail_50k_lot_aware"

    safety = cfg["safety"]
    assert safety["research_only"] is True
    assert safety["long_only"] is True
    assert safety["manual_execution_only"] is True
    assert safety["auto_trading_approved"] is False
    assert safety["broker_integration_enabled"] is False
    assert safety["llm_decision_allowed"] is False
    assert safety["writes_real_trades"] is False
    assert safety["release_profile_replacement"] is False


def test_deployment_repair_config_keeps_phase3_scope_and_caps_variants() -> None:
    cfg = load_yaml("config/strategy_v2_50k_core_deployment_repair.yml")
    repair = cfg["deployment_repair"]

    assert repair["enabled"] is True
    assert repair["max_variants"] == 24
    assert repair["hard_conditions_unchanged"] is True
    assert repair["source_diagnostics"]["use_phase3_traces"] is True
    assert repair["source_diagnostics"]["trace_dir"] == "reports/backtest/50k_core/traces"
    assert repair["keep_cyclical_watch_only"]["enabled"] is True
    assert cfg["evaluation"]["hard_conditions"]["max_drawdown_floor"] == -0.12
