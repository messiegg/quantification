from __future__ import annotations

import json
from pathlib import Path

from scripts import rc_hash_scope
from src.utils.config import load_yaml, resolve_path


CORE_FILES = [
    "config/strategy_v2_50k_core.yml",
    "scripts/run_50k_core_experiments.py",
    "src/strategy/score_50k_core.py",
    "src/execution/replacement.py",
]


def test_50k_core_files_never_enable_auto_trading_or_broker() -> None:
    for rel_path in CORE_FILES:
        text = resolve_path(rel_path).read_text(encoding="utf-8")
        assert "auto_trading_approved: true" not in text
        assert '"auto_trading_approved": true' not in text
        assert "broker_integration_enabled: true" not in text
        assert '"broker_integration_enabled": true' not in text
        assert "writes_real_trades: true" not in text
        assert "PASS_FOR_LIVE" not in text


def test_50k_core_does_not_modify_default_release_profile() -> None:
    cfg = load_yaml("config/strategy_v2_50k_core.yml")
    manifest = json.loads(resolve_path("reports/backtest/release/combined_v2_rc_manifest.json").read_text(encoding="utf-8"))

    assert cfg["release_profile_replacement"] is False
    assert manifest["profile"] == "combined_v2"
    assert manifest["profile"] != "combined_v2_50k_core"
    assert manifest["account_profile"] in {"retail_50k_lot_aware", "actual_50k_lot_aware"}


def test_50k_core_research_artifacts_excluded_from_release_hash_scope() -> None:
    excluded = set(rc_hash_scope.RESEARCH_ONLY_EXCLUDED_FROM_RC_CODE_HASH)

    assert "config/strategy_v2_50k_core.yml" in excluded
    assert "scripts/run_50k_core_experiments.py" in excluded
    assert "reports/backtest/50k_core/**" in excluded


def test_no_real_trade_or_broker_files_created_for_50k_core() -> None:
    forbidden = [
        Path("data/ledger/50k_core_trades.csv"),
        Path("config/50k_core_broker.yml"),
        Path("reports/backtest/50k_core/live_orders.csv"),
    ]

    assert all(not resolve_path(path).exists() for path in forbidden)
