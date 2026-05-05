from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from scripts import build_account_suitability_report as account_suitability
from scripts import build_module_contribution_report as module_contribution
from scripts import build_sensitivity_trigger_coverage_report as trigger_coverage
from scripts import check_release_status_consistency as status_consistency
from scripts import evaluate_observation_readiness as readiness


def _patch_resolve(monkeypatch, module, tmp_path: Path) -> None:
    def fake_resolve(path: str | Path) -> Path:
        candidate = Path(path)
        return candidate if candidate.is_absolute() else tmp_path / candidate

    monkeypatch.setattr(module, "resolve_path", fake_resolve)


def test_release_status_consistency_fails_on_status_mismatch(monkeypatch, tmp_path: Path) -> None:
    _patch_resolve(monkeypatch, status_consistency, tmp_path)
    (tmp_path / "reports/backtest/release").mkdir(parents=True)
    (tmp_path / "reports/audit").mkdir(parents=True)
    (tmp_path / "reports/backtest/robustness").mkdir(parents=True)
    (tmp_path / "reports/backtest/controls").mkdir(parents=True)
    (tmp_path / "reports/observation/2026-05-04").mkdir(parents=True)
    (tmp_path / "docs").mkdir()
    (tmp_path / "README.md").write_text("- current_release_status: `PASS_CANDIDATE`\n", encoding="utf-8")
    (tmp_path / "docs/project_status_2026-05-05.md").write_text("- current_release_status: `PASS_CANDIDATE`\n", encoding="utf-8")
    (tmp_path / "reports/backtest/release/combined_v2_rc_manifest.md").write_text("- status: PASS_CANDIDATE\n", encoding="utf-8")
    (tmp_path / "reports/backtest/release/release_guard_report.md").write_text("- overall_status: PASS\n", encoding="utf-8")
    (tmp_path / "reports/backtest/release/combined_v2_rc_manifest.json").write_text(json.dumps({"status": "PASS_CANDIDATE", "audit_statuses": {"x": "PASS"}}), encoding="utf-8")
    (tmp_path / "reports/audit/universe_integrity.json").write_text(json.dumps({"status": "WARN", "selected_count": 30, "target_size": 36}), encoding="utf-8")
    (tmp_path / "reports/backtest/account_constraints_report.json").write_text(json.dumps({"warnings": []}), encoding="utf-8")
    (tmp_path / "reports/backtest/robustness/sensitivity_report.json").write_text(json.dumps({"non_binding_parameters": []}), encoding="utf-8")
    (tmp_path / "reports/backtest/controls/baseline_comparison.json").write_text(json.dumps({"comparisons": []}), encoding="utf-8")
    (tmp_path / "reports/observation/2026-05-04/evidence_chain.json").write_text(json.dumps({"status": "PASS"}), encoding="utf-8")

    payload = status_consistency.build_release_status_consistency_report(write_report=False)

    assert payload["expected_current_release_status"] == "WARN"
    assert payload["status"] == "FAIL"
    assert any(item["code"] == "STATUS_MISMATCH" for item in payload["violations"])


def test_account_suitability_keeps_low_base_execution_ratio_warn(monkeypatch, tmp_path: Path) -> None:
    _patch_resolve(monkeypatch, account_suitability, tmp_path)
    (tmp_path / "config").mkdir()
    (tmp_path / "reports/backtest").mkdir(parents=True)
    (tmp_path / "config/account.yml").write_text(
        """
account:
  initial_capital: 200000
  current_cash: 50000
  reserved_cash: 0
  latest_total_equity: 200000
execution:
  round_lot: 100
position_sizing:
  min_trade_value: 5000
  tranche_weights: {1: 0.03}
""",
        encoding="utf-8",
    )
    (tmp_path / "config/strategy_v2.yml").write_text("execution:\n  max_positions: 20\n", encoding="utf-8")
    pd.DataFrame(
        [
            {"reason_code": "MIN_TRADE_AMOUNT", "current_weight": 0.0, "intended_target_weight": 0.02},
            {"reason_code": "MIN_TRADE_AMOUNT", "current_weight": 0.01, "intended_target_weight": 0.02},
        ]
    ).to_csv(tmp_path / "reports/backtest/combined_v2_blocked_signals.csv", index=False)
    monkeypatch.setattr(
        account_suitability,
        "build_account_constraints_report",
        lambda write_report=False: {
            "raw_buy_signal_count": 10,
            "executable_buy_count": 1,
            "executable_raw_buy_ratio": 0.1,
            "blocked_buy_count": 9,
            "blocker_counts": {"MIN_TRADE_AMOUNT": 6},
            "min_trade_amount_block_count": 6,
            "cash_block_count": 0,
            "exposure_block_count": 0,
            "lot_size_block_count": 0,
            "average_exposure": 0.2,
            "turnover": 1.0,
        },
    )

    payload = account_suitability.build_account_suitability_report(write_report=False)

    assert payload["status"] == "WARN"
    assert payload["base_case"]["executable_raw_buy_ratio"] == 0.1
    assert payload["estimated_capital_required_to_reach_executable_raw_25"] == "unknown"
    assert all(item["research_only"] or item["capital_multiplier"] == 1 for item in payload["scenarios"])


