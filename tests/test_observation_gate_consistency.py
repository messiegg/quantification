from __future__ import annotations

import json
from pathlib import Path

from scripts import check_observation_gate_consistency as gate


def _patch_gate_config(monkeypatch, tmp_path: Path) -> Path:
    outbase = tmp_path / "reports" / "observation"
    monkeypatch.setattr(
        gate,
        "load_yaml_optional",
        lambda path: {"manual_observation": {"observation_report_dir": str(outbase)}},
    )
    return outbase


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _allowed_freshness() -> dict:
    return {
        "allowed_actions": "observation_report_allowed",
        "requested_as_of_is_trading_day": False,
        "market_closed_as_of_date": True,
        "target_trading_date": "2026-04-30",
        "stale_calendar_days": 4,
        "max_stale_calendar_days": 3,
        "stale_trading_days": 0,
        "warnings": ["STALE_CALENDAR_DAYS_EXCEED_LIMIT_NON_TRADING_DAY_WARN"],
        "blocking_reason": "NONE",
    }


def test_observation_gate_consistency_passes_for_allowed_holiday_summary(monkeypatch, tmp_path: Path) -> None:
    out_dir = _patch_gate_config(monkeypatch, tmp_path) / "2026-05-04"
    _write_json(out_dir / "data_freshness_report.json", _allowed_freshness())
    _write_json(out_dir / "data_quality_observation_report.json", {"status": "WARN"})
    _write_json(out_dir / "observation_run_manifest.json", {"action_allowed": True})
    (out_dir / "observation_summary.md").write_text(
        "MARKET_CLOSED_AS_OF_DATE\n- data_quality_status: WARN\n- 禁止自动下单。\n",
        encoding="utf-8",
    )
    (out_dir / "combined_v2_manual_order_list.csv").write_text(
        "execution_scope,auto_order_allowed,requires_human_review\n"
        "NEXT_TRADING_DAY_MANUAL_REVIEW_ONLY,False,True\n",
        encoding="utf-8",
    )
    frame = gate.build_observation_gate_consistency_check("2026-05-04", write_report=False)
    assert set(frame["status"]) == {"PASS"}


def test_observation_gate_consistency_fails_current_blocked_when_allowed(monkeypatch, tmp_path: Path) -> None:
    out_dir = _patch_gate_config(monkeypatch, tmp_path) / "2026-05-04"
    _write_json(out_dir / "data_freshness_report.json", _allowed_freshness())
    _write_json(out_dir / "observation_run_manifest.json", {"action_allowed": True})
    (out_dir / "observation_summary.md").write_text("MARKET_CLOSED_AS_OF_DATE\n", encoding="utf-8")
    (out_dir / "observation_blocked.md").write_text("STALE_DATA_BLOCKED\n", encoding="utf-8")
    frame = gate.build_observation_gate_consistency_check("2026-05-04", write_report=False)
    failed = frame[frame["status"] == "FAIL"]
    assert "GATE-001A" in set(failed["check_id"])
    assert "GATE-001B" in set(failed["check_id"])


def test_observation_gate_consistency_allows_legacy_blocked_when_allowed(monkeypatch, tmp_path: Path) -> None:
    out_dir = _patch_gate_config(monkeypatch, tmp_path) / "2026-05-04"
    _write_json(out_dir / "data_freshness_report.json", _allowed_freshness())
    _write_json(out_dir / "observation_run_manifest.json", {"action_allowed": True})
    (out_dir / "observation_summary.md").write_text("MARKET_CLOSED_AS_OF_DATE\n", encoding="utf-8")
    (out_dir / "observation_blocked.md").write_text("LEGACY_SUPERSEDED\nSTALE_DATA_BLOCKED\n", encoding="utf-8")
    frame = gate.build_observation_gate_consistency_check("2026-05-04", write_report=False)
    assert not set(frame[frame["status"] == "FAIL"]["check_id"]) & {"GATE-001A", "GATE-001B", "GATE-001C"}


def test_observation_gate_consistency_fails_tracked_current_blocked_when_allowed(monkeypatch, tmp_path: Path) -> None:
    out_dir = _patch_gate_config(monkeypatch, tmp_path) / "2026-05-04"
    _write_json(out_dir / "data_freshness_report.json", _allowed_freshness())
    _write_json(out_dir / "observation_run_manifest.json", {"action_allowed": True})
    (out_dir / "observation_summary.md").write_text("MARKET_CLOSED_AS_OF_DATE\n", encoding="utf-8")
    (out_dir / "observation_blocked.md").write_text("action_allowed: false\nstale_trading_days: 18\n", encoding="utf-8")
    monkeypatch.setattr(gate, "_git_tracked", lambda path: True)
    frame = gate.build_observation_gate_consistency_check("2026-05-04", write_report=False)
    failed = frame[frame["status"] == "FAIL"]
    assert "GATE-001C" in set(failed["check_id"])


def test_observation_gate_consistency_blocks_summary_in_historical_review(monkeypatch, tmp_path: Path) -> None:
    out_dir = _patch_gate_config(monkeypatch, tmp_path) / "2026-05-04"
    _write_json(
        out_dir / "data_freshness_report.json",
        {"allowed_actions": "historical_review_only", "requested_as_of_is_trading_day": False},
    )
    (out_dir / "observation_summary.md").write_text("stale summary\n", encoding="utf-8")
    frame = gate.build_observation_gate_consistency_check("2026-05-04", write_report=False)
    failed = frame[frame["status"] == "FAIL"]
    assert "GATE-004" in set(failed["check_id"])
    assert "GATE-005" in set(failed["check_id"])
