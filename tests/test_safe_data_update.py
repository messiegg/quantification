from __future__ import annotations

from pathlib import Path

import pandas as pd

from scripts import update_market_data_safe as safe_update
from src.utils.config import resolve_path


def test_update_market_data_safe_dry_run_does_not_run_update_commands(monkeypatch, tmp_path: Path) -> None:
    def fail_run(*args, **kwargs):
        raise AssertionError("dry-run must not execute data update commands")

    monkeypatch.setattr(safe_update.subprocess, "run", fail_run)
    result = safe_update.run_safe_update("2026-05-04", dry_run=True, write_report=False)
    assert result["status"] == "DRY_RUN"
    assert result["wrote_data"] is False


def test_update_market_data_safe_plan_lists_gap_trading_days(monkeypatch) -> None:
    monkeypatch.setattr(
        safe_update,
        "resolve_target_trading_date",
        lambda *args, **kwargs: {
            "requested_as_of_date": "2026-05-04",
            "requested_as_of_is_trading_day": False,
            "target_trading_date": "2026-04-30",
            "target_trading_date_is_valid": True,
            "calendar_source": "fixture",
            "calendar_min_date": "2026-04-01",
            "calendar_max_date": "2026-04-30",
            "calendar_market": "A_SHARE",
        },
    )
    monkeypatch.setattr(
        safe_update,
        "build_data_freshness_report",
        lambda *args, **kwargs: {
            "data_max_date": "2026-04-28",
            "feature_max_date": "2026-04-28",
            "benchmark_max_date": "2026-04-28",
        },
    )
    monkeypatch.setattr(
        safe_update,
        "trading_dates_between",
        lambda *args, **kwargs: ["2026-04-29", "2026-04-30"],
    )
    plan = safe_update.build_update_plan("2026-05-04")
    assert plan["gap_trading_dates"] == ["2026-04-29", "2026-04-30"]
    assert "daily行情" in plan["update_types"]


def test_real_paper_ledger_is_gitignored() -> None:
    import subprocess

    for path in [
        "data/observation/paper_account.yml",
        "data/observation/paper_trades.csv",
        "data/observation/paper_positions.yml",
    ]:
        result = subprocess.run(["git", "check-ignore", "--quiet", "--", path], cwd=resolve_path("."), check=False)
        assert result.returncode == 0


def test_combined_v2_next_bar_metrics_remain_exact() -> None:
    execution = pd.read_csv(resolve_path("reports/backtest/audit/execution_mode_compare.csv"))
    row = execution[(execution["profile"] == "combined_v2") & (execution["execution_mode"] == "next_bar")].iloc[0]
    assert float(row["annual_return"]) == 0.0713520247687258
    assert float(row["cumulative_return"]) == 0.2196444045310004
    assert float(row["max_drawdown"]) == -0.0936454742991675
    assert int(row["total_trades"]) == 76
    assert 200000.0 * (1.0 + float(row["cumulative_return"])) == 243928.8809062001
