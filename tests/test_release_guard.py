from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from scripts import run_release_guard as guard
from src.utils.config import resolve_path


pytestmark = pytest.mark.release_guard

EXPECTED_NEXT_BAR = {
    "annual_return": 0.024846220411411934,
    "cumulative_return": 0.07326562069200016,
    "max_drawdown": -0.08876605706976393,
    "total_trades": 41,
    "final_nav": 53663.281034600004,
}


def _pass_frame() -> pd.DataFrame:
    return pd.DataFrame([{"status": "PASS"}])


def _patch_base_guard(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setattr(guard, "build_config_consistency_report", lambda *args, **kwargs: {"status": "PASS"})
    monkeypatch.setattr(guard, "build_universe_integrity_report", lambda *args, **kwargs: {"status": "PASS"})
    monkeypatch.setattr(guard, "build_universe_shortfall_report", lambda *args, **kwargs: {"status": "PASS", "shortfall_to_target": 0})
    monkeypatch.setattr(guard, "build_audit_data_freshness_report", lambda *args, **kwargs: {"status": "PASS", "target_trade_date": "2026-05-04"})
    monkeypatch.setattr(guard, "build_account_constraints_report", lambda *args, **kwargs: {"status": "PASS", "warnings": []})
    monkeypatch.setattr(guard, "build_account_suitability_report", lambda *args, **kwargs: {"status": "PASS", "base_case": {"executable_raw_buy_ratio": 0.5}})
    monkeypatch.setattr(
        guard,
        "_check_account_profile_comparison",
        lambda rows: rows.append(
            {
                "check_id": "RG-ACCOUNT-003",
                "check_name": "fixture",
                "status": "PASS",
                "expected": "",
                "actual": "",
                "evidence": "",
                "recommendation": "",
            }
        )
        or {"status": "PASS", "profiles": [{"profile": "actual_50k_retail", "executable_raw_buy_ratio": 0.5}]},
    )
    monkeypatch.setattr(guard, "build_observation_evidence_chain", lambda *args, **kwargs: {"status": "PASS"})
    monkeypatch.setattr(guard, "_check_lookahead_audit", lambda rows: rows.append({"check_id": "RG-LOOKAHEAD-001", "check_name": "fixture", "status": "PASS", "expected": "", "actual": "", "evidence": "", "recommendation": ""}))
    monkeypatch.setattr(guard, "_check_sensitivity", lambda rows: rows.append({"check_id": "RG-SENS-001", "check_name": "fixture", "status": "PASS", "expected": "", "actual": "", "evidence": "", "recommendation": ""}))
    monkeypatch.setattr(guard, "build_sensitivity_trigger_coverage_report", lambda *args, **kwargs: {"status": "PASS", "classifications": []})
    monkeypatch.setattr(guard, "_check_baseline_comparison", lambda rows: rows.append({"check_id": "RG-BASELINE-001", "check_name": "fixture", "status": "PASS", "expected": "", "actual": "", "evidence": "", "recommendation": ""}))
    monkeypatch.setattr(guard, "build_module_contribution_report", lambda *args, **kwargs: {"status": "PASS", "modules": []})
    monkeypatch.setattr(guard, "_check_tests_status", lambda rows: rows.append({"check_id": "RG-TESTS-001", "check_name": "fixture", "status": "PASS", "expected": "", "actual": "", "evidence": "", "recommendation": ""}))
    monkeypatch.setattr(guard, "evaluate_observation_readiness", lambda *args, **kwargs: {"status": "READY"})
    monkeypatch.setattr(guard, "build_release_status_consistency_report", lambda *args, **kwargs: {"status": "PASS", "expected_current_release_status": "PASS_CANDIDATE"})
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


def test_run_release_guard_fails_closed_on_invalid_universe(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_base_guard(monkeypatch, tmp_path)
    monkeypatch.setattr(
        guard,
        "build_universe_integrity_report",
        lambda *args, **kwargs: {"status": "FAIL", "violations": [{"code": "UNIVERSE_UNDER_FLOOR"}]},
    )

    frame = guard.build_release_guard_report(ci=True, as_of_date="2026-05-04", write_report=False)
    universe = frame[frame["check_id"] == "RG-UNIVERSE-001"].iloc[0]
    assert universe["status"] == "FAIL"
    assert guard._release_status_from_rows(frame) == "FAIL"


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
    assert abs(float(row["annual_return"]) - EXPECTED_NEXT_BAR["annual_return"]) < 1e-12
    assert abs(float(row["cumulative_return"]) - EXPECTED_NEXT_BAR["cumulative_return"]) < 1e-12
    assert abs(float(row["max_drawdown"]) - EXPECTED_NEXT_BAR["max_drawdown"]) < 1e-12
    assert int(row["total_trades"]) == EXPECTED_NEXT_BAR["total_trades"]
    assert 50000.0 * (1.0 + float(row["cumulative_return"])) == EXPECTED_NEXT_BAR["final_nav"]


def test_account_profile_low_50k_ratio_stays_warn(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "status": "PASS",
        "default_release_profile": "actual_50k_lot_aware",
        "profiles": [
            {
                "profile": "actual_50k_lot_aware",
                "executable_raw_buy_ratio": 0.036,
                "buy_trades": 23,
                "max_positions": 8,
                "portfolio_max_positions": 8,
            }
        ],
    }
    monkeypatch.setattr(guard, "_read_json", lambda path: payload)
    rows: list[dict] = []
    result = guard._check_account_profile_comparison(rows)
    assert result is payload
    assert rows[-1]["check_id"] == "RG-ACCOUNT-003"
    assert rows[-1]["status"] == "WARN"


def test_research_only_200k_profile_does_not_change_release_default(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "status": "WARN",
        "default_release_profile": "actual_50k_lot_aware",
        "profiles": [
            {
                "profile": "actual_50k_lot_aware",
                "executable_raw_buy_ratio": 0.036,
                "buy_trades": 23,
                "max_positions": 8,
                "portfolio_max_positions": 8,
            },
            {
                "profile": "capital_200k_maxpos20",
                "research_only": True,
                "executable_raw_buy_ratio": 0.189,
                "buy_trades": 50,
                "max_positions": 20,
                "portfolio_max_positions": 20,
            },
        ],
    }
    monkeypatch.setattr(guard, "_read_json", lambda path: payload)
    rows: list[dict] = []
    guard._check_account_profile_comparison(rows)
    assert "default=actual_50k_lot_aware" in rows[-1]["actual"]
    assert rows[-1]["status"] == "WARN"
