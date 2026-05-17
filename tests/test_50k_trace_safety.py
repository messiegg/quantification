from __future__ import annotations

from pathlib import Path

from tests.test_50k_core_trace_generation import make_trace_bundle


def test_trace_effective_config_is_research_only_and_no_release_replacement() -> None:
    config = make_trace_bundle().trace_effective_config

    assert config["research_only"] is True
    assert config["auto_trading_approved"] is False
    assert config["broker_integration_enabled"] is False
    assert config["llm_decision_allowed"] is False
    assert config["writes_real_trades"] is False
    assert config["release_profile_replacement"] is False


def test_diagnostic_future_return_not_read_by_strategy_or_execution_code() -> None:
    root = Path(__file__).resolve().parents[1]
    offenders = []
    for path in list((root / "src").rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        if "diagnostic_future_return" in text or "diagnostic_opportunity_cost" in text:
            offenders.append(path)

    assert offenders == []


def test_trace_scripts_do_not_enable_auto_trading_or_broker() -> None:
    root = Path(__file__).resolve().parents[1]
    for path in [root / "scripts" / "generate_50k_core_traces.py", root / "scripts" / "diagnose_50k_core_traces.py"]:
        text = path.read_text(encoding="utf-8")
        assert "auto_trading_approved=True" not in text
        assert "broker_integration_enabled=True" not in text
        assert "writes_real_trades=True" not in text