def test_sensitivity_trigger_coverage_classifies_param_not_wired(monkeypatch, tmp_path: Path) -> None:
    _patch_resolve(monkeypatch, trigger_coverage, tmp_path)
    (tmp_path / "reports/backtest/robustness").mkdir(parents=True)
    (tmp_path / "reports/backtest").mkdir(parents=True, exist_ok=True)
    (tmp_path / "src").mkdir()
    (tmp_path / "scripts").mkdir()
    (tmp_path / "config").mkdir()
    (tmp_path / "reports/backtest/robustness/sensitivity_report.json").write_text(
        json.dumps({"mode": "ci", "start_date": "2025-04-03", "end_date": "2026-04-03"}),
        encoding="utf-8",
    )
    pd.DataFrame(
        [
            {"variant_id": "current_v2", "variant_group": "current", "raw_buy_signal_count": 1, "raw_sell_signal_count": 0},
            {
                "variant_id": "unused_param",
                "variant_group": "unused_param",
                "changed_parameter": "unused_param=1",
                "variant_config_hash": "v",
                "raw_buy_signal_count": 1,
                "raw_sell_signal_count": 0,
                "blocked_signal_count": 0,
                "changed_action_days_count": 0,
                "changed_position_days_count": 0,
                "parameter_binding_status": "NON_BINDING",
                "non_binding_reason": "NO_SIGNAL_COVERAGE",
            },
        ]
    ).to_csv(tmp_path / "reports/backtest/robustness/sensitivity_metrics.csv", index=False)
    pd.DataFrame([{"date": "2025-04-03"}]).to_csv(tmp_path / "reports/backtest/combined_v2_signal_funnel.csv", index=False)

    payload = trigger_coverage.build_sensitivity_trigger_coverage_report(write_report=False)

    assert payload["status"] == "FAIL"
    assert payload["classifications"][0]["classification"] == "PARAM_NOT_WIRED"


def test_module_contribution_classifies_risk_reducer_and_drag(monkeypatch, tmp_path: Path) -> None:
    _patch_resolve(monkeypatch, module_contribution, tmp_path)
    (tmp_path / "reports/backtest/controls").mkdir(parents=True)
    rows = [
        {"control_id": "combined_v2_next_bar", "annual_return": 0.07, "cumulative_return": 0.2, "max_drawdown": -0.09, "sharpe": 0.8, "calmar": 0.7, "turnover": 2.0, "avg_daily_exposure": 0.4, "max_daily_exposure": 0.7, "total_trades": 10, "excess_annual_return": 0.04},
        {"control_id": "v2_no_high_dividend_supplement", "annual_return": 0.09, "cumulative_return": 0.25, "max_drawdown": -0.08, "sharpe": 0.9, "calmar": 1.0, "turnover": 2.0, "avg_daily_exposure": 0.4, "max_daily_exposure": 0.7, "total_trades": 10, "excess_annual_return": 0.06},
        {"control_id": "v2_no_trend_stop", "annual_return": 0.09, "cumulative_return": 0.25, "max_drawdown": -0.08, "sharpe": 0.9, "calmar": 1.0, "turnover": 2.0, "avg_daily_exposure": 0.4, "max_daily_exposure": 0.7, "total_trades": 10, "excess_annual_return": 0.06},
        {"control_id": "v2_no_market_state_filter", "annual_return": 0.08, "cumulative_return": 0.23, "max_drawdown": -0.13, "sharpe": 0.7, "calmar": 0.5, "turnover": 2.5, "avg_daily_exposure": 0.5, "max_daily_exposure": 0.8, "total_trades": 12, "excess_annual_return": 0.05},
        {"control_id": "v2_no_industry_cap", "annual_return": 0.05, "cumulative_return": 0.15, "max_drawdown": -0.10, "sharpe": 0.6, "calmar": 0.5, "turnover": 2.5, "avg_daily_exposure": 0.5, "max_daily_exposure": 0.8, "total_trades": 12, "excess_annual_return": 0.02},
        {"control_id": "v2_relaxed_account_constraints_research_only", "annual_return": 0.05, "cumulative_return": 0.15, "max_drawdown": -0.10, "sharpe": 0.6, "calmar": 0.5, "turnover": 2.5, "avg_daily_exposure": 0.5, "max_daily_exposure": 0.8, "total_trades": 12, "excess_annual_return": 0.02},
    ]
    pd.DataFrame(rows).to_csv(tmp_path / "reports/backtest/controls/control_baselines_metrics.csv", index=False)

    payload = module_contribution.build_module_contribution_report(write_report=False)
    classes = {item["module"]: item["classification"] for item in payload["modules"]}

    assert classes["high_dividend_supplement"] == "POSSIBLE_DRAG"
    assert classes["market_state_filter"] == "RISK_REDUCER"


def test_observation_readiness_is_not_ready_without_manual_log(monkeypatch, tmp_path: Path) -> None:
    _patch_resolve(monkeypatch, readiness, tmp_path)
    (tmp_path / "config").mkdir()
    (tmp_path / "config/observation_readiness.yml").write_text(
        """
minimum_observation_trading_days: 60
maximum_hard_fail_count: 0
maximum_unknown_sensitivity_params: 0
maximum_param_not_wired_count: 0
minimum_executable_raw_buy_ratio: 0.25
require_manual_review_log: true
require_evidence_chain_every_day: true
manual_review_log_path: data/observation/manual_review_log.csv
""",
        encoding="utf-8",
    )

    payload = readiness.evaluate_observation_readiness(write_report=False)

    assert payload["status"] == "NOT_READY"
    assert payload["observation_trading_days"] == 0
