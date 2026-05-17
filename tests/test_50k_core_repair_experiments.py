from __future__ import annotations

from pathlib import Path

import pandas as pd

from scripts import run_50k_core_repair_experiments as repair


def test_repair_variant_builder_caps_at_24() -> None:
    variants = repair.build_repair_variants()

    assert len(variants) <= 24
    assert all(item.research_only for item in variants)
    assert all(not item.auto_trading_approved for item in variants)


def test_repair_outputs_are_research_only_and_do_not_replace_release(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(repair, "OUT_DIR", str(tmp_path))
    rows = [
        {
            "variant": "repair_a",
            "research_only": True,
            "auto_trading_approved": False,
            "broker_integration_enabled": False,
            "llm_decision_allowed": False,
            "writes_real_trades": False,
            "release_profile_replacement": False,
            "annual_return": 0.06,
            "cumulative_return": 0.18,
            "max_drawdown": -0.10,
            "sharpe": 0.80,
            "total_trades": 24,
            "executable_account_actionable_ratio": 0.9,
            "avg_cash_ratio_in_risk_on": 0.30,
            "largest_single_stock_pnl_contribution": 0.30,
            "largest_industry_pnl_contribution": 0.40,
            "realized_pnl": 1000,
            "cyclical_rotation_pnl": 0,
        }
    ]

    summary = repair.write_repair_outputs(rows, stage1_best={})

    assert summary["release_profile_replacement"] is False
    assert (tmp_path / "repair_experiment_metrics.csv").exists()
    assert (tmp_path / "repair_warnings.json").exists()
