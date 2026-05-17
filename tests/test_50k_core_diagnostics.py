from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import yaml

from scripts import diagnose_50k_core_failures as diag


def _write_stage1_fixture(base: Path) -> None:
    base.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "variant": "top",
            "profile": "combined_v2_50k_core",
            "research_only": True,
            "annual_return": 0.098,
            "cumulative_return": 0.309,
            "max_drawdown": -0.1604,
            "sharpe": 0.62,
            "total_trades": 10,
            "buy_trades": 7,
            "sell_trades": 3,
            "executable_buy_count": 7,
            "account_actionable_buy_count": 7,
            "executable_account_actionable_ratio": 1.0,
            "raw_buy_signal_count": 152,
            "watch_only_count": 146,
            "avg_cash_ratio_in_risk_on": 0.365,
            "average_exposure": 0.59,
            "largest_single_stock_pnl_contribution": 0.23,
            "largest_industry_pnl_contribution": 0.41,
            "defensive_dividend_pnl": 15473.0,
            "cyclical_rotation_pnl": 0.0,
            "realized_pnl": 9130.0,
            "unrealized_pnl": 6343.0,
            "replacement_count": 1,
            "max_positions": 5,
            "cash_reserve_ratio": 0.10,
            "max_single_stock_weight": 0.18,
            "cyclical_max_positions": 0,
            "fail_reasons": "sharpe,max_drawdown,total_trades,avg_cash_ratio_in_risk_on",
        },
        {
            "variant": "second",
            "profile": "combined_v2_50k_core",
            "research_only": True,
            "annual_return": 0.031,
            "cumulative_return": 0.092,
            "max_drawdown": -0.086,
            "sharpe": 0.34,
            "total_trades": 24,
            "buy_trades": 14,
            "sell_trades": 10,
            "executable_buy_count": 14,
            "account_actionable_buy_count": 14,
            "executable_account_actionable_ratio": 1.0,
            "raw_buy_signal_count": 120,
            "watch_only_count": 80,
            "avg_cash_ratio_in_risk_on": 0.426,
            "average_exposure": 0.47,
            "largest_single_stock_pnl_contribution": 0.26,
            "largest_industry_pnl_contribution": 0.30,
            "defensive_dividend_pnl": 6448.0,
            "cyclical_rotation_pnl": -1808.0,
            "realized_pnl": 3519.0,
            "unrealized_pnl": 120.0,
            "replacement_count": 1,
            "max_positions": 6,
            "cash_reserve_ratio": 0.10,
            "max_single_stock_weight": 0.18,
            "cyclical_max_positions": 2,
            "fail_reasons": "annual_return,sharpe,avg_cash_ratio_in_risk_on,cyclical_rotation_pnl",
        },
    ]
    pd.DataFrame(rows).to_csv(base / "core_experiment_metrics.csv", index=False)
    pd.DataFrame(
        [
            {
                "date": "2024-01-02",
                "variant": "top",
                "market_regime": "risk_on",
                "raw_buy_signal_count": 3,
                "account_actionable_buy_count": 0,
                "watch_only_count": 3,
                "executable_buy_count": 0,
                "cyclical_candidates": 2,
                "cyclical_executed_buys": 0,
                "holdings_count": 5,
                "cash": 20000,
                "nav": 60000,
                "cash_ratio": 0.333,
                "exposure": 0.667,
                "replacement_count": 0,
            },
            {
                "date": "2024-01-03",
                "variant": "top",
                "market_regime": "risk_on",
                "raw_buy_signal_count": 2,
                "account_actionable_buy_count": 1,
                "watch_only_count": 1,
                "executable_buy_count": 1,
                "cyclical_candidates": 0,
                "cyclical_executed_buys": 0,
                "holdings_count": 4,
                "cash": 18000,
                "nav": 60000,
                "cash_ratio": 0.30,
                "exposure": 0.70,
                "replacement_count": 0,
            },
        ]
    ).to_csv(base / "core_execution_funnel.csv", index=False)
    pd.DataFrame(
        [
            {
                "variant": "top",
                "symbol_pnl": json.dumps({"600000.sh": 3000, "600036.sh": -1200}),
                "industry_pnl": json.dumps({"银行": 1800, "公用事业": 2200}),
                "bucket_pnl": json.dumps({"defensive_dividend": 4000, "cyclical_rotation": 0}),
                "largest_single_stock_pnl_contribution": 0.23,
                "largest_industry_pnl_contribution": 0.41,
            }
        ]
    ).to_csv(base / "core_attribution_summary.csv", index=False)
    pd.DataFrame(
        [
            {
                "date": "2024-02-01",
                "sell_symbol": "600000.sh",
                "buy_symbol": "000001.sz",
                "sell_industry": "银行",
                "buy_industry": "银行",
                "weakest_holding_score": 40,
                "candidate_score": 55,
                "score_gap": 15,
                "sell_reason": "VALUATION_NOT_CHEAP",
                "buy_reason": "EXPECTED_EDGE_SCORE_GAP_AND_LOT_FIT",
                "realized_pnl_from_sell": 500,
                "estimated_cost": 8,
                "portfolio_positions_before": 6,
                "portfolio_positions_after": 5,
                "variant": "top",
            }
        ]
    ).to_csv(base / "core_replacement_report.csv", index=False)
    (base / "core_experiment_report.md").write_text("# report\n", encoding="utf-8")
    (base / "core_module_contribution_report.md").write_text("# modules\n", encoding="utf-8")
    (base / "core_warnings.json").write_text(json.dumps({"watch_only_reasons": {"WATCH_ONLY_CYCLICAL_DISABLED": 5}}), encoding="utf-8")
    (base / "core_effective_config.yml").write_text(yaml.safe_dump({"evaluation": diag.DEFAULT_EVALUATION, "safety": {"auto_trading_approved": False}}), encoding="utf-8")


