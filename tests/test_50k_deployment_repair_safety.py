from __future__ import annotations

from pathlib import Path

from scripts import rc_hash_scope
from scripts import run_50k_core_deployment_repair as deployment
from src.utils.config import load_yaml, resolve_path


def test_deployment_repair_does_not_enable_live_or_replace_release() -> None:
    cfg = load_yaml("config/strategy_v2_50k_core_deployment_repair.yml")
    safety = cfg["safety"]

    assert safety["research_only"] is True
    assert safety["auto_trading_approved"] is False
    assert safety["broker_integration_enabled"] is False
    assert safety["llm_decision_allowed"] is False
    assert safety["writes_real_trades"] is False
    assert safety["release_profile_replacement"] is False


def test_deployment_repair_source_contains_no_broker_or_live_approval() -> None:
    text = resolve_path("scripts/run_50k_core_deployment_repair.py").read_text(encoding="utf-8")

    assert "auto_trading_approved: true" not in text
    assert '"auto_trading_approved": true' not in text
    assert "broker_integration_enabled: true" not in text
    assert "writes_real_trades: true" not in text
    assert "PASS_FOR_LIVE" not in text


def test_cash_sleeve_pass_is_not_stock_only_pass() -> None:
    row = {"pass_hard_conditions": True, "stock_only": False, "mechanisms_enabled": "cash_sleeve_research"}

    assert deployment.is_stock_only_pass(row) is False


def test_deployment_repair_research_files_are_excluded_from_release_hash_scope() -> None:
    excluded = set(rc_hash_scope.RESEARCH_ONLY_EXCLUDED_FROM_RC_CODE_HASH)

    assert "config/strategy_v2_50k_core_deployment_repair.yml" in excluded
    assert "src/strategy/deployment_repair.py" in excluded
    assert "scripts/run_50k_core_deployment_repair.py" in excluded
    assert "reports/backtest/50k_core/**" in excluded
