from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from scripts import run_release_guard as guard
from src.utils.config import resolve_path


pytestmark = pytest.mark.release_guard

EXPECTED_NEXT_BAR = {
    "annual_return": 0.0713520247687258,
    "cumulative_return": 0.2196444045310004,
    "max_drawdown": -0.0936454742991675,
    "total_trades": 76,
    "final_nav": 243928.8809062001,
}


def _pass_frame() -> pd.DataFrame:
    return pd.DataFrame([{"status": "PASS"}])


def _patch_base_guard(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setattr(guard, "build_config_consistency_report", lambda *args, **kwargs: {"status": "PASS"})
    monkeypatch.setattr(guard, "build_universe_integrity_report", lambda *args, **kwargs: {"status": "PASS"})
    monkeypatch.setattr(guard, "build_audit_data_freshness_report", lambda *args, **kwargs: {"status": "PASS", "target_trade_date": "2026-05-04"})
    monkeypatch.setattr(guard, "build_account_constraints_report", lambda *args, **kwargs: {"status": "PASS", "warnings": []})
    monkeypatch.setattr(guard, "build_observation_evidence_chain", lambda *args, **kwargs: {"status": "PASS"})
    monkeypatch.setattr(guard, "_check_lookahead_audit", lambda rows: rows.append({"check_id": "RG-LOOKAHEAD-001", "check_name": "fixture", "status": "PASS", "expected": "", "actual": "", "evidence": "", "recommendation": ""}))
    monkeypatch.setattr(guard, "_check_sensitivity", lambda rows: rows.append({"check_id": "RG-SENS-001", "check_name": "fixture", "status": "PASS", "expected": "", "actual": "", "evidence": "", "recommendation": ""}))
    monkeypatch.setattr(guard, "_check_baseline_comparison", lambda rows: rows.append({"check_id": "RG-BASELINE-001", "check_name": "fixture", "status": "PASS", "expected": "", "actual": "", "evidence": "", "recommendation": ""}))
    monkeypatch.setattr(guard, "_check_tests_status", lambda rows: rows.append({"check_id": "RG-TESTS-001", "check_name": "fixture", "status": "PASS", "expected": "", "actual": "", "evidence": "", "recommendation": ""}))
    monkeypatch.setattr(guard, "_write_release_manifest", lambda *args, **kwargs: None)
    monkeypatch.setattr(guard, "build_report_freshness_check", lambda *args, **kwargs: _pass_frame())
    monkeypatch.setattr(guard, "build_release_sync_consistency_check", lambda *args, **kwargs: _pass_frame())
    monkeypatch.setattr(guard, "build_report_path_sanitization_check", lambda *args, **kwargs: _pass_frame())
    monkeypatch.setattr(guard, "build_observation_gate_consistency_check", lambda *args, **kwargs: _pass_frame())
    monkeypatch.setattr(guard, "verify_release_candidate", lambda *args, **kwargs: _pass_frame())
    monkeypatch.setattr(guard, "build_forbidden_tracked_files_check", lambda *args, **kwargs: _pass_frame())
    monkeypatch.setattr(guard, "_git_tracked_paths", lambda pathspecs: [])

    def fake_resolve(path: str | Path) -> Path:
        candidate = Path(path)
        return candidate if candidate.is_absolute() else tmp_path / candidate

    monkeypatch.setattr(guard, "resolve_path", fake_resolve)
    return tmp_path / "reports" / "observation" / "2026-05-04"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_run_release_guard_current_state_fails_closed_on_invalid_universe() -> None:
    frame = guard.build_release_guard_report(ci=True, as_of_date="2026-05-04", write_report=False)
    universe = frame[frame["check_id"] == "RG-UNIVERSE-001"].iloc[0]
    assert universe["status"] == "FAIL"


def test_run_release_guard_fails_allowed_and_blocked_conflict(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    obs_dir = _patch_base_guard(monkeypatch, tmp_path)
    _write_json(obs_dir / "data_freshness_report.json", {"allowed_actions": "observation_report_allowed"})
    (obs_dir / "observation_summary.md").write_text("MARKET_CLOSED_AS_OF_DATE\n", encoding="utf-8")
    (obs_dir / "observation_blocked.md").write_text("STALE_DATA_BLOCKED\n", encoding="utf-8")

    frame = guard.build_release_guard_report(ci=True, as_of_date="2026-05-04", write_report=False)
    failed = frame[frame["status"] == "FAIL"]
    assert "OBS-CONFLICT-001" in set(failed["check_id"])


def test_run_release_guard_fails_when_path_sanitization_fails(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    obs_dir = _patch_base_guard(monkeypatch, tmp_path)
    _write_json(obs_dir / "data_freshness_report.json", {"allowed_actions": "observation_report_allowed"})
    (obs_dir / "observation_summary.md").write_text("MARKET_CLOSED_AS_OF_DATE\n", encoding="utf-8")
    monkeypatch.setattr(
        guard,
        "build_report_path_sanitization_check",
        lambda *args, **kwargs: pd.DataFrame([{"status": "FAIL", "evidence": "/Users/local/path"}]),
    )

    frame = guard.build_release_guard_report(ci=True, as_of_date="2026-05-04", write_report=False)
    row = frame[frame["check_id"] == "RG-003"].iloc[0]
    assert row["status"] == "FAIL"


def test_run_release_guard_fails_when_manual_order_list_is_tracked(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    obs_dir = _patch_base_guard(monkeypatch, tmp_path)
    _write_json(obs_dir / "data_freshness_report.json", {"allowed_actions": "observation_report_allowed"})
    (obs_dir / "observation_summary.md").write_text("MARKET_CLOSED_AS_OF_DATE\n", encoding="utf-8")
    monkeypatch.setattr(
        guard,
        "_git_tracked_paths",
        lambda pathspecs: ["reports/observation/2026-05-04/combined_v2_manual_order_list.csv"]
        if pathspecs == guard.MANUAL_ORDER_PATTERNS
        else [],
    )

    frame = guard.build_release_guard_report(ci=True, as_of_date="2026-05-04", write_report=False)
    row = frame[frame["check_id"] == "GIT-MANUAL-001"].iloc[0]
    assert row["status"] == "FAIL"


def test_combined_v2_next_bar_metrics_remain_exact_after_release_guard_changes() -> None:
    execution = pd.read_csv(resolve_path("reports/backtest/audit/execution_mode_compare.csv"))
    row = execution[(execution["profile"] == "combined_v2") & (execution["execution_mode"] == "next_bar")].iloc[0]
    assert float(row["annual_return"]) == EXPECTED_NEXT_BAR["annual_return"]
    assert float(row["cumulative_return"]) == EXPECTED_NEXT_BAR["cumulative_return"]
    assert float(row["max_drawdown"]) == EXPECTED_NEXT_BAR["max_drawdown"]
    assert int(row["total_trades"]) == EXPECTED_NEXT_BAR["total_trades"]
    assert 200000.0 * (1.0 + float(row["cumulative_return"])) == EXPECTED_NEXT_BAR["final_nav"]
