from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import yaml

from scripts import check_data_freshness as freshness
from scripts import run_observation_pipeline as pipeline
from scripts import update_paper_observation as paper
from scripts.verify_combined_v2_rc import sha256_path
from src.utils.config import resolve_path


def _pass_frame() -> pd.DataFrame:
    return pd.DataFrame([{"status": "PASS", "check_id": "TEST", "check_name": "fixture"}])


def _fail_frame() -> pd.DataFrame:
    return pd.DataFrame([{"status": "FAIL", "check_id": "TEST", "check_name": "fixture"}])


def _temp_observation_config(tmp_path: Path) -> dict:
    return {
        "observation": {
            "primary_profile": "combined_v2",
            "conservative_profile": "combined_v2_1_risk_guard",
            "execution_mode": "next_bar",
            "mode": "paper_observation_only",
            "generate_manual_order_list": True,
            "generate_manual_order_list_only_when_market_data_current": True,
        },
        "manual_observation": {
            "initial_paper_capital": 200000,
            "paper_account_path": str(tmp_path / "paper_account.yml"),
            "paper_trades_path": str(tmp_path / "paper_trades.csv"),
            "paper_positions_path": str(tmp_path / "paper_positions.yml"),
            "observation_report_dir": str(tmp_path / "reports" / "observation"),
            "compare_v2_1_risk_guard": True,
        },
    }


