from __future__ import annotations

from pathlib import Path

import pandas as pd

from scripts import run_50k_core_experiments as core


def _metric_row(variant: str, **overrides) -> dict:
    row = {
        "variant": variant,
        "profile": "combined_v2_50k_core",
        "research_only": True,
        "max_positions": 5,
        "max_tranches": 1,
        "target_universe_size": 8,
        "cash_reserve_ratio": 0.10,
        "max_single_stock_weight": 0.16,
        "industry_max_positions": 1,
        "cyclical_max_positions": 0,
        "defensive_core_min_positions": 3,
        "lot_notional_max_ratio_to_target_budget": 0.90,
        "score_gap_threshold": 10,
        "max_replacements_per_month": 1,
        "risk_on_target_exposure": 0.75,
        "neutral_target_exposure": 0.45,
        "risk_off_target_exposure": 0.00,
        "annual_return": 0.07,
        "cumulative_return": 0.21,
        "max_drawdown": -0.08,
        "sharpe": 0.90,
        "total_trades": 32,
        "buy_trades": 18,
        "sell_trades": 14,
        "executable_buy_count": 18,
        "account_actionable_buy_count": 20,
        "raw_buy_signal_count": 100,
        "watch_only_count": 80,
        "avg_cash_ratio_in_risk_on": 0.25,
        "largest_single_stock_pnl_contribution": 0.30,
        "largest_industry_pnl_contribution": 0.40,
        "defensive_dividend_pnl": 3_000,
        "cyclical_rotation_pnl": 0,
        "realized_pnl": 1_000,
        "unrealized_pnl": 2_000,
        "replacement_count": 1,
    }
    row.update(overrides)
    return row


def test_hard_condition_logic_collects_fail_reasons() -> None:
    passing = core.evaluate_hard_conditions(_metric_row("pass"), core.DEFAULT_EVALUATION)
    failing = core.evaluate_hard_conditions(
        _metric_row(
            "fail",
            annual_return=0.02,
            sharpe=0.3,
            total_trades=8,
            avg_cash_ratio_in_risk_on=0.50,
            largest_single_stock_pnl_contribution=0.70,
            realized_pnl=-1,
        ),
        core.DEFAULT_EVALUATION,
    )

    assert passing["pass_hard_conditions"] is True
    assert failing["pass_hard_conditions"] is False
    assert "annual_return" in failing["fail_reasons"]
    assert "realized_pnl" in failing["fail_reasons"]


def test_top20_report_and_failure_report_are_written(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(core, "OUT_DIR", str(tmp_path))
    rows = [_metric_row(f"v{i}", annual_return=0.07 + i / 10_000) for i in range(25)]

    summary = core.write_core_outputs(rows, config={"profile_name": "combined_v2_50k_core", "evaluation": core.DEFAULT_EVALUATION})

    metrics = pd.read_csv(tmp_path / "core_experiment_metrics.csv")
    report = (tmp_path / "core_experiment_report.md").read_text(encoding="utf-8")
    assert len(metrics) == 25
    assert report.count("| v") >= 20
    assert summary["hard_condition_pass_count"] == 25
    assert (tmp_path / "core_best_candidate.yml").exists()


def test_no_candidate_still_generates_failure_reports(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(core, "OUT_DIR", str(tmp_path))
    rows = [_metric_row(f"fail{i}", annual_return=0.01, sharpe=0.2, total_trades=5, realized_pnl=-100) for i in range(3)]

    summary = core.write_core_outputs(rows, config={"profile_name": "combined_v2_50k_core", "evaluation": core.DEFAULT_EVALUATION})

    assert summary["status"] == "NO_50K_CORE_CANDIDATE"
    assert (tmp_path / "core_warnings.json").exists()
    assert "失败分布" in (tmp_path / "core_experiment_report.md").read_text(encoding="utf-8")


def test_neighborhood_robustness_requires_at_least_eight_neighbors() -> None:
    best = _metric_row("best")
    neighbors = [_metric_row(f"n{i}", annual_return=0.065) for i in range(8)]

    result = core.evaluate_neighborhood_robustness(best, neighbors, core.DEFAULT_EVALUATION)

    assert result["neighbor_count"] >= 8
    assert result["support_count_excluding_best"] == 8
    assert result["status"] == "ROBUST"


def test_required_output_names_are_declared() -> None:
    assert set(core.REQUIRED_OUTPUTS) == {
        "core_experiment_metrics.csv",
        "core_experiment_report.md",
        "core_best_candidate.yml",
        "core_observation_candidate.md",
        "core_neighborhood_robustness.md",
        "core_execution_funnel.csv",
        "core_attribution_summary.csv",
        "core_replacement_report.csv",
        "core_effective_config.yml",
        "core_warnings.json",
        "core_module_contribution_report.md",
    }


def test_regime_target_exposure_accepts_regime_dict() -> None:
    params = core.CoreParams(
        max_positions=5,
        max_tranches=1,
        target_universe_size=8,
        cash_reserve_ratio=0.10,
        max_single_stock_weight=0.18,
        max_new_positions_per_day=1,
        max_adds_per_day=0,
        industry_max_positions=2,
        defensive_core_min_positions=3,
        cyclical_max_positions=1,
        lot_notional_max_ratio_to_target_budget=1.0,
        score_gap_threshold=8,
        max_replacements_per_month=1,
        risk_on_target_exposure=0.85,
        neutral_target_exposure=0.60,
        risk_off_target_exposure=0.25,
    )

    assert core._regime_target_exposure(params, {"regime": "risk_on"}) == 0.85
    assert core._target_weight(params, {"regime": "risk_on"}) == 0.17
