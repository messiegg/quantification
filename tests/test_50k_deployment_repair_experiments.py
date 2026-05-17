from __future__ import annotations

from pathlib import Path

from scripts import run_50k_core_deployment_repair as deployment


def test_deployment_repair_variant_builder_is_layered_and_capped() -> None:
    variants = deployment.build_deployment_repair_variants()

    assert len(variants) <= 24
    assert variants[0].name == "repair_best_baseline"
    assert any("quality_defensive_fill" in item.mechanisms_enabled for item in variants)
    assert any("winner_add" in item.mechanisms_enabled for item in variants)
    assert any("financial_group_cap" in item.mechanisms_enabled for item in variants)
    assert any("market_regime_block_review" in item.mechanisms_enabled for item in variants)
    assert any("cash_sleeve_research" in item.mechanisms_enabled for item in variants)
    assert all(item.research_only for item in variants)
    assert all(not item.release_profile_replacement for item in variants)


def test_deployment_repair_outputs_required_files_and_closest_to_pass(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(deployment, "OUT_DIR", str(tmp_path))
    rows = [
        {
            "variant": "repair_best_baseline",
            "mechanisms_enabled": "baseline",
            "annual_return": 0.098,
            "cumulative_return": 0.309,
            "max_drawdown": -0.160,
            "sharpe": 0.62,
            "total_trades": 10,
            "buy_trades": 7,
            "sell_trades": 3,
            "average_exposure": 0.59,
            "avg_cash_ratio_in_risk_on": 0.365,
            "realized_pnl": 9130,
            "unrealized_pnl": 6343,
            "largest_single_stock_pnl_contribution": 0.23,
            "largest_industry_pnl_contribution": 0.41,
            "defensive_dividend_pnl": 15473,
            "cyclical_rotation_pnl": 0,
            "quality_defensive_fill_candidates": 0,
            "quality_defensive_fill_executed": 0,
            "winner_add_candidates": 0,
            "winner_add_executed": 0,
            "financial_group_cap_blocks": 0,
            "market_regime_review_fills": 0,
            "cash_sleeve_trades": 0,
            "cash_sleeve_pnl": 0,
            "cash_sleeve_data_available": False,
            "no_raw_signal_risk_on_days": 95,
            "cyclical_disabled_or_blocked_days": 93,
            "executable_account_actionable_ratio": 1.0,
        }
    ]

    summary = deployment.write_deployment_repair_outputs(rows, effective_config={"safety": {"research_only": True}})

    assert summary["variant_count"] == 1
    assert summary["hard_condition_pass_count"] == 0
    assert summary["closest_to_pass_variant"]["variant"] == "repair_best_baseline"
    for name in deployment.REQUIRED_OUTPUTS:
        assert (tmp_path / name).exists(), name