def test_diagnostics_generates_required_files(tmp_path: Path) -> None:
    stage1 = tmp_path / "50k_core"
    _write_stage1_fixture(stage1)

    summary = diag.run_diagnostics(input_dir=stage1, output_dir=stage1 / "diagnostics")

    assert summary["top_variant"] == "top"
    for name in diag.REQUIRED_DIAGNOSTIC_OUTPUTS:
        assert (stage1 / "diagnostics" / name).exists(), name


def test_failure_condition_summary_contains_all_hard_conditions(tmp_path: Path) -> None:
    stage1 = tmp_path / "50k_core"
    _write_stage1_fixture(stage1)
    diag.run_diagnostics(input_dir=stage1, output_dir=stage1 / "diagnostics")
    frame = pd.read_csv(stage1 / "diagnostics" / "failure_condition_summary.csv")

    assert set(diag.HARD_CONDITIONS) <= set(frame["condition_name"])
    assert {"fail_count", "fail_ratio", "median_gap_to_pass", "interpretation"} <= set(frame.columns)


def test_top_variant_deep_dive_warns_when_trade_detail_is_missing(tmp_path: Path) -> None:
    stage1 = tmp_path / "50k_core"
    _write_stage1_fixture(stage1)
    diag.run_diagnostics(input_dir=stage1, output_dir=stage1 / "diagnostics")
    text = (stage1 / "diagnostics" / "top_variant_deep_dive.md").read_text(encoding="utf-8")

    assert "缺失字段警告" in text
    assert "逐笔交易明细" in text


def test_risk_on_cash_drag_classifies_each_high_cash_day(tmp_path: Path) -> None:
    stage1 = tmp_path / "50k_core"
    _write_stage1_fixture(stage1)
    diag.run_diagnostics(input_dir=stage1, output_dir=stage1 / "diagnostics")
    frame = pd.read_csv(stage1 / "diagnostics" / "risk_on_cash_drag_report.csv")

    assert "reason_cash_not_deployed" in frame.columns
    assert frame["reason_cash_not_deployed"].notna().all()
