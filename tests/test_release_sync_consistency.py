from __future__ import annotations

from pathlib import Path

import pandas as pd

from scripts import check_report_freshness as stale_mod
from scripts.check_release_sync_consistency import (
    PAPER_LEDGER_FILES,
    SUMMARY_FORBIDDEN,
    SUMMARY_MD,
    SYNC_CSV,
    build_release_sync_consistency_check,
)
from scripts.check_report_freshness import build_report_freshness_check
from src.utils.config import resolve_path


EXPECTED_NEXT_BAR = {
    "annual_return": 0.0713520247687258,
    "cumulative_return": 0.2196444045310004,
    "max_drawdown": -0.0936454742991675,
    "total_trades": 76,
    "final_nav": 243928.8809062001,
}


def _sync_frame() -> pd.DataFrame:
    return pd.read_csv(resolve_path(SYNC_CSV))


def test_observation_sync_check_marks_key_files_keep_tracked() -> None:
    sync = _sync_frame().set_index("file_path")
    assert sync.loc["config/observation.yml", "action"] == "KEEP_TRACKED"
    assert sync.loc["scripts/verify_combined_v2_rc.py", "action"] == "KEEP_TRACKED"
    assert sync.loc["scripts/run_observation_pipeline.py", "action"] == "KEEP_TRACKED"
    assert sync.loc["docs/manual_observation_protocol.md", "action"] == "KEEP_TRACKED"


def test_observation_sync_check_keeps_real_paper_ledger_local_only() -> None:
    sync = _sync_frame().set_index("file_path")
    for path in PAPER_LEDGER_FILES:
        assert sync.loc[path, "action"] == "IGNORE_LOCAL_ONLY"
        assert bool(sync.loc[path, "ignored_by_git"]) is True


def test_observation_sync_check_has_no_add_or_investigate_actions() -> None:
    sync = _sync_frame()
    actions = sync["action"].astype(str)
    assert int((actions == "ADD_TO_GIT").sum()) == 0
    assert int((actions == "INVESTIGATE").sum()) == 0


def test_release_sync_summary_removes_pre_commit_state_phrases() -> None:
    text = resolve_path(SUMMARY_MD).read_text(encoding="utf-8")
    for phrase in SUMMARY_FORBIDDEN:
        assert phrase not in text


def test_release_sync_consistency_outputs_all_pass() -> None:
    frame = build_release_sync_consistency_check(write_report=False)
    assert set(frame["status"]) == {"PASS"}


def test_stale_report_check_detects_release_sync_stale_sentence(tmp_path: Path) -> None:
    stale = tmp_path / "observation_release_sync_summary.md"
    stale.write_text("报告生成时尚未提交\n当前 HEAD commit: 6d16a186b7ccdf06aaeed7882c7847cafddc0aaf\n", encoding="utf-8")
    frame = build_report_freshness_check(
        scan_globs=[str(stale)],
        output_csv=tmp_path / "stale.csv",
        output_md=tmp_path / "stale.md",
    )
    matched = frame[frame["check_name"] == "release_sync_stale_residue"]
    assert not matched.empty
    assert set(matched["status"]) == {"FAIL"}


def test_stale_report_check_detects_current_stale_blocked_report(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path

    def fake_resolve(path: str | Path) -> Path:
        candidate = Path(path)
        return candidate if candidate.is_absolute() else root / candidate

    monkeypatch.setattr(stale_mod, "resolve_path", fake_resolve)
    obs_dir = root / "reports" / "observation" / "2026-05-04"
    obs_dir.mkdir(parents=True, exist_ok=True)
    (obs_dir / "data_freshness_report.json").write_text(
        '{"allowed_actions":"observation_report_allowed","blocking_reason":"NONE"}',
        encoding="utf-8",
    )
    (obs_dir / "observation_run_manifest.json").write_text('{"action_allowed":true}', encoding="utf-8")
    (obs_dir / "observation_summary.md").write_text("MARKET_CLOSED_AS_OF_DATE\n", encoding="utf-8")
    (obs_dir / "observation_blocked.md").write_text(
        "blocking_reason: STALE_DATA_BLOCKED\ndata_max_date: 2026-04-03\nstale_trading_days: 18\naction_allowed: false\n",
        encoding="utf-8",
    )
    attribution = root / "reports" / "backtest" / "attribution" / "combined_v2_attribution_report.md"
    attribution.parent.mkdir(parents=True, exist_ok=True)
    attribution.write_text("\n".join(stale_mod.REQUIRED_ATTRIBUTION_SECTIONS), encoding="utf-8")

    frame = stale_mod.build_report_freshness_check(
        scan_globs=[],
        output_csv=root / "stale.csv",
        output_md=root / "stale.md",
    )
    matched = frame[frame["check_name"] == "observation_gate_allowed_no_stale_blocked_content"]
    assert not matched.empty
    assert set(matched["status"]) == {"FAIL"}


def test_combined_v2_next_bar_metrics_remain_exact() -> None:
    execution = pd.read_csv(resolve_path("reports/backtest/audit/execution_mode_compare.csv"))
    row = execution[(execution["profile"] == "combined_v2") & (execution["execution_mode"] == "next_bar")].iloc[0]
    assert float(row["annual_return"]) == EXPECTED_NEXT_BAR["annual_return"]
    assert float(row["cumulative_return"]) == EXPECTED_NEXT_BAR["cumulative_return"]
    assert float(row["max_drawdown"]) == EXPECTED_NEXT_BAR["max_drawdown"]
    assert int(row["total_trades"]) == EXPECTED_NEXT_BAR["total_trades"]
    assert 200000.0 * (1.0 + float(row["cumulative_return"])) == EXPECTED_NEXT_BAR["final_nav"]