def _ensure_temp_paper_files(tmp_path: Path) -> dict[str, Path]:
    account = tmp_path / "paper_account.yml"
    trades = tmp_path / "paper_trades.csv"
    positions = tmp_path / "paper_positions.yml"
    for path in (account, trades, positions):
        path.parent.mkdir(parents=True, exist_ok=True)
    if not account.exists():
        account.write_text(
            yaml.safe_dump(
                {
                    "paper_account": {
                        "initial_capital": 200000,
                        "current_cash": 200000,
                        "total_equity": 200000,
                        "mode": "paper_observation_only",
                        "broker_connected": False,
                        "auto_order_enabled": False,
                    }
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
    if not trades.exists():
        trades.write_text(",".join(paper.PAPER_COLUMNS) + "\n", encoding="utf-8")
    if not positions.exists():
        positions.write_text("paper_positions: []\nbroker_connected: false\nauto_order_enabled: false\n", encoding="utf-8")
    return {
        "account": account,
        "trades": trades,
        "positions": positions,
        "report_dir": tmp_path / "reports" / "observation",
    }


def _patch_pipeline_common(
    monkeypatch,
    tmp_path: Path,
    data_allowed: bool = True,
    rc_pass: bool = True,
    quality_status: str = "PASS",
    non_trading_day: bool = False,
) -> Path:
    config = _temp_observation_config(tmp_path)
    outbase = Path(config["manual_observation"]["observation_report_dir"])
    monkeypatch.setattr(pipeline, "load_yaml", lambda path: config)
    monkeypatch.setattr(pipeline, "verify_release_candidate", lambda rerun_backtest=True: _pass_frame() if rc_pass else _fail_frame())
    monkeypatch.setattr(pipeline, "build_report_freshness_check", lambda: _pass_frame())
    monkeypatch.setattr(pipeline, "build_release_sync_consistency_check", lambda write_report=False: _pass_frame())
    monkeypatch.setattr(
        pipeline,
        "build_data_quality_observation_report",
        lambda as_of_date, write_report=True: {
            "status": quality_status,
            "feature_rows_on_target_date": 10,
            "unique_stocks_on_target_date": 10,
            "benchmark_row_exists_on_target_trading_date": True,
        },
    )
    monkeypatch.setattr(pipeline, "ensure_paper_observation_files", lambda: _ensure_temp_paper_files(tmp_path))

    def fake_freshness(as_of_date: str, write_report: bool = False) -> dict:
        out_dir = outbase / as_of_date
        out_dir.mkdir(parents=True, exist_ok=True)
        report = {
            "requested_as_of_date": as_of_date,
            "requested_as_of_is_trading_day": not non_trading_day,
            "target_trading_date": "2026-04-30" if non_trading_day else as_of_date,
            "data_max_date": as_of_date if data_allowed else "2026-04-03",
            "feature_max_date": as_of_date if data_allowed else "2026-04-03",
            "benchmark_max_date": as_of_date if data_allowed else "2026-04-03",
            "universe_max_effective_date": as_of_date,
            "stale_calendar_days": 0 if data_allowed else 31,
            "stale_trading_days": 0 if data_allowed else 18,
            "blocking_reason": "NONE" if data_allowed else "DATA_MAX_DATE_BEFORE_TARGET_TRADING_DATE",
            "allowed_actions": "observation_report_allowed" if data_allowed else "historical_review_only",
        }
        (out_dir / "data_freshness_report.md").write_text("fixture\n", encoding="utf-8")
        (out_dir / "data_freshness_report.json").write_text(json.dumps(report), encoding="utf-8")
        return report

    monkeypatch.setattr(pipeline, "build_data_freshness_report", fake_freshness)
    return outbase


def test_check_data_freshness_blocks_when_as_of_after_data_max() -> None:
    report = freshness.build_data_freshness_report("2026-05-04", write_report=False)
    assert report["allowed_actions"] == "historical_review_only"
    assert report["requested_as_of_is_trading_day"] is False
    assert report["target_trading_date"] == "2026-04-30"
    assert "DATA_MAX_DATE_BEFORE_TARGET_TRADING_DATE" in report["blocking_reason"]


def test_check_data_freshness_allows_current_fixture(monkeypatch) -> None:
    current = pd.Timestamp("2026-05-04")
    monkeypatch.setattr(freshness, "load_yaml_optional", lambda path: {"observation": {"max_stale_calendar_days_for_daily_report": 3, "require_data_max_date_ge_as_of_date": True}})
    monkeypatch.setattr(
        freshness,
        "resolve_target_trading_date",
        lambda *args, **kwargs: {
            "requested_as_of_date": "2026-05-04",
            "requested_as_of_is_trading_day": True,
            "target_trading_date": "2026-05-04",
            "target_trading_date_is_valid": True,
            "calendar_source": "fixture",
            "calendar_min_date": "2026-05-04",
            "calendar_max_date": "2026-05-04",
            "calendar_market": "A_SHARE",
        },
    )
    monkeypatch.setattr(freshness, "trading_dates_between", lambda *args, **kwargs: [])
    monkeypatch.setattr(freshness, "_feature_max_date", lambda: (current, "fixture_features"))
    monkeypatch.setattr(freshness, "_max_date_from_parquet", lambda path, date_columns=("date", "trade_date"): current)
    monkeypatch.setattr(freshness, "_universe_max_effective_date", lambda: current)
    monkeypatch.setattr(
        freshness,
        "_json_optional",
        lambda path: {"as_of_date": "2026-05-04"} if "manifest" not in str(path) else {"data_max_date": "2026-04-03"},
    )
    report = freshness.build_data_freshness_report("2026-05-04", write_report=False)
    assert report["allowed_actions"] == "observation_report_allowed"
    assert report["is_data_current"] is True


def test_run_observation_pipeline_blocks_on_rc_fail(monkeypatch, tmp_path: Path) -> None:
    outbase = _patch_pipeline_common(monkeypatch, tmp_path, data_allowed=True, rc_pass=False)
    manifest = pipeline.run_observation_pipeline("2026-05-04", rerun_rc_verify=False)
    out_dir = outbase / "2026-05-04"
    assert manifest["blocking_reason"] == "RC_VERIFY_FAIL"
    assert (out_dir / "observation_blocked.md").exists()
    assert not (out_dir / "combined_v2_manual_order_list.csv").exists()


def test_run_observation_pipeline_blocks_stale_data_without_manual_order_list(monkeypatch, tmp_path: Path) -> None:
    outbase = _patch_pipeline_common(monkeypatch, tmp_path, data_allowed=False, rc_pass=True)
    manifest = pipeline.run_observation_pipeline("2026-05-04", rerun_rc_verify=False)
    out_dir = outbase / "2026-05-04"
    assert manifest["blocking_reason"] == "STALE_DATA_BLOCKED"
    assert (out_dir / "observation_blocked.md").exists()
    assert not (out_dir / "combined_v2_manual_order_list.csv").exists()


def test_run_observation_pipeline_generates_summary_and_manual_list_when_allowed(monkeypatch, tmp_path: Path) -> None:
    outbase = _patch_pipeline_common(monkeypatch, tmp_path, data_allowed=True, rc_pass=True)
    manifest = pipeline.run_observation_pipeline("2023-04-04", rerun_rc_verify=False)
    out_dir = outbase / "2023-04-04"
    assert manifest["action_allowed"] is True
    assert (out_dir / "observation_summary.md").exists()
    manual = out_dir / "combined_v2_manual_order_list.csv"
    assert manual.exists()
    assert "需要人工判断和人工执行" in (out_dir / "observation_summary.md").read_text(encoding="utf-8")
    assert manifest["profile"] == "combined_v2"
    assert manifest["conservative_profile"] == "combined_v2_1_risk_guard"


def test_run_observation_pipeline_blocks_on_data_quality_fail(monkeypatch, tmp_path: Path) -> None:
    outbase = _patch_pipeline_common(monkeypatch, tmp_path, data_allowed=True, rc_pass=True, quality_status="FAIL")
    manifest = pipeline.run_observation_pipeline("2026-04-30", rerun_rc_verify=False)
    out_dir = outbase / "2026-04-30"
    assert manifest["blocking_reason"] == "DATA_QUALITY_FAIL"
    assert (out_dir / "observation_blocked.md").exists()
    assert not (out_dir / "combined_v2_manual_order_list.csv").exists()


def test_non_trading_day_observation_summary_is_next_day_review_only(monkeypatch, tmp_path: Path) -> None:
    outbase = _patch_pipeline_common(monkeypatch, tmp_path, data_allowed=True, rc_pass=True, quality_status="PASS", non_trading_day=True)
    manifest = pipeline.run_observation_pipeline("2026-05-04", rerun_rc_verify=False)
    out_dir = outbase / "2026-05-04"
    assert manifest["action_allowed"] is True
    summary = (out_dir / "observation_summary.md").read_text(encoding="utf-8")
    assert "MARKET_CLOSED_AS_OF_DATE" in summary
    assert "今日实盘执行" not in summary
    manual = out_dir / "combined_v2_manual_order_list.csv"
    assert manual.exists()
    assert "next_trading_day_manual_review_only" in manual.read_text(encoding="utf-8")


def test_update_paper_observation_is_paper_only_and_schema_correct(monkeypatch, tmp_path: Path) -> None:
    paths = _ensure_temp_paper_files(tmp_path)
    monkeypatch.setattr(paper, "_observation_paths", lambda: paths)
    report_dir = paths["report_dir"] / "2023-04-04"
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "combined_v2_manual_order_list.csv").write_text(
        "date,profile,ts_code,name,side,action,signal_level,shares,price,next_bar_price,amount\n"
        "2023-04-04,combined_v2,600036.sh,招商银行,BUY,BUY_1,BUY_1,100,10,10,1000\n",
        encoding="utf-8",
    )
    result = paper.update_paper_observation("2023-04-04")
    assert result["broker_connected"] is False
    assert result["auto_order_enabled"] is False
    trades = pd.read_csv(paths["trades"])
    assert list(trades.columns) == paper.PAPER_COLUMNS
    assert set(trades["source"]).issubset(paper.ALLOWED_SOURCES)
    assert set(trades["human_review_status"]).issubset(paper.ALLOWED_REVIEW_STATUS)


def test_observation_scripts_do_not_change_combined_v2_next_bar_results(monkeypatch, tmp_path: Path) -> None:
    execution_before = pd.read_csv(resolve_path("reports/backtest/audit/execution_mode_compare.csv"))
    before = execution_before[(execution_before["profile"] == "combined_v2") & (execution_before["execution_mode"] == "next_bar")].iloc[0]
    trade_hash_before = sha256_path("reports/backtest/combined_v2_trades_detailed.csv")
    _patch_pipeline_common(monkeypatch, tmp_path, data_allowed=False, rc_pass=True)
    pipeline.run_observation_pipeline("2026-05-04", rerun_rc_verify=False)
    execution_after = pd.read_csv(resolve_path("reports/backtest/audit/execution_mode_compare.csv"))
    after = execution_after[(execution_after["profile"] == "combined_v2") & (execution_after["execution_mode"] == "next_bar")].iloc[0]
    for column in ["annual_return", "cumulative_return", "max_drawdown", "total_trades"]:
        assert before[column] == after[column]
    assert sha256_path("reports/backtest/combined_v2_trades_detailed.csv") == trade_hash_before
